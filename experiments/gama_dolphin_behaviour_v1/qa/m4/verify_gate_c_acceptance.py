"""Verify MAR's Gate C decision without rewriting the sealed M4 candidate."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[4]
BASE = REPO / 'experiments/gama_dolphin_behaviour_v1'
QA = BASE / 'qa/m4'


def read(path):
    return json.loads(path.read_text())


def check(records):
    for item in records:
        relative = Path(item['path'])
        assert not relative.is_absolute() and '..' not in relative.parts
        assert not set(relative.parts) & {'_build', 'extscache', '__pycache__', '.cache'}
        assert relative.suffix != '.pyc'
        data = (REPO / relative).read_bytes()
        assert len(data) == item['bytes'], str(relative)
        assert hashlib.sha256(data).hexdigest() == item['sha256'], str(relative)
    return len(records)


def main():
    acceptance = read(BASE / 'reviews/MAR_GATE_C_2026_11_05_acceptance_manifest.json')
    record = read(BASE / 'reviews/MAR_GATE_C_2026_11_05.json')
    files, bindings = check(acceptance['files']), check(record['bindings'])
    assert acceptance['gate'] == record['gate'] == 'C'
    assert acceptance['reviewer'] == record['reviewer'] == 'MAR'
    assert acceptance['status'] == record['status'] == 'accepted'
    assert record['response_verbatim'] == 'Accept Gate C as MAR'
    assert record['acceptance_received'] and record['milestone_4_accepted']
    assert record['bounded_animation_visual_acceptance']
    for key in ('biological_approval', 'optical_approval', 'final_sprint_acceptance', 'milestone_5_started_by_this_record'):
        assert record[key] is False
    technical_hash = hashlib.sha256((BASE / 'm4_manifest.json').read_bytes()).hexdigest()
    assert acceptance['technical_manifest_sha256'] == technical_hash
    assert record['technical_manifest_sha256'] == technical_hash

    previous_path = BASE / 'reviews/gate_c_review_before_acceptance_2026_11_05.json'
    previous = read(previous_path)
    assert previous['status'] == 'pending' and previous['reviewer'] is None and not previous['accepted']
    assert hashlib.sha256(previous_path.read_bytes()).hexdigest() == record['superseded_review_state_sha256']
    current = read(BASE / 'reviews/gate_c_review.json')
    assert current['status'] == 'accepted' and current['reviewer'] == 'MAR'
    assert current['accepted'] and current['acceptance_received'] and current['milestone_4_accepted']
    assert current['acceptance_record'] == 'reviews/MAR_GATE_C_2026_11_05.json'
    assert current['acceptance_manifest'] == 'reviews/MAR_GATE_C_2026_11_05_acceptance_manifest.json'
    assert current['manifest']['sha256'] == technical_hash
    assert not current['biological_approval'] and not current['optical_approval']
    assert not current['milestone_5_started']

    # The technical seal and packet retain the true pre-review state. This
    # subsequent, separately sealed decision supplies the current gate status.
    technical = read(BASE / 'm4_manifest.json')
    assert technical['gate_c_at_seal'] == 'pending'
    assert not technical['human_acceptance_received_at_seal']
    result = subprocess.run([sys.executable, '-B', str(QA / 'verify_package.py')],
                            cwd=REPO, text=True, capture_output=True, check=True)
    verification = json.loads(result.stdout)
    assert verification['passed']
    return dict(passed=True, gate='C', reviewer='MAR', status='accepted',
                acceptance_files_verified=files, reviewed_bindings_verified=bindings,
                original_technical_seal_preserved=True, milestone_4_complete=True,
                bounded_animation_visual_acceptance=True, biological_approval=False,
                optical_approval=False, final_sprint_acceptance=False,
                milestone_5_started=False, technical_verification=verification)


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
