"""Live opt-in animation ownership using actual accepted M3 states."""
from copy import deepcopy
import json
import argparse
from pathlib import Path
import time
import traceback
import urllib.request

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parents[1]


def main(name):
    if not name.replace('_','').isalnum():raise ValueError('Safe output name required')
    output=ROOT/name;output.mkdir(exist_ok=False)
    calls=[];checks={};token=None
    def api(path,payload=None):
        req=urllib.request.Request('http://localhost:8011'+path,data=None if payload is None else json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=40) as r:v=json.load(r)
        calls.append(dict(path=path,payload=payload,response=v));return v
    def check(name,ok):checks[name]=bool(ok);assert ok,name
    def command(name,**kwargs):return api('/integration/gama/v3/animated_actor/'+name,dict(ownership_token=token,**kwargs))
    def status():return api('/integration/gama/v3/animated_actor/status')
    def held(s):return {k:s[k] for k in ('composed_matrix','composed_joint_attributes','expected_joint_attributes','frame','pose_controls','accepted_steps','latest')}
    try:
        check('initially_unowned',not status()['owned'])
        result=api('/integration/gama/v3/animated_actor/acquire',dict(agent_id='Bottlenose_001'));check('acquire',result['ok']);token=result['ownership_token']
        states=json.loads((BASE/'trajectories/m3_ref_a01/trajectory.json').read_text())
        signature=status()['body_fingerprint'];pose_hashes=set()
        for index,state in enumerate(states):
            result=command('step',step=state);check('actual_M3_step_'+str(index),result['ok'])
            if index in (0,16,24,64,120,168,224,280,296):
                s=status();check('body_immutable_'+str(index),s['body_fingerprint']==signature)
                check('composed_pose_guard_'+str(index),s['guard_error'] is None and s['composed_joint_attributes']==s['expected_joint_attributes'])
                pose_hashes.add(json.dumps(s['composed_joint_attributes'],sort_keys=True))
            if index==25:
                records={}
                for t in (6.,6.125,6.25):
                    result=command('evaluate',simulation_time_s=t)
                    check('evaluate_'+str(t),result['ok'] and result['frame']['body_pose_mapping']=='existing_baked_cycle_m4_v1' and result['frame']['body_animation_evaluated'])
                    records[t]=held(status())
                for t in (6.25,6.,6.125):
                    command('evaluate',simulation_time_s=t);check('query_order_'+str(t),held(status())==records[t])
                s=held(status());check('pause',command('pause',paused=True)['ok'])
                check('paused_evaluate_rejected',not command('evaluate',simulation_time_s=6.)['ok'])
                time.sleep(2.1);check('pause_holds_root_joints_phase',held(status())==s)
                check('resume',command('pause',paused=False)['ok']);check('resume_no_jump',held(status())==s)
                check('stale_rejected',not command('step',step=states[0])['ok']);check('rejected_pose_held',held(status())==s)
        s=status();check('zero_speed_rest_weight',s['pose_controls']['weight']==0)
        check('local_body_tracks_varied',len(pose_hashes)>3)
        check('no_timeline_or_subscription',not s['timeline_driven'] and s['update_subscription_count']==0 and not s['autonomous_controller'])
        check('static_v3_competing_acquire_refused',not api('/integration/gama/v3/actor/acquire',dict(agent_id='Other'))['ok'])
        before=held(s);check('reset',command('reset')['ok']);after=status()
        check('reset_holds_root_joints_phase',all(after[k]==before[k] for k in ('composed_matrix','composed_joint_attributes','frame','pose_controls')))
        check('reset_new_run_step',command('step',step=states[0])['ok'])
        check('release',command('release')['ok']);token=None
        check('ends_unowned',not status()['owned'])
        check('legacy_v1_unowned',not api('/integration/gama/actor/status')['owned'])
        check('legacy_v2_unowned',not api('/integration/gama/v2/actor/status')['owned'])
    except BaseException:
        (output/'failure.txt').write_text(traceback.format_exc());raise
    finally:
        if token:checks['finally_release']=command('release')['ok']
        (output/'http_calls.json').write_text(json.dumps(calls,indent=2)+'\n')
        (output/'results.json').write_text(json.dumps(dict(passed=bool(checks) and all(checks.values()) and not (output/'failure.txt').exists(),checks=checks,scope='297 actual accepted M3 states applied to composed live USD skeleton; no rendered-image acceptance inferred'),indent=2)+'\n')
    print(json.dumps(dict(passed=True,checks=len(checks))))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--name',default='live_contract_attempt01');main(parser.parse_args().name)
