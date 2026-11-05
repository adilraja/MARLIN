"""Host HTTP acceptance; isolated actor is always released in finally."""
from copy import deepcopy
import datetime
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import traceback
import urllib.request

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parents[1]
T=json.loads((BASE/'acceptance_tolerances.json').read_text())
assert hashlib.sha256((BASE/'acceptance_tolerances.json').read_bytes()).hexdigest()==json.loads((ROOT/'locked_plan.json').read_text())['tolerance_sha256']


def run(output):
    output.mkdir(exist_ok=False)
    calls=[]; checks={}; token=None

    def request(path,payload=None):
        req=urllib.request.Request('http://localhost:8011'+path,
            data=None if payload is None else json.dumps(payload,allow_nan=False).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=40) as response:result=json.load(response)
        calls.append(dict(path=path,payload=payload,response=result,utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
        return result

    def check(name,condition,actual=None):
        checks[name]=dict(passed=bool(condition),actual=actual)
        assert condition,(name,actual)

    def status():return request('/integration/gama/v3/actor/status')
    def command(name,**kwargs):return request('/integration/gama/v3/actor/'+name,dict(ownership_token=token,**kwargs))
    def manual(i=0,**changes):
        s=json.loads((BASE/'fixtures/m2/valid_step_0.json').read_text())
        s.update(step_index=i,simulation_time_s=float(i));s['agents'][0].update(changes)
        return s
    def invariant(s):
        return {k:s[k] for k in ('world_pose','composed_matrix','body_fingerprint','frame','accepted_steps','latest')}

    try:
        restart=json.loads((ROOT/'live_restart/done.json').read_text())
        check('checkpoint_restored_before_testing',restart['ok'],restart)
        schema=request('/openapi.json');(output/'openapi.json').write_text(json.dumps(schema,indent=2)+'\n')
        check('v1_v2_preserved_and_v3_present',all(p in schema['paths'] for p in
            ('/integration/gama/actor/step','/integration/gama/v2/actor/step','/integration/gama/v3/actor/evaluate')))
        original=request('/debug/scene/inspection')
        ocean=request('/scene/ocean/animation/status')
        water=request('/scene/ocean/material/status');preset=request('/scene/ocean/material/preset/status')
        check('starts_unowned',not status()['owned'])
        result=request('/integration/gama/v3/actor/acquire',dict(agent_id='Bottlenose_001'))
        check('acquire',result.get('ok'),result);token=result['ownership_token']
        s=status();check('no_autonomous_subscription',s['update_subscription_count']==0 and not s['autonomous_controller'])
        fingerprint=s['body_fingerprint'];before=invariant(s)
        result=request('/integration/gama/v3/actor/acquire',dict(agent_id='Other'))
        check('second_owner_rejected',not result['ok'] and invariant(status())==before)
        for i,h in enumerate((0,90,180,270)):
            result=command('step',step=manual(i,heading_deg=h,depth_m=.8+i,horizontal_position_m=[3+i,7-i]))
            check('cardinal_step_'+str(h),result['ok'],result)
            s=status();m=s['composed_matrix'];position=[m[3][j]*.01 for j in range(3)]
            expected=[3+i,-(.8+i),7-i]
            pe=max(abs(x-y) for x,y in zip(position,expected));heading=math.degrees(math.atan2(m[2][0],m[2][2]))%360
            he=abs((heading-h+180)%360-180)
            check('composed_mapping_'+str(h),pe<=T['position_error_m'] and he<=T['circular_heading_error_deg'],dict(position_error_m=pe,heading_error_deg=he))
            check('static_body_'+str(h),s['body_fingerprint']==fingerprint)
        before=invariant(status())
        result=command('step',step=manual(3,heading_deg=270,depth_m=3.8,horizontal_position_m=[6,4]))
        check('duplicate_no_scene_write',result['ok'] and result['duplicate'] and invariant(status())==before,result)
        for name,bad in [('stale',manual()),('gap',manual(5)),('wrong_agent',manual(4,agent_id='Other'))]+[(i['name'],i['payload']) for i in json.loads((BASE/'fixtures/m2/invalid_steps.json').read_text())]:
            result=command('step',step=bad)
            check('atomic_reject_'+name,not result['ok'] and invariant(status())==before,result)
        result=request('/integration/gama/v3/actor/reset',dict(ownership_token='wrong'))
        check('wrong_token',not result['ok'] and invariant(status())==before)
        check('reset_ok',command('reset')['ok'])
        check('reset_holds_pose_and_phase',status()['frame']==before['frame'])
        check('wrap_left',command('step',step=manual(heading_deg=350))['ok'])
        check('wrap_right',command('step',step=manual(1,heading_deg=10,horizontal_position_m=[5,9],depth_m=1.8))['ok'])
        snapshots={}
        for t in (0,.25,.5,.75,1):
            check('evaluate_'+str(t),command('evaluate',simulation_time_s=t)['ok'])
            snapshots[t]=invariant(status())
        for t in (1,.5,0,.75,.25):
            command('evaluate',simulation_time_s=t)
            check('query_order_'+str(t),invariant(status())==snapshots[t])
        command('evaluate',simulation_time_s=.5);s=status();m=s['composed_matrix']
        pe=max(abs(x-y) for x,y in zip([m[3][j]*.01 for j in range(3)],[4,-1.3,8]))
        he=abs(math.degrees(math.atan2(m[2][0],m[2][2])))
        phase_error=abs((s['frame']['animation_phase_cycles']-.65+.5)%1-.5)
        check('interpolation_wrap_and_phase',pe<=T['position_error_m'] and he<=T['circular_heading_error_deg'] and phase_error<=T['animation_phase_error_cycles'],dict(position_error_m=pe,heading_error_deg=he,phase_error_cycles=phase_error))
        before=invariant(s);check('pause',command('pause',paused=True)['ok'])
        check('paused_step_rejected',not command('step',step=manual(2))['ok'])
        check('paused_evaluate_rejected',not command('evaluate',simulation_time_s=1)['ok'])
        time.sleep(2.2)
        check('pause_wall_clock_hold',invariant(status())==before and status()['transport_state']=='paused')
        check('resume',command('pause',paused=False)['ok'])
        check('resume_no_jump',invariant(status())==before)
        check('missing_freeze_report',status()['transport_state']=='frozen_updates_missing' and invariant(status())==before)
        check('outside_bracket_freezes',not command('evaluate',simulation_time_s=3)['ok'] and invariant(status())==before)
        command('reset')
        frozen=dict(version='constant_rate_v1',epoch_time_s=0.,epoch_phase_cycles=.2,rate_hz=0.)
        command('step',step=manual(speed_mps=0,animation_clock=frozen))
        command('step',step=manual(1,speed_mps=0,animation_clock=frozen))
        f=status()['frame'];command('evaluate',simulation_time_s=0)
        check('zero_speed_phase_frozen',f['animation_phase_cycles']==status()['frame']['animation_phase_cycles']==.2)
        elapsed=request('/scene/ocean/animation/status')
        check('ocean_continues_independently',elapsed['running'] and elapsed['elapsed']>ocean['elapsed'])
        check('water_unchanged_during_actor_test',request('/scene/ocean/material/status')==water and request('/scene/ocean/material/preset/status')==preset)
        check('legacy_actors_remain_unowned',not request('/integration/gama/actor/status')['owned'] and not request('/integration/gama/v2/actor/status')['owned'])
        check('release',command('release')['ok']);token=None
        after=request('/debug/scene/inspection')
        def animal(inspection):
            return [{k:p[k] for k in ('path','type','visibility','bounds_min','bounds_max')}|
                    {'xform_ops':[{k:o[k] for k in ('name','value')} for o in p['xform_ops']]}
                    for p in inspection['prims'] if p['path'].startswith('/World/Cetaceans/')]
        check('demonstration_animal_unchanged',animal(original)==animal(after))
        check('owned_layer_removed',not status()['owned'] and all(not p['path'].startswith('/MarlinGamaBottlenose') for p in after['prims']) and len(original['layers'])==len(after['layers']))
        for name,path in dict(inspection='/debug/scene/inspection',ocean='/scene/ocean/animation/status',swim='/scene/cetacean/swim/status',gallery='/scene/cetaceans/gallery/swim/status',chase='/scene/camera/chase/status',material='/scene/ocean/material/status',preset='/scene/ocean/material/preset/status').items():
            (output/(name+'_after.json')).write_text(json.dumps(request(path),indent=2)+'\n')
    except BaseException:
        (output/'failure.txt').write_text(traceback.format_exc())
        raise
    finally:
        if token:
            result=command('release');checks['finally_release']=dict(passed=result['ok'])
        (output/'http_calls.json').write_text(json.dumps(calls,indent=2)+'\n')
        (output/'results.json').write_text(json.dumps(dict(passed=bool(checks) and all(v['passed'] for v in checks.values()) and not (output/'failure.txt').exists(),checks=checks,tolerance_sha256=hashlib.sha256((BASE/'acceptance_tolerances.json').read_bytes()).hexdigest(),scope='live Kit Services + composed USD state; hand-authored fixtures, no image identity or body animation claim'),indent=2)+'\n')
    print(json.dumps(dict(passed=True,checks=len(checks),output=str(output))))


if __name__=='__main__':run(Path(sys.argv[1]))
