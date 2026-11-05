"""Continue from the successful first reference; execute fresh-process repeats."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

REPO=Path(__file__).resolve().parents[4]
ROOT=Path(__file__).resolve().parent
BASE=ROOT.parents[1]
sys.path.insert(0,str(REPO/'tools'))
import gama_bottlenose as runner


def load(run):return json.loads((BASE/'trajectories'/run/'execution.json').read_text())
def states(run):return json.loads((BASE/'trajectories'/run/'trajectory.json').read_text())


def main():
    output=ROOT/'campaign_execution.json'
    if output.exists():raise ValueError('Campaign report exists; preserve it')
    plan=json.loads((ROOT/'locked_plan.json').read_text());lock=ROOT/'implementation_lock_attempt01.json'
    assert plan['stochastic_seeds']==[1,42,184729] and plan['fresh_processes']==8
    first=load('m3_ref_a01');assert first['status']=='passed' and not first['variation']
    report=dict(status='started',started_utc=datetime.now(timezone.utc).isoformat(),
        orchestrator_sha256=runner.sha(Path(__file__)),plan_sha256=runner.sha(ROOT/'locked_plan.json'),
        implementation_lock_sha256=runner.sha(lock),reference_executed_before_variation=True,
        runs=[first],repeat_comparisons=[],marlin_mutation=False,biological_approval=False)
    logs=ROOT/'recorder_logs';logs.mkdir(exist_ok=False)
    jobs=[('m3_ref_b01',184729,False)]+[(f'm3_seed{seed}_{suffix}01',seed,True) for seed in (1,42,184729) for suffix in ('a','b')]
    try:
        for name,seed,var in jobs:
            cmd=['/usr/bin/python3','-B',str(REPO/'tools/gama_bottlenose.py'),'--run-id',name,'--seed',str(seed),'--lock',str(lock)]+(['--variation'] if var else [])
            with (logs/(name+'.log')).open('x') as log:
                p=subprocess.Popen(cmd,cwd=REPO,stdout=log,stderr=subprocess.STDOUT)
                try:code=p.wait(timeout=210)
                except subprocess.TimeoutExpired:p.kill();p.wait();raise RuntimeError('Recorder timeout: '+name)
            execution=load(name);report['runs'].append(execution)
            assert code==0 and execution['status']=='passed',(name,execution.get('error'))
            for key in ('model_sha256','configuration_sha256','acceptance_sha256','implementation_lock_sha256','launcher_sha256','runtime_configuration_sha256','runtime'):
                assert execution[key]==first[key],(name,key)
            if '_b01' in name:
                other='m3_ref_a01' if not var else name.replace('_b01','_a01')
                same=runner.canonical(states(name))==runner.canonical(states(other))
                choices=execution['realised_choices']==load(other)['realised_choices']
                comparison=dict(first=other,repeat=name,canonical_states_exact=same,choices_exact=choices,
                    different_launcher_processes=execution['launcher_process_id']!=load(other)['launcher_process_id'])
                report['repeat_comparisons'].append(comparison);assert all(comparison[k] for k in ('canonical_states_exact','choices_exact','different_launcher_processes'))
            print(json.dumps(dict(completed=len(report['runs']),total=8,run=name,status='passed')),flush=True)
        primaries=[load(f'm3_seed{s}_a01') for s in (1,42,184729)]
        report['actual_seed_variation']=len({json.dumps(r['realised_choices'],sort_keys=True) for r in primaries})==3 and len({r['canonical_state_sha256'] for r in primaries})==3
        assert report['actual_seed_variation']
        report['status']='passed'
    except BaseException as error:
        report.update(status='failed',error=type(error).__name__+': '+str(error));raise
    finally:
        report['finished_utc']=datetime.now(timezone.utc).isoformat();runner.write(output,report)


if __name__=='__main__':main()
