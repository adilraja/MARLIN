"""Verify sealed M3 inputs, actual raw GAMA outputs and pending/named review."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parents[1]
REPO=ROOT.parents[3]
sys.path.insert(0,str(REPO/'tools'))
import gama_bottlenose as recorder
from analyze_gama_bottlenose import analyze


def verify(records):
    for item in records:
        p=Path(item['path'])
        assert not p.is_absolute() and '..' not in p.parts
        assert not set(p.parts)&{'_build','extscache','__pycache__','.cache'} and p.suffix!='.pyc'
        b=(REPO/p).read_bytes()
        assert len(b)==item['bytes'] and hashlib.sha256(b).hexdigest()==item['sha256'],str(p)
    return len(records)


def main():
    manifest=json.loads((BASE/'m3_manifest.json').read_text())
    counts={k:verify(manifest[k]) for k in ('files','source_pins','prior_package_manifests')}
    allowed_runtime={'/opt/gama-platform/headless/gama-headless.sh','/opt/gama-platform/configuration/config.ini','/opt/gama-platform/jdk/bin/java'}
    for item in manifest['runtime_inputs']:
        assert item['absolute_path'] in allowed_runtime
        data=Path(item['absolute_path']).read_bytes()
        assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256']
    counts['runtime_inputs']=len(manifest['runtime_inputs'])
    plan=json.loads((ROOT/'locked_plan.json').read_text());config=json.loads(recorder.CONFIG.read_text());tol=json.loads(recorder.ACCEPTANCE.read_text())
    assert recorder.sha(recorder.CONFIG)==plan['parameter_sha256']
    assert recorder.sha(recorder.ACCEPTANCE)==plan['acceptance_sha256']
    assert recorder.sha(BASE/'acceptance_tolerances.json')==tol['m2_tolerance_sha256']
    campaign=json.loads((ROOT/'campaign_execution.json').read_text());summary=json.loads((ROOT/'campaign_analysis.json').read_text())
    assert campaign['status']=='passed' and len(campaign['runs'])==8 and campaign['actual_seed_variation']
    assert summary['passed'] and summary['total_samples']==2376
    config,count=recorder.load_config();assert count==297
    ids=set();processes=set();all_states={}
    for e in campaign['runs']:
        run=e['run_id'];assert run not in ids;ids.add(run);processes.add(e['launcher_process_id'])
        directory=BASE/'trajectories'/run
        assert e==json.loads((directory/'execution.json').read_text())
        assert e['status']=='passed' and not e['marlin_http_used'] and not e['scene_mutated']
        assert recorder.sha(directory/'model.gaml')==e['model_sha256']==recorder.sha(recorder.MODEL)
        assert recorder.sha(directory/'parameters.json')==e['configuration_sha256']==recorder.sha(recorder.CONFIG)
        assert recorder.sha(directory/'acceptance.json')==e['acceptance_sha256']==recorder.sha(recorder.ACCEPTANCE)
        assert recorder.sha(directory/'experiment.xml')==e['experiment_plan_sha256']
        assert recorder.sha(directory/'raw/simulation-outputs0.xml')==e['raw_xml_sha256']
        assert recorder.sha(directory/'trajectory.json')==e['trajectory_sha256']
        states,diagnostics=recorder.read_trajectory(directory/'raw/simulation-outputs0.xml',run,e['actual_seed'],e['variation'],config)
        assert states==json.loads((directory/'trajectory.json').read_text())
        assert diagnostics==json.loads((directory/'diagnostics.json').read_text())
        assert all(s['model_version']==config['version'] and s['agents'][0]['agent_id']=='Bottlenose_001' for s in states)
        assert hashlib.sha256(recorder.canonical(states)).hexdigest()==e['canonical_state_sha256']
        result=analyze(states,diagnostics,config,tol,e['variation'])
        assert result==json.loads((directory/'analysis.json').read_text()) and result['passed']
        all_states[run]=states
    assert len(processes)==8
    assert [e['variation'] for e in campaign['runs']]==[False,False,True,True,True,True,True,True]
    first_seeded=min(e['started_utc'] for e in campaign['runs'] if e['variation'])
    assert max(e['finished_utc'] for e in campaign['runs'] if not e['variation'])<first_seeded
    for pair in summary['repeatability']:
        assert recorder.canonical(all_states[pair['first']])==recorder.canonical(all_states[pair['repeat']])
        assert all(v==0 for v in pair['max_discrepancies'].values())
    assert len(summary['repeatability'])==4
    assert json.loads((ROOT/'acceptance_tests_attempt02.json').read_text())['passed']
    assert json.loads((ROOT/'acceptance_tests_attempt02.json').read_text())['tests']==9
    assert json.loads((ROOT/'acceptance_tests_attempt01.json').read_text())['passed'] is False
    assert not json.loads((ROOT/'acceptance_test_amendment.json').read_text())['numeric_tolerances_changed']
    assert json.loads((ROOT/'live_preservation.json').read_text())['passed']
    review=json.loads((BASE/'reviews/gate_b_review.json').read_text())
    assert review['status'] in ('pending','accepted','changes_requested','rejected')
    if review['status']=='pending':assert review['reviewer'] is None and not review['acceptance_received']
    elif review['status']=='accepted':
        assert review['reviewer'] and review['acceptance_received'] and (BASE/review['acceptance_record']).is_file()
    for script in (BASE/'qa/verify_package.py',BASE/'qa/m2/verify_package.py'):
        subprocess.run(['/usr/bin/python3','-B',str(script)],capture_output=True,text=True,check=True)
    return dict(passed=True,verified=counts,actual_gama_executions=8,samples=2376,fresh_process_repeat_pairs=4,
                exact_canonical_repeats=True,distinct_stochastic_choices=True,acceptance_tests=9,
                previous_test_failure_retained=True,marlin_preserved=True,m1_m2_preserved=True,
                gate_b=review['status'],milestone_3_accepted=review['status']=='accepted',body_animation_started=False,biological_approval=False)


if __name__=='__main__':print(json.dumps(main(),indent=2))
