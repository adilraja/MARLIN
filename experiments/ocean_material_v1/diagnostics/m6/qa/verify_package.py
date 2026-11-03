"""Verify immutable M6 technical evidence, the preset and preserved prior work."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[3]
BASE=REPO/'experiments/ocean_material_v1'


def check(records):
    for item in records:
        path=REPO/item['path']
        assert not set(path.parts)&{'_build','extscache','__pycache__','.cache'} and path.suffix!='.pyc'
        data=path.read_bytes()
        assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256'],str(path)
    return len(records)


def main():
    manifest=json.loads((ROOT/'manifest.json').read_text())
    counts={key:check(manifest[key]) for key in ('files','source_pins','checkpoint_artifacts')}
    preset=json.loads((BASE/'presets/engineering_v1/manifest.json').read_text())
    counts['preset_files']=check(preset['files'])
    counts['local_asset_dependencies']=check(preset['local_asset_dependencies'])
    driver=json.loads((ROOT.parent/'m4_driver_5959902/manifest.json').read_text())
    counts['driver_retest_files']=check(driver['files'])
    counts['retest_source_inputs']=check(driver['source_inputs'])
    previous=subprocess.run(['/usr/bin/python3','-B',str(ROOT.parent/'m5/qa/verify_package.py')],capture_output=True,text=True,check=True)
    result=json.loads((ROOT/'analysis.json').read_text())
    assert result['all_pair_invariants_passed'] and result['all_reload_rollback_checks_passed']
    final=json.loads((ROOT/'qa/final_live_verification.json').read_text())
    assert all(final['checks'].values())
    live=json.loads((ROOT/'qa/live_animation/verification.json').read_text())
    assert live['actual_live_updates']==10 and live['phase_advanced']
    retest=json.loads((ROOT.parent/'m4_driver_5959902/analysis.json').read_text())
    assert retest['valid_capture_run'] and retest['above_water_target_positive_control_passed']
    assert retest['initial_inside_optical_checks_passed'] is False
    review=json.loads((ROOT/'review_state.json').read_text())
    assert review['reviewer']=='MAR' and review['status'] in ('pending','accepted','changes_requested')
    if review['status']=='pending':
        assert review['acceptance_received'] is False
    print(json.dumps(dict(verified=counts,prior_m5_and_historical=json.loads(previous.stdout)['verified'],
          technical_checks_passed=True,human_review=review['status'],m4_complete=False,full_sprint_complete=False),indent=2))


if __name__=='__main__':
    main()
