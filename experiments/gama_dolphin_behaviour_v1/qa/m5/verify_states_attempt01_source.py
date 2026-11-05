"""Independent USD reopening, replay and numerical audit of M5 state evidence."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
from pxr import Usd, UsdGeom, UsdSkel

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[3]
BASE = ROOT.parents[1]
sys.path.insert(0, str(REPO/'tools'))
import test_gama_animated_v3 as accepted

spec = importlib.util.spec_from_file_location('_m5_reused_geometry', BASE/'qa/m4/native_worker.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
env_spec = importlib.util.spec_from_file_location('_m5_frozen_environment', ROOT/'native_m5.py')
env_module = importlib.util.module_from_spec(env_spec)
env_spec.loader.exec_module(env_module)


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(phase):
    plan = load(ROOT/'locked_plan_v3.json')
    tolerance = load(REPO/plan['acceptance']['path'])
    primary = load(ROOT/plan['primary_run']/'result.json')
    assert primary['status']=='passed'
    assert all(primary['checks'].values()) and all(primary['restoration'].values())
    directory = Path(primary['media_directory'])
    records = load(directory/'schedule_a.json')
    expected_times = sorted({round(i/5,6) for i in range(370)} | set(plan['snapshot_times_s']))
    assert [r['simulation_time_s'] for r in records]==expected_times
    assert len(primary['comparisons'])==len(records)+len(plan['reorder_times_s'])
    assert all(c['passed'] for c in primary['comparisons'])
    report = dict(passed=False, phase=phase, simulation_duration_s=74, video_fps=5,
        queried_timestamps=len(records), schedule_comparisons=len(records),
        reordered_seek_comparisons=len(plan['reorder_times_s']), frozen_snapshots=[],
        actual_gama_reference_sha256=sha(REPO/plan['reference']['path']),
        max_root_matrix_error=0., max_joint_matrix_error=0., max_phase_error_cycles=0.,
        max_root_position_error_m=0., max_frozen_skin_error_m=0., max_repeated_skin_error_m=0.)
    source = load(REPO/plan['reference']['path'])
    actor = accepted.actor.AnimatedBottlenoseActor()
    stage = accepted.new_stage()
    token = actor.acquire(stage, 'Bottlenose_001')['ownership_token']
    index = -1
    try:
        import math
        for record in records:
            seconds=record['simulation_time_s']
            target=int(math.ceil(seconds/.25-1e-10))
            while index<target:
                index+=1; actor.apply(stage,token,source[index])
            actor.evaluate(stage,token,seconds)
            root=np.asarray(native.plain(actor.expected_matrix))
            joints=np.asarray(native.plain(UsdSkel.Cache().GetAnimQuery(actor.pose.animation).ComputeJointLocalTransforms(Usd.TimeCode.Default())))
            root_error=float(np.abs(root-record['root_matrix']).max())
            pose_error=float(np.abs(joints-record['joint_local_matrices']).max())
            position_error=float(np.linalg.norm((root-np.asarray(record['root_matrix']))[3,:3])*.01)
            phase_error=abs(actor.pose_controls['phase']-record['pose_controls']['phase'])
            assert actor.frame['agent']==record['frame']['agent']
            assert actor.pose_controls==record['pose_controls']
            assert not record['root_time_samples'] and not any(record['joint_time_samples'].values())
            assert not record['timeline_playing']
            report['max_root_matrix_error']=max(report['max_root_matrix_error'],root_error)
            report['max_joint_matrix_error']=max(report['max_joint_matrix_error'],pose_error)
            report['max_phase_error_cycles']=max(report['max_phase_error_cycles'],phase_error)
            report['max_root_position_error_m']=max(report['max_root_position_error_m'],position_error)
    finally:
        actor.close()

    runs=[primary]
    if phase=='final':
        fresh=load(ROOT/'fresh01/result.json')
        assert fresh['status']=='passed' and fresh['pid']!=primary['pid']
        assert all(fresh['checks'].values()) and all(fresh['restoration'].values())
        assert len(fresh['comparisons'])==6 and all(c['passed'] for c in fresh['comparisons'])
        report.update(primary_pid=primary['pid'], fresh_pid=fresh['pid'], fresh_process_comparisons=6,
                      fresh_process_is_distinct=True)
        runs.append(fresh)
    reference_points={}
    for run in runs:
        for capture in run['captures']:
            if not capture['snapshot']:
                continue
            folder=Path(run['media_directory'])/capture['label']
            record=load(folder/'state.json')
            assert sha(folder/'scene.usdc')==record['scene_sha256']
            assert sha(folder/'skin.npz')==record['skin_sha256']
            reopened=Usd.Stage.Open(str(folder/'scene.usdc'))
            assert reopened
            points=native.geometry(reopened,accepted.actor.ACTOR)*UsdGeom.GetStageMetersPerUnit(reopened)
            with np.load(folder/'skin.npz') as archive:
                measured=archive['points_m']
            assert points.shape==measured.shape==(21504,3)
            error=float(np.linalg.norm(points-measured,axis=1).max())
            report['max_frozen_skin_error_m']=max(report['max_frozen_skin_error_m'],error)
            t=record['simulation_time_s']
            repeat_error=0.
            if t in reference_points:
                repeat_error=float(np.linalg.norm(measured-reference_points[t],axis=1).max())
            else:
                reference_points[t]=measured.copy()
            report['max_repeated_skin_error_m']=max(report['max_repeated_skin_error_m'],repeat_error)
            frozen_root=UsdGeom.Xformable(reopened.GetPrimAtPath(accepted.actor.ACTOR)).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            root_error=float(np.abs(np.asarray(native.plain(frozen_root))-record['root_matrix']).max())
            frozen_animation=UsdSkel.Animation(reopened.GetPrimAtPath(accepted.actor.ANIMATION))
            frozen_joints=UsdSkel.Cache().GetAnimQuery(frozen_animation).ComputeJointLocalTransforms(Usd.TimeCode.Default())
            joint_error=float(np.abs(np.asarray(native.plain(frozen_joints))-record['joint_local_matrices']).max())
            current_env=env_module.environment(reopened)
            assert current_env==record['environment'], 'Reopened ocean/lighting differed'
            assert env_module.fingerprint(current_env)==record['environment_sha256']
            assert record['buffer_samples'] and record['accepted_steps']>0
            assert root_error<=tolerance['root_matrix_component_error']
            assert joint_error<=tolerance['joint_matrix_component_error']
            report['frozen_snapshots'].append(dict(run=run['run_id'],label=capture['label'],time_s=t,
                vertices=len(points), reopened_skin_error_m=error, repeated_skin_error_m=repeat_error,
                root_matrix_error=root_error,joint_matrix_error=joint_error,
                environment_reopened_exactly=True,
                passed=error<=tolerance['skinned_vertex_repeat_error_m'] and repeat_error<=tolerance['skinned_vertex_repeat_error_m']))
            del reopened
    assert len(reference_points)==23
    report['passed']=(report['max_root_matrix_error']<=tolerance['root_matrix_component_error'] and
        report['max_joint_matrix_error']<=tolerance['joint_matrix_component_error'] and
        report['max_root_position_error_m']<=tolerance['root_position_error_m'] and
        report['max_phase_error_cycles']<=tolerance['phase_error_cycles'] and
        all(r['passed'] for r in report['frozen_snapshots']))
    assert report['passed']
    path=ROOT/('state_comparison_'+phase+'.json')
    with path.open('x') as stream:json.dump(report,stream,indent=2);stream.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k!='frozen_snapshots'},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['primary','final'])
    main(parser.parse_args().phase)
