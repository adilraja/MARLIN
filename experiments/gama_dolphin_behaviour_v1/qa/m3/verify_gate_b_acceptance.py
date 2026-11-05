"""Verify MAR's subsequent Gate B decision without altering the M3 seal."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parents[1]
REPO=ROOT.parents[3]


def check(records):
    for item in records:
        path=Path(item['path'])
        assert not path.is_absolute() and '..' not in path.parts
        assert not set(path.parts)&{'_build','extscache','__pycache__','.cache'} and path.suffix!='.pyc'
        data=(REPO/path).read_bytes()
        assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256'],str(path)
    return len(records)


def main():
    acceptance=json.loads((BASE/'reviews/MAR_GATE_B_2026_11_05_acceptance_manifest.json').read_text())
    record=json.loads((BASE/'reviews/MAR_GATE_B_2026_11_05.json').read_text())
    files=check(acceptance['files']);bindings=check(record['bindings'])
    assert acceptance['status']==record['status']=='accepted'
    assert acceptance['reviewer']==record['reviewer']=='MAR'
    assert acceptance['technical_manifest_sha256']==hashlib.sha256((BASE/'m3_manifest.json').read_bytes()).hexdigest()
    assert record['response_verbatim']=='Accept Gate B as MAR' and record['acceptance_received']
    assert record['milestone_3_accepted'] and not record['biological_approval'] and not record['final_animation_visual_acceptance']
    assert not record['milestone_4_started_by_this_record']
    current=json.loads((BASE/'reviews/gate_b_review.json').read_text())
    assert current['status']=='accepted' and current['reviewer']=='MAR' and current['acceptance_received']
    assert current['acceptance_record']=='reviews/MAR_GATE_B_2026_11_05.json'
    assert current['acceptance_manifest']=='reviews/MAR_GATE_B_2026_11_05_acceptance_manifest.json'
    assert not current['biological_approval'] and not current['body_animation_started']
    previous=json.loads((BASE/'reviews/gate_b_review_before_acceptance_2026_11_05.json').read_text())
    assert previous['status']=='pending' and previous['reviewer'] is None and not previous['acceptance_received']
    technical=json.loads((BASE/'m3_manifest.json').read_text())
    assert technical['gate_b_at_seal']=='pending' and not technical['human_acceptance_received_at_seal']
    result=subprocess.run(['/usr/bin/python3','-B',str(ROOT/'verify_package.py')],capture_output=True,text=True,check=True)
    verification=json.loads(result.stdout)
    assert verification['gate_b']=='accepted' and verification['milestone_3_accepted']
    return dict(passed=True,gate='B',reviewer='MAR',status='accepted',
        acceptance_files_verified=files,reviewed_bindings_verified=bindings,
        original_technical_seal_preserved=True,milestone_3_complete=True,
        biological_approval=False,final_animation_visual_acceptance=False,
        milestone_4_started=False,technical_verification=verification)


if __name__=='__main__':print(json.dumps(main(),indent=2))
