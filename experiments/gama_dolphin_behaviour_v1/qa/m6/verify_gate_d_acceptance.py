"""Verify MAR's final decision and retained technical seal without scene writes."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parents[1]
REPO=ROOT.parents[3]


def load(path):return json.loads(path.read_text())


def check(records):
    for record in records:
        path=Path(record['path'])
        assert not path.is_absolute() and '..' not in path.parts
        assert not set(path.parts)&{'_build','extscache','__pycache__','.cache'} and path.suffix!='.pyc'
        data=(REPO/path).read_bytes()
        assert len(data)==record['bytes'] and hashlib.sha256(data).hexdigest()==record['sha256'],str(path)
    return len(records)


def main():
    manifest=load(BASE/'reviews/MAR_GATE_D_2026_11_05_acceptance_manifest.json')
    decision=load(BASE/'reviews/MAR_GATE_D_2026_11_05.json')
    count=check(manifest['files']);bindings=check(decision['bindings'])
    assert manifest['gate']==decision['gate']=='D'
    assert manifest['status']==decision['status']=='accepted'
    assert manifest['reviewer']==decision['reviewer']=='MAR'
    assert manifest['evidence_version']==decision['evidence_version']=='bottlenose_engineering_demo_v1'
    assert decision['response_verbatim']=='Accept Gate D as MAR' and decision['acceptance_received']
    assert decision['milestone_6_complete'] and decision['sprint_closed']
    assert decision['bounded_engineering_visual_acceptance']
    assert not decision['biological_approval'] and not decision['optical_approval'] and not decision['research_capture_approval']
    technical=BASE/'m6_manifest.json'
    technical_sha=hashlib.sha256(technical.read_bytes()).hexdigest()
    assert manifest['technical_manifest_sha256']==decision['technical_manifest_sha256']==technical_sha
    old_path=BASE/'reviews/gate_d_review_before_acceptance_2026_11_05.json'
    old=load(old_path)
    assert old['status']=='pending' and old['reviewer'] is None and not old['accepted']
    assert hashlib.sha256(old_path.read_bytes()).hexdigest()==decision['superseded_review_state_sha256']
    sealed=load(technical)
    assert sealed['gate_d_at_seal']=='pending' and not sealed['human_acceptance_received_at_seal']
    assert not sealed['milestone_6_complete_at_seal'] and not sealed['sprint_closed_at_seal']
    current=load(BASE/'reviews/gate_d_review.json')
    assert current['status']=='accepted' and current['reviewer']=='MAR' and current['accepted']
    assert current['milestone_6_complete'] and current['sprint_closed']
    assert current['acceptance_record']=='reviews/MAR_GATE_D_2026_11_05.json'
    assert current['acceptance_manifest']=='reviews/MAR_GATE_D_2026_11_05_acceptance_manifest.json'
    assessments=load(BASE/'reviews/gate_d_assessments.json')
    assert assessments['engineering']['status']==assessments['visual']['status']=='passed'
    assert assessments['visual']['reviewer']=='MAR'
    assert assessments['biological']['status']=='provisional' and not assessments['biological']['expert_review_received']
    assert not assessments['research_capture']['approved']
    assert assessments['next_use']['decision']=='accepted_for_bounded_engineering_visual_demonstrations'
    status=load(BASE/'SPRINT_STATUS.json')
    assert status['sprint_closed'] and status['gate_d']=='accepted'
    assert all(item['status']=='complete' for item in status['milestones'].values())
    assert len(status['milestones'])==6
    assert status['separate_ocean_material_underwater_camera_issue']=='open'
    result=subprocess.run([sys.executable,'-B',str(ROOT/'verify_package.py')],cwd=REPO,
        capture_output=True,text=True,check=True)
    verification=json.loads(result.stdout)
    assert verification['passed'] and verification['gate_d']=='accepted' and verification['sprint_closed']
    return dict(passed=True,gate='D',reviewer='MAR',status='accepted',
        acceptance_files_verified=count,reviewed_bindings_verified=bindings,
        original_technical_seal_preserved=True,milestone_6_complete=True,sprint_closed=True,
        bounded_engineering_visual_acceptance=True,biological_support='provisional',
        biological_approval=False,optical_approval=False,research_capture_approval=False,
        new_dataset_ml_or_species_work_started=False,separate_ocean_material_issue='open',
        technical_verification=verification)


if __name__=='__main__':print(json.dumps(main(),indent=2))
