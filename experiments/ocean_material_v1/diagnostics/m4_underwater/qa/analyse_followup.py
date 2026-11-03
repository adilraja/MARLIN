"""Check the retained native probes; never relabel failed optics as a pass."""
import ast
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[3]
sys.path.insert(0, str(ROOT.parent / 'm3/qa'))
from validate_final import exr_dimensions


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    qa = ROOT / 'qa'
    rows = []
    for response_file in sorted(qa.glob('probe*.json')):
        record = read(response_file)
        response = record['response']
        assert response['ok'], response_file
        directory = Path(response['directory'])
        metadata = read(directory / 'metadata.json')
        assert metadata['scene_sha256'] == hashlib.sha256((directory / 'scene.usdc').read_bytes()).hexdigest()
        assert metadata['actual_viewport_resolution'] == [512, 384]
        assert metadata['gpu_before']['free_mib'] >= 768
        assert exr_dimensions(directory / 'hdr.exr') == (512, 384)
        for name in ('rgb.png', 'warmup.png'):
            with Image.open(directory / name) as image:
                assert image.size == (512, 384)
                image.verify()
        samples = np.load(directory / 'hdr.npz', allow_pickle=False)['rgba']
        assert samples.shape == (384, 512, 4) and np.isfinite(samples).all()
        geometry = metadata['integrated_geometry']
        assert geometry['boundary_edges'] == geometry['nonmanifold_edges'] == geometry['same_direction_shared_edges'] == 0
        assert geometry['minimum_top_normal_y'] > 0
        assert geometry['minimum_outward_side_dot'] > 0
        assert geometry['maximum_bottom_normal_y'] < 0
        restored = read(directory / 'restoration.json')
        assert all(restored['ocean_root_attributes_restored'].values())
        assert all(v for k, v in restored.items() if k != 'ocean_root_attributes_restored')
        effective = read(directory / 'effective_settings.json')
        assert effective['render_product']['omni:rtx:rendermode'] == 'PathTracing'
        assert effective['render_product']['omni:rtx:fog:enabled'] == 'False'
        assert effective['render_product']['omni:rtx:pt:fireflyFilter:enabled'] == 'False'
        assert effective['camera']['omni:rtx:autoExposure:enabled'] == 'False'
        matrix = np.linalg.inv(np.array(metadata['capture_view_matrix']))
        position = matrix[3, :3] * metadata['config']['meters_per_scene_unit']
        inside = record['request']['view'] == 'inside'
        np.testing.assert_allclose(position, [12, -.5 if inside else 3, 0], atol=1e-8)
        mean = samples[184:200, 248:264, :3].mean(axis=(0, 1)).astype(float)
        if inside:
            np.testing.assert_allclose(mean, [11336] * 3, atol=1e-6)
        rows.append({'response_record': response_file.name,
                     'directory': str(directory.relative_to(ROOT)),
                     'request': record['request'], 'actual_camera_position_m': position.tolist(),
                     'target_roi_mean_rgb': mean.tolist(), 'gpu_free_before_mib': metadata['gpu_before']['free_mib'],
                     'geometry_image_controls_and_restoration_checks_passed': True,
                     'inside_attenuation_qualified': False if inside else None})
    assert len(rows) == 15
    before, after = read(qa / 'before_checkpoint.json'), read(qa / 'final_checkpoint.json')
    restoration = {name + '_restored': before[name] == after[name]
                   for name in ('renderer_settings', 'camera', 'resolution', 'fill_frame', 'display_options')}
    restoration['renderer_setting_count'] = len(before['renderer_settings'])
    restoration['original_material_restored'] = read(qa / 'final_material.json') == read(ROOT.parent / 'm4/qa/final_material.json')
    settings = ast.literal_eval(read(qa / 'final_medium_capabilities.json')['rtx_settings_tree'])
    restoration['extra_ptvol_global_restored_false'] = settings['pathtracing']['ptvol']['enabled'] is False
    assert all(v for k, v in restoration.items() if k != 'renderer_setting_count')
    write(qa / 'restoration_validation.json', restoration)
    history = {}
    base = REPO / 'experiments/ocean_material_v1'
    for name, manifest, prefix in (
        ('m1', base / 'manifest.json', base),
        ('m2', base / 'diagnostics/m2/manifest.json', REPO),
        ('m3', base / 'diagnostics/m3/manifest.json', REPO),
        ('initial_m4', base / 'diagnostics/m4/manifest.json', REPO),
    ):
        entries = read(manifest)['files']
        for entry in entries:
            data = (prefix / entry['path']).read_bytes()
            assert len(data) == entry['bytes'] and hashlib.sha256(data).hexdigest() == entry['sha256'], entry['path']
        history[name] = {'pinned_evidence_files': len(entries), 'unchanged': True}
    write(qa / 'historical_evidence_integrity.json', history)
    result = {'successful_capture_requests': len(rows),
              'inside_views': sum(row['request']['view'] == 'inside' for row in rows),
              'above_water_controls': sum(row['request']['view'] == 'nadir' for row in rows),
              'fixed_hdr_roi': {'rows': [184, 200], 'columns': [248, 264], 'coordinates': 'zero-based half-open'},
              'observations': rows,
              'minimum_observed_pre_request_free_mib': min(row['gpu_free_before_mib'] for row in rows),
              'gpu_guard_mib': 768, 'controlled_restarts_this_followup': 1,
              'camera_inside_attenuation_resolved': False, 'full_milestone_complete': False,
              'status': 'native_material_probes_and_flat_enclosure_reproduced_unresolved_inside_medium_attenuation',
              'diagnostic_data_and_restoration_checks_passed': True}
    write(qa / 'probe_validation.json', result)
    figures = ROOT / 'comparisons'
    figures.mkdir(exist_ok=True)
    selected = ['probe_flat_box_clear_nadir.json', 'probe_flat_box_nadir.json',
                'probe_flat_box_clear_inside.json', 'probe_flat_box_inside.json']
    canvas = Image.new('RGB', (1024, 900), '#10202a')
    draw = ImageDraw.Draw(canvas)
    draw.text((10, 10), 'Native HDR: same log1p(RGB)/log1p(12000) preview mapping; no per-image scaling', fill='white')
    for index, name in enumerate(selected):
        row = next(row for row in rows if row['response_record'] == name)
        samples = np.load(ROOT / row['directory'] / 'hdr.npz', allow_pickle=False)['rgba'][..., :3]
        display = np.uint8(np.clip(np.log1p(np.maximum(samples, 0)) / np.log1p(12000), 0, 1) * 255)
        x, y = index % 2 * 512, index // 2 * 430 + 36
        label = name.removeprefix('probe_').removesuffix('.json')
        draw.text((x + 8, y + 5), label, fill='white')
        draw.text((x + 8, y + 20), 'Centre RGB: ' + str([round(v, 1) for v in row['target_roi_mean_rgb']]), fill='white')
        canvas.paste(Image.fromarray(display), (x, y + 40))
    canvas.save(figures / 'flat_enclosure_controls.png')
    print(json.dumps({k: v for k, v in result.items() if k != 'observations'}, indent=2))


if __name__ == '__main__':
    main()
