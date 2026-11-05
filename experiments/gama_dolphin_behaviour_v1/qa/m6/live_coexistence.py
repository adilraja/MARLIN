"""Bounded public-API coexistence and exact checkpoint rollback; no Kit restart."""
from copy import deepcopy
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
import subprocess
import time
import traceback
import urllib.request

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parents[1]


def write(path,value):
    with path.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')


def main():
    output=ROOT/'live_attempt01';output.mkdir(exist_ok=False)
    calls=[];checks={};token=None;failure=None
    baseline=json.loads((ROOT/'live_before/checkpoint.json').read_text())
    def api(path,payload=None):
        request=urllib.request.Request('http://localhost:8011'+path,
            data=None if payload is None else json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=90) as response:value=json.load(response)
        calls.append(dict(path=path,payload=payload,response=value,utc=datetime.now(timezone.utc).isoformat()))
        return value
    def check(name,condition):
        checks[name]=bool(condition)
        assert condition,name
    def command(name,**kwargs):
        return api('/integration/gama/v3/animated_actor/'+name,dict(ownership_token=token,**kwargs))
    def status():return api('/integration/gama/v3/animated_actor/status')
    def held(record):
        return {k:record[k] for k in ['composed_matrix','composed_joint_attributes','expected_joint_attributes',
            'frame','pose_controls','accepted_steps','latest','body_fingerprint']}
    def gpu(label):
        r=subprocess.run(['nvidia-smi','--query-gpu=name,memory.total,memory.used,memory.free,driver_version',
            '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=15)
        write(output/(label+'_gpu.json'),dict(returncode=r.returncode,stdout=r.stdout,stderr=r.stderr))
        assert r.returncode==0 and float(r.stdout.split(',')[-2])>=768
    try:
        gpu('before')
        check('unowned_before',not status()['owned'])
        acquired=api('/integration/gama/v3/animated_actor/acquire',dict(agent_id='Bottlenose_001'))
        check('private_acquired',acquired['ok']);token=acquired['ownership_token']
        source=json.loads((BASE/'trajectories/m3_ref_a01/trajectory.json').read_text())
        for state in source[:26]:check('accepted_reference_step_'+str(state['step_index']),command('step',step=state)['ok'])
        check('evaluated_nonzero_pose',command('evaluate',simulation_time_s=6.)['ok'])
        expected=held(status())
        config=json.loads((BASE/'qa/m5/locked_plan_v3.json').read_text())['ocean']['configuration']
        check('standard_ocean_started',api('/scene/ocean/animation/start',config)['ok'])
        regression=api('/scene/ocean/material/preset/diagnostic/regression',{})
        write(output/'native_regression_call.json',regression)
        check('native_wave_controller_regression',regression['ok'] and regression['phase_count']==5 and regression['controller_case_count']==2)
        result=json.loads((Path(regression['directory'])/'result.json').read_text())
        write(output/'native_regression_result.json',result)
        check('private_held_during_native_regression',held(status())==expected)
        check('engineering_preset_selected',api('/scene/ocean/material/preset',dict(selection='engineering_v1',configure_renderer=False))['ok'])
        check('standard_swimmer_started',api('/scene/cetacean/swim/start',dict(name='Dolphin_001',
            speed=5.,heading=0.,follow_ocean_surface=True,depth_below_surface=25.,body_animation=False))['ok'])
        check('standard_chase_started',api('/scene/camera/chase/start',dict(target_name='Dolphin_001',
            camera_name='M6CoexistenceCamera',activate_viewport=False,documentary_mode=False))['ok'])
        first={name:api(path) for name,path in dict(ocean='/scene/ocean/animation/status',
            swim='/scene/cetacean/swim/status',chase='/scene/camera/chase/status').items()}
        write(output/'coexist_before.json',first)
        started=time.monotonic()
        for index in range(4):
            time.sleep(1.)
            current=status()
            check('private_root_body_phase_held_'+str(index),held(current)==expected and current['guard_error'] is None)
        last={name:api(path) for name,path in dict(ocean='/scene/ocean/animation/status',
            swim='/scene/cetacean/swim/status',chase='/scene/camera/chase/status').items()}
        write(output/'coexist_after.json',last)
        write(output/'coexist_wall.json',dict(seconds=time.monotonic()-started,private_simulation_time_s=6.))
        check('standard_controllers_remained_running',all(v['running'] for v in first.values()) and all(v['running'] for v in last.values()))
        check('actual_ocean_phase_advanced',last['ocean']['elapsed']>first['ocean']['elapsed'])
        check('actual_standard_animal_advanced',any(last['swim'][k]!=first['swim'][k] for k in ['x','z','current_y']))
        check('actual_standard_camera_advanced',last['chase']['camera_position']!=first['chase']['camera_position'])
        check('private_no_autonomous_subscriptions',status()['update_subscription_count']==0)
        check('static_competing_owner_refused',not api('/integration/gama/v3/actor/acquire',dict(agent_id='Other'))['ok'])
        check('private_explicit_advance',command('evaluate',simulation_time_s=6.25)['ok'])
        check('private_advanced_only_on_command',held(status())!=expected)
        gpu('during')
        check('private_release',command('release')['ok']);token=None
        check('private_unowned_after_release',not status()['owned'])
        check('unrelated_controllers_survived_release',all(api(path)['running'] for path in
            ['/scene/ocean/animation/status','/scene/cetacean/swim/status','/scene/camera/chase/status']))
    except BaseException as error:
        failure=dict(error=str(error),traceback=traceback.format_exc())
    finally:
        cleanup={}
        if token:
            try:cleanup['private_release']=command('release')['ok']
            except BaseException:cleanup['private_release']=False
        for name,path in [('chase','/scene/camera/chase/stop'),('swim','/scene/cetacean/swim/stop'),('ocean','/scene/ocean/animation/stop')]:
            try:cleanup[name+'_stopped']=api(path,{})['ok']
            except BaseException:cleanup[name+'_stopped']=False
        try:
            restored=api('/debug/scene/checkpoint/'+baseline['checkpoint_id']+'/restore',{})
            write(output/'checkpoint_restore.json',restored);cleanup['baseline_restored']=restored['ok']
        except BaseException:
            cleanup['baseline_restored']=False
        checks.update(cleanup)
        write(output/'http_calls.json',calls)
        result=dict(passed=bool(checks) and all(checks.values()) and failure is None,checks=checks,
            failure=failure,kit_restarts=0,scope='One private GAMA actor and existing standard controllers; no source/asset edit, no rendering qualification, original checkpoint restored')
        write(output/'results.json',result)
    print(json.dumps(dict(passed=result['passed'],checks=len(checks),failure=failure),indent=2))
    assert result['passed'],failure


if __name__=='__main__':main()
