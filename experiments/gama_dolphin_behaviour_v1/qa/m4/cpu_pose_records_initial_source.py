"""Retain actual CPU UsdSkel geometry for diagnostic reference timestamps."""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from pxr import Usd,UsdGeom

REPO=Path(__file__).resolve().parents[4]
BASE=REPO/'experiments/gama_dolphin_behaviour_v1'
sys.path.insert(0,str(REPO/'tools'))
import test_gama_animated_v3 as helper


def main():
    output=REPO/'artifacts/gama_dolphin_behaviour_v1/m4/cpu_geometry';output.mkdir(parents=True,exist_ok=False)
    stage=helper.new_stage();owner=helper.actor.AnimatedBottlenoseActor();token=owner.acquire(stage,'Bottlenose_001')['ownership_token']
    times=json.loads((BASE/'qa/m4/locked_plan.json').read_text())['diagnostic_simulation_times_s']
    source=json.loads((BASE/'trajectories/m3_ref_a01/trajectory.json').read_text());index=-1;records=[];arrays=[]
    try:
        for i,t in enumerate(times):
            target=int(np.ceil(t/.25))
            while index<target:index+=1;owner.apply(stage,token,source[index])
            owner.evaluate(stage,token,t)
            points,triangles=helper.skin_geometry(stage);arrays.append(points)
            report=dict(index=i,time_s=t,frame=owner.frame,pose_controls=owner.pose_controls,body_signature=owner.expected_body,
                root_matrix=[list(row) for row in owner.expected_matrix],local_animation_matrices=[list(map(list,m)) for m in owner.pose.animation.GetTransforms(Usd.TimeCode.Default())[1]] if False else None,
                root_space_bounds_m=[points.min(axis=0).tolist(),points.max(axis=0).tolist()])
            snapshot=output/f'pose_{i:02d}.usda';owner.layer.Export(str(snapshot));reopened=Usd.Stage.Open(str(snapshot));UsdGeom.SetStageUpAxis(reopened,'Y');UsdGeom.SetStageMetersPerUnit(reopened,.01);reopened.GetRootLayer().Save()
            report.update(pose_snapshot=str(snapshot.relative_to(REPO)),pose_snapshot_sha256=hashlib.sha256(snapshot.read_bytes()).hexdigest())
            records.append(report)
        np.savez_compressed(output/'geometry.npz',points=np.array(arrays),triangles=triangles,times=np.array(times))
        summary=dict(passed=True,scope='CPU evaluated skinned geometry; no RTX image or biological acceptance',vertices=len(arrays[0]),triangles=len(triangles),records=records,geometry_file=str((output/'geometry.npz').relative_to(REPO)),geometry_sha256=hashlib.sha256((output/'geometry.npz').read_bytes()).hexdigest())
        (BASE/'qa/m4/cpu_pose_records.json').write_text(json.dumps(summary,indent=2)+'\n')
    finally:owner.close()
    print('Retained',len(records),'actual M3 timestamp poses and their evaluated skin geometry')


if __name__=='__main__':main()
