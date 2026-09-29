"""Check the delivered M2 records against measured and live evidence (stdlib)."""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT = ROOT / 'experiments/gsd_pilot_v1'
WILDLIFE = EXPERIMENT / 'wildlife'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    measured = read(WILDLIFE / 'measurements.json')
    live = read(WILDLIFE / 'live_validation.json')
    preview = read(WILDLIFE / 'kit_review/preview.json')
    spec = read(EXPERIMENT / 'specification.json')
    previous = read(EXPERIMENT / 'history/milestone_1/specification.json')
    assert live['passed'] and live['original_dependencies_unchanged']
    assert spec['targets']['selected_bird'] == 'european_storm_petrel'
    assert spec['targets']['selected_cetacean'] == 'harbour_porpoise'
    for key in previous:
        if key not in {'schema_version', 'status', 'targets', 'outstanding_gates'}:
            assert spec[key] == previous[key], key
    assert spec['targets']['state_conditioned_sampling_ranges'] is None
    assert spec['targets']['selection_status'] == 'pilot_calibrated_with_explicit_provisional_fields'
    counts = {}
    for species, measurement in measured.items():
        record = read(WILDLIFE / (species + '.json'))
        assert record['physical_reference']['status'] == 'provisional'
        assert not record['biological_calibration_verified']
        assert record['physical_reference']['value_m'] == measurement['reference_measurement_m']
        assert record['geometry']['corrected_metric_bounds_relative_to_root'] == measurement['metric_world_bounds']
        for name, expected in [('scale', measurement['spawn_scale_for_centimetre_stage']),
                               ('model_rotation', measurement['correction_xyz_deg'])]:
            assert record['spawn'][name] == expected
            assert preview['animals'][species]['request'][name] == expected
        for dep in record['asset']['dependencies']:
            path = ROOT / dep['path']
            assert path.is_relative_to(ROOT / 'assets')
            assert sha(path) == dep['sha256'], dep['path']
        state = record['supported_states'][0]
        assert [state['id']] == spec['targets']['permitted_states'][species]
        y = state['review_root_y_m']
        expected_min_y = measurement['metric_world_bounds']['minimum'][1] + y
        expected_max_y = measurement['metric_world_bounds']['maximum'][1] + y
        observed = live['checks']['shallow']['animals'][species]
        assert observed['passed'] and observed['live_heading90_authored']
        assert abs(observed['world_bounds_m']['minimum'][1] - expected_min_y) < 1e-5
        assert abs(observed['world_bounds_m']['maximum'][1] - expected_max_y) < 1e-5
        for phase in ['dry', 'shallow']:
            item = live['checks'][phase]['animals'][species]
            assert item['max_point_error_m'] < record['verification']['geometry_tolerance_m']
            assert item['vertex_count'] == measurement['vertex_count']
            assert all(h['passed'] for h in item['heading_cases'])
        for path in record['verification']['images']:
            assert (WILDLIFE / path).is_file()
        counts[species] = {'vertices_per_checkpoint': measurement['vertex_count'], 'passed': True}
    history = read(EXPERIMENT / 'history/milestone_1/path_relocations.json')['path_relocations']
    m1 = read(EXPERIMENT / 'qa/milestone_1_manifest.json')
    for output in m1['outputs']:
        path = history.get(output['path'], output['path'])
        assert sha(EXPERIMENT / path) == output['sha256'], path
    inputs = read(EXPERIMENT / 'qa/input_provenance.json')['files']
    for entry in inputs:
        path = Path(entry['path'])
        assert not any(part in {'_build', 'extscache', '__pycache__', '.cache'} for part in path.parts)
        assert sha(ROOT / path) == entry['sha256'], str(path)
    scripts = list(WILDLIFE.glob('*.py')) + [Path(__file__)]
    for path in scripts:
        ast.parse(path.read_text(), filename=str(path))
    result = {'passed': True, 'scope': 'Delivery consistency and preservation; live USD verification is separately recorded',
              'targets': counts, 'm1_outputs_preserved': len(m1['outputs']),
              'baseline_input_hashes_unchanged': len(inputs), 'scripts_parsed': len(scripts),
              'experimental_camera_gsd_dataset_and_ml_protocol_unchanged': True,
              'biological_and_optical_validation': False}
    (EXPERIMENT / 'qa/milestone_2_validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
