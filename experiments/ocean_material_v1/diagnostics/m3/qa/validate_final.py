"""Validate physical fixtures, effective controls and predeclared M3 comparisons."""
import hashlib
import json
from pathlib import Path
import re
import struct
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text())


def exr_dimensions(path):
    """Read the standard OpenEXR dataWindow header without a new dependency."""
    data = path.read_bytes()
    assert data[:4] == b'v/1\x01'
    offset = 8
    while data[offset] != 0:
        end = data.index(0, offset); name = data[offset:end].decode('ascii'); offset = end+1
        end = data.index(0, offset); kind = data[offset:end].decode('ascii'); offset = end+1
        size = struct.unpack_from('<I', data, offset)[0]; offset += 4
        if name == 'dataWindow':
            assert kind == 'box2i' and size == 16
            xmin,ymin,xmax,ymax = struct.unpack_from('<4i', data, offset)
            return xmax-xmin+1,ymax-ymin+1
        offset += size
    raise ValueError('Missing OpenEXR dataWindow')


def main():
    rows = read(ROOT / 'qa/measurements_final.json')['rows']
    assert len(rows) == 26, len(rows)
    checks = []
    for row in rows:
        d = ROOT / row['directory']
        metadata, fixture, effective = [read(d / p) for p in ('metadata.json', 'fixture.json', 'effective_settings.json')]
        q = metadata['request']; unit = q['meters_per_scene_unit']
        assert metadata['protocol'] == 'controlled_v3_unclamped_effective_usd_settings'
        assert metadata['default_stage_retained']
        assert metadata['target_visibility_modified'] is False
        assert metadata['actual_viewport_resolution'] == [512, 384]
        assert metadata['render_product']['resolution'] == [512, 384]
        assert metadata['completed_rendered_frame_wait'] == 64
        assert metadata['scene_sha256'] == hashlib.sha256((d/'scene.usda').read_bytes()).hexdigest()
        assert metadata['gpu_before']['free_mib'] >= 768
        assert effective['render_product']['omni:rtx:rendermode'] == 'PathTracing'
        for key in ('omni:rtx:fog:enabled', 'omni:rtx:pt:fireflyFilter:enabled', 'omni:rtx:rtpt:fireflyFilter:enabled'):
            assert effective['render_product'][key] == 'False', key
        assert effective['camera']['omni:rtx:autoExposure:enabled'] == 'False'
        assert float(effective['camera']['exposure']) == (1 if q['exposure_probe'] else 0)
        assert effective['render_product']['omni:rtx:post:tonemap:operator'] == ('raw' if q['tone_map_probe'] else 'acesApproximation')
        np.testing.assert_allclose(metadata['intrinsics_px']['fx'], 875, rtol=1e-6)
        matrix = np.array(metadata['actual_view_matrix'])
        # With this nadir basis, row-vector view translation (0,0,-3/unit).
        np.testing.assert_allclose(matrix[3, :3]*unit, [0, 0, -3], atol=1e-8)
        clip = [float(s) for s in re.findall(r'[-+0-9.eE]+', effective['camera']['clippingRange'])]
        np.testing.assert_allclose(np.array(clip)*unit, [.01, 25], rtol=1e-6)
        g = fixture['geometry']
        np.testing.assert_allclose(g['measured_target_world_size_m'], [.18, 0, .18], atol=1e-6)
        assert g['target_center_m'] == [0, -q['depth_m'], 0]
        assert g['background_y_m'] == -1.8 and g['closed'] and g['boundary_edges'] == 0
        assert g['opacity_override_authored'] is False
        assert fixture['parameters'] == metadata['medium_parameters']
        assert fixture['parameters']['thin_walled'] is False
        for image in ('rgb.png', 'warmup.png'):
            with Image.open(d/image) as im:
                assert im.size == (512, 384); im.verify()
        assert exr_dimensions(d/'hdr.exr') == (512,384)
        array = np.load(d/'hdr.npz', allow_pickle=False)['rgba']
        assert array.shape == (384, 512, 4) and array.dtype == np.float32
        assert metadata['hdr_buffer']['format'] == 'TextureFormat.RGBA16_SFLOAT'
        assert np.isfinite(array).all()
        checks.append({'directory': row['directory'], 'physical_geometry_camera_controls_outputs_ok': True})

    def select(condition, depth=.75, distance=100, unit=.01):
        return next(r for r in rows if r['request']['condition'] == condition and r['request']['depth_m'] == depth
                    and r['request']['native_distance'] == distance and r['request']['meters_per_scene_unit'] == unit
                    and not r['request']['tone_map_probe'] and not r['request']['exposure_probe'])

    repeats = {}
    for suite, condition in [('controls','clear'), ('scattering','scattering_low'), ('scattering','scattering_high')]:
        pair = [r for r in rows if r['suite'] == suite and r['request']['condition'] == condition
                and r['request']['depth_m'] == .75 and not r['request']['tone_map_probe']]
        assert len(pair) == 2
        relative = np.abs(np.array(pair[1]['hdr']['signal_rgb']) / pair[0]['hdr']['signal_rgb'] - 1)
        assert max(relative) <= .03, (condition, relative)
        repeats[condition] = relative.tolist()
    units = np.abs(np.array(select('absorption', unit=1, distance=1)['hdr']['signal_relative_to_clear_rgb']) /
                   select('absorption')['hdr']['signal_relative_to_clear_rgb'] - 1)
    assert max(units) <= .03, units
    beer_errors = []
    for depth in (.25, .75, 1.25):
        for distance in (50,100,200):
            row = select('absorption',depth,distance)
            expected = np.array([.6,.8,.9])**(depth/(distance*.01))
            observed = np.array(row['hdr']['signal_relative_to_clear_rgb'])
            error = np.abs(observed/expected-1)
            beer_errors.append({'depth_m':depth,'native_distance':distance,'expected_rgb':expected.tolist(),
                                'observed_rgb':observed.tolist(),'relative_error_rgb':error.tolist()})
    # Formal depth/parameter effect uses the predeclared >3% criterion;
    # Beer-law agreement above is an additional model consistency diagnostic.
    assert np.max(np.abs(np.array(select('absorption',1.25)['hdr']['signal_rgb']) /
                         select('absorption',.25)['hdr']['signal_rgb'] - 1)) > .03
    assert np.max(np.abs(np.array(select('absorption',distance=50)['hdr']['signal_rgb']) /
                         select('absorption',distance=200)['hdr']['signal_rgb'] - 1)) > .03
    scatter_changes = {}
    for condition in ('scattering_low','scattering_high'):
        differences = []
        for depth in (.25,.75,1.25):
            a,b = select('absorption',depth),select(condition,depth)
            signal = np.array(b['hdr']['signal_rgb'])/a['hdr']['signal_rgb']-1
            background = np.array(b['hdr']['background_rgb'])/a['hdr']['background_rgb']-1
            differences.append({'depth_m':depth,'relative_signal_change_rgb':signal.tolist(),
                                'relative_background_change_rgb':background.tolist()})
        assert any(max(np.abs(d['relative_signal_change_rgb']))>.03 or
                   max(np.abs(d['relative_background_change_rgb']))>.03 for d in differences)
        scatter_changes[condition] = differences
    normal = select('clear')
    raw = next(r for r in rows if r['request']['tone_map_probe'])
    hdr_diff = np.abs(np.array(raw['hdr']['signal_rgb'])/normal['hdr']['signal_rgb']-1)
    assert max(hdr_diff) <= .03
    assert np.max(np.abs(np.array(raw['ldr']['background_rgb'])-normal['ldr']['background_rgb'])) > 1/255
    result = {'ok':True,'accepted_capture_count':len(rows),'per_capture_checks':checks,
              'relative_repeat_signal_changes_rgb':repeats,'relative_compensated_unit_error_rgb':units.tolist(),
              'absorption_vs_declared_beer_prediction':beer_errors,'scattering_changes':scatter_changes,
              'raw_tonemap_hdr_signal_relative_change_rgb':hdr_diff.tolist(),
              'tolerance_fraction':.03,'status':'passed_declared_isolated_unclamped_pathtracing_engineering_scope'}
    (ROOT/'qa/final_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('per_capture_checks','absorption_vs_declared_beer_prediction','scattering_changes')},indent=2))


if __name__=='__main__':
    main()
