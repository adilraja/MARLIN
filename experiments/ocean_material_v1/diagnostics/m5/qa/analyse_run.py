"""Evaluate actual M5 images, independently recorded state and resource evidence."""
import ast
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

from compare_images import metrics, read

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[3]
ATTEMPT = sys.argv[1] if len(sys.argv) == 2 else '03'
if ATTEMPT not in ('01', '02', '03'):
    raise ValueError('Unknown recorded attempt')
RUN = ROOT / ('runs/attempt' + ATTEMPT)


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def settings_comparator():
    # Reuse the canonical pure function without importing Kit-only modules.
    path = REPO / 'source/extensions/cris.madil.render_service/cris/madil/render_service/hidef_marine.py'
    function = next(n for n in ast.parse(path.read_text()).body
                    if isinstance(n, ast.FunctionDef) and n.name == 'same_settings')
    namespace = {'math': math}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace['same_settings'], dict(path=str(path.relative_to(REPO)), sha256=digest(path))


def hdr_metrics(reference, candidate):
    with np.load(reference) as data:
        a = data['rgba'][..., :3].astype(np.float64)
    with np.load(candidate) as data:
        b = data['rgba'][..., :3].astype(np.float64)
    if a.shape != (384, 512, 3) or b.shape != a.shape or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('Invalid native HDR data')
    result = {}
    for name, x, y in (('full_rgb', a, b), ('fixed_central_roi', a[96:288, 128:384], b[96:288, 128:384])):
        difference = np.abs(x-y)
        result[name] = dict(mean_absolute_difference=float(difference.mean()),
              p99_absolute_difference=float(np.percentile(difference, 99)), maximum_absolute_difference=float(difference.max()),
              mean_absolute_difference_divided_by_reference_mean_abs=float(difference.mean()/max(np.abs(x).mean(), 1e-12)),
              reference_rgb_mean=x.mean(axis=(0, 1)).tolist(), candidate_rgb_mean=y.mean(axis=(0, 1)).tolist())
    return dict(results=result, acceptance='Diagnostic only; no predeclared M5 HDR tolerance and no absolute radiometric calibration')


def compare_state(a, b, same_settings):
    matrices = {name: float(np.max(np.abs(np.array(a['projection'][name])-np.array(b['projection'][name]))))
                for name in ('capture_view_matrix', 'capture_projection_matrix')}
    controls_equal = same_settings(a['effective_controls'], b['effective_controls'])
    control_changes = {label: sorted(key for key in set(a['effective_controls'][label]) | set(b['effective_controls'][label])
                          if not same_settings(a['effective_controls'][label].get(key), b['effective_controls'][label].get(key)))
                      for label in a['effective_controls']}
    p, q = a['state']['prim_hashes'], b['state']['prim_hashes']
    changed_prims = sorted(key for key in set(p) | set(q) if p.get(key) != q.get(key))
    globals_equal = same_settings(a['renderer_globals'], b['renderer_globals'])
    checks = dict(camera_matrices_within_1e_6=all(v <= 1e-6 for v in matrices.values()),
                  scene_input_hashes_equal=not changed_prims,
                  effective_camera_product_controls_equal=controls_equal,
                  renderer_globals_equal=globals_equal)
    return dict(checks=checks, all_state_checks_passed=all(checks.values()),
                maximum_matrix_differences=matrices, changed_prims=changed_prims, changed_effective_controls=control_changes)


