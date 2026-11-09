"""Verify MAR's Gate A acceptance without changing the sealed audit or runtime."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[4]
BASE = REPO / 'experiments/above_water_annotation_v1'


def read(relative):
    return json.loads((BASE / relative).read_text())


def check(records):
    for record in records:
        path = Path(record['path'])
        assert not path.is_absolute() and '..' not in path.parts
        assert not set(path.parts) & {'_build', 'extscache', '__pycache__', '.cache'}
        assert path.suffix != '.pyc'
        data = (REPO / path).read_bytes()
        assert len(data) == record['bytes'], str(path)
        assert hashlib.sha256(data).hexdigest() == record['sha256'], str(path)
    return len(records)


def main():
    decision = read('reviews/MAR_GATE_A_2026_11_09.json')
    manifest = read('reviews/MAR_GATE_A_2026_11_09_acceptance_manifest.json')
    files = check(manifest['files'])
    bindings = check(decision['bindings'])
    technical_sha = hashlib.sha256((BASE/'manifest.json').read_bytes()).hexdigest()
    assert technical_sha == decision['technical_manifest_sha256'] == manifest['technical_manifest_sha256']
    assert decision['gate'] == manifest['gate'] == 'A'
    assert decision['status'] == manifest['status'] == 'accepted'
    assert decision['reviewer'] == manifest['reviewer'] == 'MAR'
    assert decision['evidence_version'] == manifest['evidence_version'] == 'above_water_m1_audit_v1'
    assert decision['response_verbatim'] == 'Accept Gate A as MAR'
    assert decision['accepted'] and decision['acceptance_received'] and decision['milestone_1_complete']
    assert not decision['milestone_2_started_by_this_record']
    assert not decision['new_dependency_installation_authorised']
    assert not decision['main_runtime_upgrade_authorised']
    assert decision['stop_before_any_required_new_dependency_installation']
    assert len(decision['retained_limitations']) == 4
    for key in ['biological_approval', 'optical_approval', 'research_capture_approval', 'ml_training_approval']:
        assert decision[key] is False
    technical = read('manifest.json')
    assert technical['gate_a_at_seal'] == 'pending'
    assert not technical['human_acceptance_received_at_seal']
    previous = read('reviews/gate_a_review_at_seal.json')
    assert previous['status'] == 'pending' and previous['reviewer'] is None and not previous['accepted']
    current = read('reviews/gate_a_review.json')
    assert current['status'] == 'accepted' and current['reviewer'] == 'MAR'
    assert current['accepted'] and current['acceptance_received']
    assert current['acceptance_record'] == 'reviews/MAR_GATE_A_2026_11_09.json'
    status = read('SPRINT_STATUS.json')
    assert status['milestones']['M1'] == 'complete'
    assert all(status['milestones'][key] == 'not_started' for key in ['M2','M3','M4','M5','M6'])
    assert status['gate_a'] == 'accepted' and status['reviewer'] == 'MAR'
    assert status['gate_a_accepted'] and status['m1_technical_audit_complete']
    assert not status['sprint_closed'] and not status['implementation_started']
    assert status['separate_ocean_material_m4'] == 'open'
    run = subprocess.run([sys.executable, '-B', str(BASE/'qa/m1/verify_audit.py')],
                         cwd=REPO, capture_output=True, text=True, check=True)
    audit = json.loads(run.stdout)
    assert audit['passed'] and audit['gate_a'] == 'accepted' and audit['reviewer'] == 'MAR'
    return dict(passed=True, gate='A', status='accepted', reviewer='MAR', milestone_1_complete=True,
                acceptance_files_verified=files, reviewed_bindings_verified=bindings,
                technical_manifest_sha256=technical_sha, original_pending_seal_preserved=True,
                implementation_started=False, milestone_2_started=False,
                new_dependency_installation_authorised=False, main_runtime_upgrade_authorised=False,
                stop_before_any_required_new_dependency_installation=True,
                biological_approval=False, optical_approval=False, research_capture_approval=False,
                separate_ocean_material_m4='open', audit_verification=audit)


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
