"""Read-only verification of MAR's Gate B acceptance and its original evidence."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[4]
BASE = REPO/'experiments/above_water_annotation_v1'


def read(relative): return json.loads((BASE/relative).read_text())


def check(rows):
    for row in rows:
        p = Path(row['path'])
        assert not p.is_absolute() and '..' not in p.parts
        assert not set(p.parts)&{'_build', 'extscache', '.cache', '__pycache__'} and p.suffix != '.pyc'
        data = (REPO/p).read_bytes()
        assert len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256'], p
    return len(rows)


def main():
    decision = read('reviews/MAR_GATE_B_2026_11_10.json')
    seal = read('reviews/MAR_GATE_B_2026_11_10_acceptance_manifest.json')
    count = check(seal['files']); bindings = check(decision['bindings'])
    assert decision['gate'] == seal['gate'] == 'B'
    assert decision['status'] == seal['status'] == 'accepted'
    assert decision['reviewer'] == seal['reviewer'] == 'MAR'
    assert decision['candidate_id'] == seal['candidate_id'] == 'above_water_m2_dry_validation_v2'
    assert decision['accepted'] and decision['acceptance_received'] and decision['milestone_2_complete']
    assert decision['response_verbatim'] == 'Accept Gate B as MAR'
    assert decision['decision_date'] == '2026-11-10'
    digest = hashlib.sha256((BASE/'diagnostics/m2_execution_v1/revision_v2/manifest.json').read_bytes()).hexdigest()
    assert digest == decision['technical_manifest_sha256'] == seal['technical_manifest_sha256']
    prior = read('reviews/gate_b_review_v2.json')
    assert prior['status'] == 'pending' and not prior['accepted'] and prior['reviewer'] is None
    current = read('reviews/gate_b_acceptance_state.json')
    assert current['accepted'] and current['status'] == 'accepted' and current['reviewer'] == 'MAR'
    assert current['candidate_id'] == decision['candidate_id'] and current['milestone_2_complete']
    assert current['acceptance_record'] == 'reviews/MAR_GATE_B_2026_11_10.json'
    snapshot = read('reviews/gate_b_progress_at_acceptance_2026_11_10.json')
    assert snapshot['milestone_2_complete'] and snapshot['gate_b'] == 'accepted'
    assert snapshot['milestone_3'] == 'not_started' and not snapshot['sprint_closed']
    for key in ('milestone_3_started_by_this_record', 'marine_labels_qualified', 'standard_instance_API_qualified',
                'geometry_empty_products_supported', 'per_AOV_frame_ID_guarantee', 'biological_approval',
                'optical_approval', 'research_capture_approval', 'ml_training_approval', 'sprint_closed'):
        assert decision[key] is False, key
    assert decision['separate_ocean_material_m4'] == 'open'
    progress = read('CURRENT_PROGRESS.json')
    assert progress['milestone_2_complete'] and progress['gate_b'] == 'accepted'
    assert progress['gate_b_reviewer'] == 'MAR'
    assert progress['gate_b_acceptance_record'] == 'reviews/MAR_GATE_B_2026_11_10.json'
    run = subprocess.run([sys.executable, '-B', str(BASE/'qa/m2_execution_v1/verify_execution_v2.py')],
                         cwd=REPO, capture_output=True, text=True, timeout=60, check=True)
    technical = json.loads(run.stdout)
    assert technical['passed'] and technical['dry_rows_passed'] == 16
    return dict(passed=True, gate='B', status='accepted', reviewer='MAR',
                candidate_id=decision['candidate_id'], milestone_2_complete=True,
                acceptance_files_verified=count, reviewed_bindings_verified=bindings,
                original_pending_packet_preserved=True, dry_rows_passed=16,
                total_attempts=24, reserve_remaining=16, gate_b_prerequisite_for_M3_satisfied=True,
                milestone_3_started_by_this_record=False, marine_labels_qualified=False,
                biological_approval=False, optical_approval=False, research_capture_approval=False,
                main_MARLIN_installation_changed=False, separate_ocean_material_m4='open', sprint_closed=False,
                technical_snapshot_pre_review=technical)


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
