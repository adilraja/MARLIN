"""Compare retained native TRS/root data and skin snapshots with final evaluator."""
import hashlib
import json
import math
from pathlib import Path
import sys
import numpy as np
from pxr import Gf,Usd,UsdSkel,Vt

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[3]
BASE=ROOT.parents[1]
sys.path.insert(0,str(REPO/'tools'))
import test_gama_animated_v3 as helper


def main():
    stage=helper.new_stage();owner=helper.actor.AnimatedBottlenoseActor();token=owner.acquire(stage,'Bottlenose_001')['ownership_token']
    source=json.loads((BASE/'trajectories/m3_ref_a01/trajectory.json').read_text());index=-1
    report=dict(passed=False,frames=0,max_root_matrix_error=0.,max_joint_matrix_error=0.,max_phase_error_cycles=0.,max_weight_error=0.,skin_snapshot_comparisons=[])
    try:
        for job in ('dry02','review01'):
            result=json.loads((ROOT/'native_runs'/job/'result.json').read_text());directory=Path(result['media_directory']);body_signatures=set()
            for record in result['frames']:
                raw=json.loads((directory/record['file']).with_suffix('.json').read_text());t=raw['simulation_time_s'];target=int(math.ceil(t/.25-1e-10))
                if index>target or (index>=0 and t<max(0,index-1)*.25):owner.reset(stage,token);index=-1
                while index<target:index+=1;owner.apply(stage,token,source[index])
                owner.evaluate(stage,token,t)
                actual=UsdSkel.MakeTransforms(Vt.Vec3fArray([Gf.Vec3f(*v) for v in raw['joint_translations']]),
                    Vt.QuatfArray([Gf.Quatf(v[0],Gf.Vec3f(*v[1:])) for v in raw['joint_rotations']]),
                    Vt.Vec3hArray([Gf.Vec3h(*v) for v in raw['joint_scales']]))
                expected=UsdSkel.Cache().GetAnimQuery(owner.pose.animation).ComputeJointLocalTransforms(Usd.TimeCode.Default())
                report['max_joint_matrix_error']=max(report['max_joint_matrix_error'],max(abs(a[i][j]-b[i][j]) for a,b in zip(actual,expected) for i in range(4) for j in range(4)))
                report['max_root_matrix_error']=max(report['max_root_matrix_error'],max(abs(raw['root_matrix'][i][j]-owner.expected_matrix[i][j]) for i in range(4) for j in range(4)))
                report['max_phase_error_cycles']=max(report['max_phase_error_cycles'],abs((raw['pose_controls']['phase']-owner.pose_controls['phase']+.5)%1-.5))
                report['max_weight_error']=max(report['max_weight_error'],abs(raw['pose_controls']['weight']-owner.pose_controls['weight']))
                assert raw['frame']['agent']==owner.frame['agent']
                assert owner.frame['body_pose_mapping']=='existing_baked_cycle_m4_v1' and owner.frame['body_animation_evaluated']
                body_signatures.add(raw['body_immutable_signature']);report['frames']+=1
            assert len(body_signatures)==1
        cpu=json.loads((ROOT/'cpu_pose_records_final.json').read_text());data=np.load(REPO/cpu['geometry_file'])
        directory=Path(json.loads((ROOT/'native_runs/review01/result.json').read_text())['media_directory'])
        native=json.loads((ROOT/'native_runs/review01/result.json').read_text())
        for t in (6.,16.,30.,38.,56.,70.):
            shot=next(f for f in native['frames'] if f['file'].startswith('shot_') and f['simulation_time_s']==t and f['view']=='close')
            metadata=json.loads((directory/shot['file']).with_suffix('.json').read_text());path=directory/metadata['pose_snapshot']
            assert hashlib.sha256(path.read_bytes()).hexdigest()==metadata['pose_snapshot_sha256']
            reopened=Usd.Stage.Open(str(path));points,triangles=helper.skin_geometry(reopened)
            i=int(np.flatnonzero(data['times']==t)[0]);error=float(np.linalg.norm(points-data['points'][i],axis=1).max())
            assert np.array_equal(triangles,data['triangles'])
            report['skin_snapshot_comparisons'].append(dict(time_s=t,vertices=len(points),max_vertex_error_m=error,passed=error<=helper.T['skinned_vertex_repeat_error_m']))
        report['passed']=(report['frames']==681 and report['max_root_matrix_error']<=helper.T['root_matrix_component_error'] and
            report['max_joint_matrix_error']<=helper.T['joint_matrix_component_error'] and report['max_phase_error_cycles']<=helper.T['phase_error_cycles'] and
            report['max_weight_error']<=1e-9 and all(x['passed'] for x in report['skin_snapshot_comparisons']))
        report['descriptive_metadata_disposition']='Raw capture frame inherited an M2 static mapping hint. It was preserved; actual owned animation controls/TRS and source snapshot identify the animated evaluator. The final subclass corrects only this descriptive label; all retained numeric poses were compared above.'
    finally:
        owner.close()
        with (ROOT/'native_pose_comparison.json').open('x') as f:f.write(json.dumps(report,indent=2)+'\n')
    assert report['passed'],report
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
