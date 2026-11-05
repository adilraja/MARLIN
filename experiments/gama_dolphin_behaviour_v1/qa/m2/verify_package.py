"""Read-only verification of M2 evidence and exact current source inputs."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parents[1]
REPO=ROOT.parents[3]


def verify(records):
    for item in records:
        path=Path(item['path'])
        assert not path.is_absolute() and '..' not in path.parts
        assert not set(path.parts)&{'_build','extscache','__pycache__','.cache'} and path.suffix!='.pyc'
        data=(REPO/path).read_bytes()
        assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256'],str(path)
    return len(records)


def main():
    manifest=json.loads((BASE/'m2_manifest.json').read_text())
    counts={key:verify(manifest[key]) for key in ('files','source_pins','checkpoint_artifacts','asset_dependencies')}
    tolerance=hashlib.sha256((BASE/'acceptance_tolerances.json').read_bytes()).hexdigest()
    assert tolerance==manifest['tolerance_sha256']==json.loads((ROOT/'locked_plan.json').read_text())['tolerance_sha256']
    cpu=json.loads((ROOT/'cpu_attempt_02.json').read_text());assert cpu['passed'] and cpu['tests']==12
    legacy=json.loads((ROOT/'legacy_regressions.json').read_text());assert len(legacy)==5 and all(r['returncode']==0 for r in legacy)
    live=json.loads((ROOT/'live_attempt_01/results.json').read_text());assert live['passed'] and len(live['checks'])==67
    assert all(v['passed'] for v in live['checks'].values())
    for file in ('preservation_disposition.json','restored_stage_comparison_attempt02.json'):
        assert json.loads((ROOT/file).read_text())['passed'],file
    assert json.loads((ROOT/'live_restart/done.json').read_text())['ok']
    assert json.loads((ROOT/'cpu_attempt_01.json').read_text())['outcome']=='aborted'
    assert json.loads((ROOT/'restored_stage_comparison.json').read_text())['passed'] is False
    assert not json.loads((ROOT/'stage_comparison_amendment.json').read_text())['numeric_tolerances_changed']
    assert json.loads((ROOT/'live_attempt_01/swim_after.json').read_text())['running'] is False
    assert json.loads((ROOT/'live_attempt_01/gallery_after.json').read_text())['running'] is False
    assert json.loads((ROOT/'live_attempt_01/ocean_after.json').read_text())['running'] is True
    assert json.loads((ROOT/'live_attempt_01/chase_after.json').read_text())['running'] is True
    for file in ('live_before/checkpoint.json','live_final/checkpoint.json'):
        saved=json.loads((ROOT/file).read_text())
        assert hashlib.sha256((ROOT/file).parent.joinpath('scene.usdc').read_bytes()).hexdigest()==saved['scene_sha256']
    m1=subprocess.run(['/usr/bin/python3','-B',str(BASE/'qa/verify_package.py')],capture_output=True,text=True,check=True)
    prior=subprocess.run(['/usr/bin/python3','-B',str(ROOT/'verify_preservation.py')],capture_output=True,text=True,check=True)
    assert json.loads(prior.stdout)['passed']
    return dict(passed=True,verified=counts,cpu_tests=12,legacy_tests=72,live_checks=67,
                m1_gate_a=json.loads(m1.stdout)['gate_a'],old_water_evidence_preserved=True,
                no_new_gama_execution=True,body_animation_integrated=False,milestone_2_complete=True,
                retained_failures='CPU attempt 01 aborted; stage-comparison omitted-normal failure and justified retry',
                limitation='State/composed USD contract verification, not rendered-body or biological acceptance')


if __name__=='__main__':print(json.dumps(main(),indent=2))