def main():
    assert load(RUN / 'done.json')['ok']
    assert all(load(RUN / 'restoration.json').values())
    rows = load(RUN / 'capture_records.json')
    records = {row['label']: row for row in rows}
    required = ('baseline', 'repeat_a', 'repeat_b', 'reload_a', 'reload_b')
    assert all(name in records for name in required)
    same_settings, comparator_source = settings_comparator()
    baseline = records['baseline']
    reference = read(RUN / 'baseline/rgb.png')
    dimensions = {}
    for name, record in records.items():
        image = read(RUN / name / 'rgb.png')
        dimensions[name] = dict(saved_image=[image.shape[1], image.shape[0]],
            render_product=record['projection']['render_product']['resolution'],
            camera=record['projection']['render_product']['camera'],
            matches=image.shape == (384, 512, 3) and record['projection']['render_product']['resolution'] == [512, 384]
                    and record['projection']['render_product']['camera'] == '/World/MarlinOceanIntegrationDiagnostic/Camera')
        assert dimensions[name]['matches']
    comparisons = {}
    visible_reference = read(RUN / 'baseline/hdr_display.png') if ATTEMPT == '03' else None
    for name in required[1:]:
        state = compare_state(baseline, records[name], same_settings)
        images = metrics(reference, read(RUN / name / 'rgb.png'))
        visible = metrics(visible_reference, read(RUN / name / 'hdr_display.png')) if ATTEMPT == '03' else None
        conversion = load(RUN / name / 'display_conversion.json') if ATTEMPT == '03' else None
        comparisons[name] = dict(state=state, display_image=images,
            fixed_hdr_display=visible,
            visible_display_informative=bool(conversion and conversion['nonconstant'] and conversion['fraction_of_rgb_values_at_255'] < .01),
            native_hdr=hdr_metrics(RUN / 'baseline/hdr.npz', RUN / name / 'hdr.npz'),
            passed=state['all_state_checks_passed'] and images['image_tolerance_passed']
                   and bool(visible and visible['image_tolerance_passed'])
                   and bool(conversion and conversion['nonconstant'] and conversion['fraction_of_rgb_values_at_255'] < .01))
    snapshot = load(RUN / 'snapshot.json')
    identifiers = [records[name]['layer_identifier'] for name in ('baseline', 'reload_a', 'reload_b')]
    reload_verified = len(set(identifiers)) == 3 and digest(RUN / 'saved_scene.usdc') == snapshot['sha256']
    for name in ('reload_a', 'reload_b'):
        reload_verified = reload_verified and records[name]['reload_input']['sha256'] == snapshot['sha256']
    mode_comparison = None
    if 'mode_comparison' in records:
        mode_comparison = dict(recorded_mode=records['mode_comparison']['mode'],
            state=compare_state(baseline, records['mode_comparison'], same_settings),
            display_image=metrics(reference, read(RUN / 'mode_comparison/rgb.png')),
            native_hdr=hdr_metrics(RUN / 'baseline/hdr.npz', RUN / 'mode_comparison/hdr.npz'),
            acceptance='No cross-mode identical-pixel requirement; state and control differences are reported explicitly')
    monitor = load(ROOT / 'qa/driver_recovery_2026_11_03' / ('post_reboot' if ATTEMPT == '01' else 'post_reboot_retry' + ATTEMPT) / 'monitor_result.json')
    result = dict(same_mode_comparisons=comparisons, dimensions_and_camera=dimensions,
        actual_fresh_layer_reloads_verified=reload_verified, reload_layer_identifiers=identifiers,
        saved_scene_sha256=snapshot['sha256'], comparator_source=comparator_source,
        mode_comparison=mode_comparison, resources=monitor,
        capture_times_seconds={name: record['elapsed_seconds'] for name, record in records.items()},
        actual_gpu_samples_measured=False, completed_rendered_frame_wait_per_image=64,
        all_same_mode_checks_passed=all(c['passed'] for c in comparisons.values()),
        above_water_m5_acceptance_passed=reload_verified and all(c['passed'] for c in comparisons.values()),
        underwater_camera_qualified=False, m4_complete=False)
    with (RUN / 'analysis.json').open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('all_same_mode_checks_passed', 'actual_fresh_layer_reloads_verified', 'above_water_m5_acceptance_passed')}, indent=2))
    for name, comparison in comparisons.items():
        print(name, 'state:', comparison['state']['checks'], 'images:', comparison['display_image']['comparisons'])
        if comparison['fixed_hdr_display']:
            print(name, 'visible HDR display:', comparison['fixed_hdr_display']['comparisons'])


if __name__ == '__main__':
    main()
