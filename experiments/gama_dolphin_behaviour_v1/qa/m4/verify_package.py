"""Read-only verification of the M4 candidate and retained local evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[4]
BASE = REPO / 'experiments/gama_dolphin_behaviour_v1'
QA = BASE / 'qa/m4'
FORBIDDEN = {'_build', 'extscache', '__pycache__', '.cache'}


def read(path):
    return json.loads(path.read_text())


def verify_records(records):
    for record in records:
        relative = Path(record['path'])
        assert not relative.is_absolute() and '..' not in relative.parts
        assert not FORBIDDEN.intersection(relative.parts) and relative.suffix != '.pyc'
        data = (REPO / relative).read_bytes()
        assert len(data) == record['bytes'], str(relative)
        assert hashlib.sha256(data).hexdigest() == record['sha256'], str(relative)
    return len(records)


def main(manifest_path):
    manifest = read(manifest_path)
    counts = {key: verify_records(manifest[key]) for key in (
        'files', 'source_pins', 'artifact_files', 'asset_dependencies',
        'checkpoint_artifacts', 'prior_package_manifests', 'completed_runtime_logs')}
    assert manifest['gate_c_at_seal'] == 'pending'
    assert not manifest['human_acceptance_received_at_seal']
    assert not manifest['milestone_4_accepted_at_seal']
    assert manifest['body_animation_implemented'] and not manifest['milestone_5_started']
    assert not manifest['biological_approval'] and not manifest['optical_approval']

    controller = (BASE / 'animation/m4_controller_v1.json').read_bytes()
    canonical = REPO / 'source/extensions/cris.madil.gama_bridge/config/animation_model61a_m4_v1.json'
    assert controller == canonical.read_bytes()
    locked = read(QA / 'locked_plan.json')
    assert hashlib.sha256(controller).hexdigest() == locked['controller_sha256']
    tolerance_bytes = (BASE / 'animation/m4_acceptance_v1.json').read_bytes()
    assert hashlib.sha256(tolerance_bytes).hexdigest() == locked['tolerance_sha256']
    for source, snapshot in manifest['implementation_snapshots'].items():
        assert (REPO / source).read_bytes() == (REPO / snapshot).read_bytes(), source

    cpu = read(QA / 'cpu_attempt05.json')
    assert cpu['passed'] and cpu['tests'] == 8 and not cpu['failures'] and not cpu['errors']
    assert cpu['tolerance_sha256'] == locked['tolerance_sha256']
    assert read(QA / 'static_v3_regressions.json')['passed']
    assert all(r['returncode'] == 0 for r in read(QA / 'pre_native_regressions.json'))
    live = read(QA / 'live_contract_attempt02/results.json')
    assert live['passed'] and len(live['checks']) == 341 and all(live['checks'].values())

    poses = read(QA / 'native_pose_comparison.json')
    assert poses['passed'] and poses['frames'] == 681
    assert poses['max_root_matrix_error'] == 0 and poses['max_phase_error_cycles'] == 0
    assert poses['max_weight_error'] == 0
    assert poses['max_joint_matrix_error'] <= 2e-6
    assert len(poses['skin_snapshot_comparisons']) == 6
    assert all(p['passed'] and p['vertices'] == 21504 and p['max_vertex_error_m'] == 0
               for p in poses['skin_snapshot_comparisons'])
    media = read(QA / 'native_media_analysis.json')
    assert media['passed'] and {c['job'] for c in media['candidates']} == {'dry02', 'review01'}
    for candidate in media['candidates']:
        assert candidate['passed'] and candidate['all_frames_nonflat']
        assert candidate['all_pose_joint_arrays_complete']
        assert candidate['clip_frames'] == 300 and candidate['clip_duration_s'] == 30
        assert candidate['clip_fps'] == 10
        movie = (REPO / candidate['movie']).read_bytes()
        assert hashlib.sha256(movie).hexdigest() == candidate['movie_sha256']
    assert sum(c['native_frames'] for c in media['candidates']) == poses['frames']

    final = read(QA / 'final_gui_checks.json')
    assert final['passed'] and all(final['checks'].values()) and final['normal_gui_restored']
    assert final['diagnostic_worker_removed']
    stage = read(QA / 'restored_gui_stage_comparison.json')
    assert stage['passed'] and stage['prims_before'] == stage['prims_after'] == 38
    assert not any(stage[k] for k in ('missing', 'extra', 'differences', 'unexpected'))
    historical = subprocess.run([sys.executable, '-B', str(QA / 'verify_historical_preservation.py')],
                                cwd=REPO, text=True, capture_output=True, check=True)
    assert json.loads(historical.stdout)['passed']
    return dict(passed=True, manifest=str(manifest_path.relative_to(REPO)), verified=counts,
                cpu_tests=8, live_checks=341, native_frames_compared=681,
                reopened_skin_snapshots=6, previous_evidence_preserved=True,
                exact_original_scene_restored=True, normal_gui_restored=True,
                gate_c_at_seal='pending', human_acceptance_claimed=False,
                milestone_5_started=False,
                limitations='Existing swim cycle; turn/descent/ascent lack bespoke local poses. '
                            'Geometric guards are sampled, and biological/optical approval is absent.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, default=BASE / 'm4_manifest.json')
    args = parser.parse_args()
    print(json.dumps(main(args.manifest.resolve()), indent=2))
