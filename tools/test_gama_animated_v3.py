"""CPU composed UsdSkel acceptance against predeclared M4 gates."""
from copy import deepcopy
import hashlib
import importlib
import json
import math
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

import numpy as np
from pxr import Gf, Sdf, Usd, UsdGeom, UsdSkel, Vt

REPO=Path(__file__).resolve().parents[1]
BASE=REPO/'experiments/gama_dolphin_behaviour_v1'
# Load the pure USD helper without starting the Omniverse extension __init__.
for name,path in [('cris',REPO/'source/extensions/cris.madil.render_service/cris'),('cris.madil',REPO/'source/extensions/cris.madil.render_service/cris/madil'),('cris.madil.render_service',REPO/'source/extensions/cris.madil.render_service/cris/madil/render_service'),('_animated_v3_test',REPO/'source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge')]:
    module=types.ModuleType(name);module.__path__=[str(path)];sys.modules[name]=module
actor=importlib.import_module('_animated_v3_test.actor_animated_v3')
static=importlib.import_module('_animated_v3_test.actor_v3')
T=json.loads((BASE/'animation/m4_acceptance_v1.json').read_text())
assert hashlib.sha256((BASE/'animation/m4_acceptance_v1.json').read_bytes()).hexdigest()==json.loads((BASE/'qa/m4/locked_plan.json').read_text())['tolerance_sha256']
METRICS=[]


def new_stage():
    stage=Usd.Stage.CreateInMemory();UsdGeom.SetStageUpAxis(stage,'Y');UsdGeom.SetStageMetersPerUnit(stage,.01)
    UsdGeom.Xform.Define(stage,'/World/OtherAnimal');return stage


def skin_geometry(stage):
    cache=UsdSkel.Cache();root=stage.GetPrimAtPath(actor.ACTOR+'/Model')
    for p in Usd.PrimRange(root):
        if p.IsA(UsdSkel.Root):cache.Populate(UsdSkel.Root(p),Usd.PrimDefaultPredicate)
    skeleton=next(p for p in Usd.PrimRange(root) if p.IsA(UsdSkel.Skeleton))
    query=cache.GetSkelQuery(UsdSkel.Skeleton(skeleton));transforms=query.ComputeSkinningTransforms(Usd.TimeCode.Default())
    world=UsdGeom.Xformable(skeleton).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    inverse=UsdGeom.Xformable(stage.GetPrimAtPath(actor.ACTOR)).ComputeLocalToWorldTransform(Usd.TimeCode.Default()).GetInverse()
    points=[];triangles=[];offset=0
    for p in Usd.PrimRange(root):
        if not p.IsA(UsdGeom.Mesh):continue
        mesh=UsdGeom.Mesh(p);vertices=Vt.Vec3fArray(mesh.GetPointsAttr().Get());skin=cache.GetSkinningQuery(p)
        assert skin and skin.ComputeSkinnedPoints(transforms,vertices,Usd.TimeCode.Default())
        points.extend([list(inverse.Transform(world.Transform(Gf.Vec3d(v)))*.01) for v in vertices])
        cursor=0;indices=mesh.GetFaceVertexIndicesAttr().Get()
        for count in mesh.GetFaceVertexCountsAttr().Get():
            face=list(indices[cursor:cursor+count]);cursor+=count
            triangles.extend([[offset+face[0],offset+face[i],offset+face[i+1]] for i in range(1,count-1)])
        offset+=len(vertices)
    return np.array(points),np.array(triangles,dtype=np.int64)


def phase_frame(phase,speed=.8):
    value=json.loads((BASE/'fixtures/m2/valid_step_0.json').read_text())
    value['agents'][0]['speed_mps']=speed
    value['agents'][0]['animation_clock'].update(epoch_phase_cycles=phase,rate_hz=.8 if speed else 0)
    b=static.StepBuffer();b.accept(value);return b.evaluate(0)


class AnimatedUSD(unittest.TestCase):
    def setUp(self):
        self.stage=new_stage();self.before=self.stage.GetRootLayer().ExportToString();self.session=self.stage.GetSessionLayer().ExportToString()
        self.owner=actor.AnimatedBottlenoseActor();self.addCleanup(self.owner.close)
        self.token=self.owner.acquire(self.stage,'Bottlenose_001')['ownership_token']

    def test_bound_default_pose_and_independent_timeline(self):
        self.assertEqual(self.owner.pose.binding.GetAnimationSourceRel().GetTargets(),[Sdf.Path(actor.ANIMATION)])
        self.assertTrue(all(not a.GetTimeSamples() for a in self.owner.pose.animation.GetPrim().GetAttributes()))
        self.owner._write(self.stage,phase_frame(.2))
        query=UsdSkel.Cache().GetAnimQuery(self.owner.pose.animation)
        a=query.ComputeJointLocalTransforms(Usd.TimeCode.Default());b=query.ComputeJointLocalTransforms(Usd.TimeCode(543))
        self.assertEqual(a,b)

    def test_existing_timeline_binder_and_instance_pose_agree_at_bake_knots(self):
        legacy_module=importlib.import_module('cris.madil.render_service.skeletal_animation')
        old_stage=new_stage();old_owner=static.BottlenoseActor()
        self.addCleanup(old_owner.close);old_owner.acquire(old_stage,'Legacy')
        result=legacy_module.bind_baked_skeletal_animation(old_stage,actor.ACTOR,str(REPO/'assets/cetaceans/bottlenose_dolphin/animation/swim_cycle.json'))
        self.assertTrue(result['ok'])
        old_animation=UsdSkel.Animation(old_stage.GetPrimAtPath(result['animation_path']))
        query=UsdSkel.Cache().GetAnimQuery(old_animation)
        max_error=0.
        for index in range(30):
            expected=query.ComputeJointLocalTransforms(Usd.TimeCode(index/24*old_stage.GetTimeCodesPerSecond()))
            frame=phase_frame(index/30);evaluation=self.owner.pose.evaluate(frame)
            self.owner._write(self.stage,frame)
            current=UsdSkel.Cache().GetAnimQuery(self.owner.pose.animation).ComputeJointLocalTransforms(Usd.TimeCode.Default())
            max_error=max(max_error,max(abs(a[i][j]-b[i][j]) for a,b in zip(expected,current) for i in range(4) for j in range(4)))
        METRICS.append(dict(test='legacy binder vs explicit instance at 30 bake knots',max_joint_matrix_component_error=max_error))
        self.assertLessEqual(max_error,T['joint_matrix_component_error'])

    def test_actual_skinned_motion_and_gross_deformation(self):
        self.owner._write(self.stage,phase_frame(0,0));rest,triangles=skin_geometry(self.stage)
        base=rest[triangles];base_edges=np.stack((base[:,1]-base[:,0],base[:,2]-base[:,1],base[:,0]-base[:,2]),axis=1)
        base_lengths=np.linalg.norm(base_edges,axis=2);base_norm=np.cross(base[:,1]-base[:,0],base[:,2]-base[:,0]);base_area=np.linalg.norm(base_norm,axis=1)
        valid=base_area>2*T['gross_deformation']['degenerate_rest_area_m2'];edge_valid=base_lengths>1e-8
        peaks=dict(max_vertex_change_m=0.,edge_ratio_min=math.inf,edge_ratio_max=0.,area_ratio_min=math.inf,area_ratio_max=0.,face_normal_dot_min=1.)
        failures=[];fingerprint=self.owner.expected_body
        for phase in np.linspace(0,1,61,endpoint=False):
            self.owner._write(self.stage,phase_frame(float(phase)));points,faces=skin_geometry(self.stage)
            self.assertTrue(np.array_equal(triangles,faces));self.assertTrue(np.isfinite(points).all())
            current=points[faces];edges=np.stack((current[:,1]-current[:,0],current[:,2]-current[:,1],current[:,0]-current[:,2]),axis=1)
            ratio=np.linalg.norm(edges,axis=2)[edge_valid]/base_lengths[edge_valid]
            normals=np.cross(current[:,1]-current[:,0],current[:,2]-current[:,0]);areas=np.linalg.norm(normals,axis=1)
            area_ratio=areas[valid]/base_area[valid]
            dots=np.sum(normals[valid]*base_norm[valid],axis=1)/(areas[valid]*base_area[valid])
            peaks['max_vertex_change_m']=max(peaks['max_vertex_change_m'],float(np.linalg.norm(points-rest,axis=1).max()))
            for name,value,operation in [('edge_ratio_min',ratio.min(),min),('edge_ratio_max',ratio.max(),max),('area_ratio_min',area_ratio.min(),min),('area_ratio_max',area_ratio.max(),max),('face_normal_dot_min',dots.min(),min)]:peaks[name]=operation(peaks[name],float(value))
            if ratio.min()<.5 or ratio.max()>1.5 or area_ratio.min()<.25 or area_ratio.max()>4 or dots.min()<0:failures.append(float(phase))
            self.assertEqual(self.owner._body_signature(),fingerprint)
        METRICS.append(dict(test='61 actual UsdSkel phase samples',vertices=len(rest),triangles=len(triangles),degenerate_rest_triangles_excluded=int((~valid).sum()),peaks=peaks,failed_phases=failures))
        self.assertGreater(peaks['max_vertex_change_m'],.001)
        self.assertFalse(failures,'Gross geometry guards failed; do not relax post hoc')

    def test_loop_orientation_and_derivative_continuity(self):
        eps=T['loop_probe_phase'];pose=self.owner.pose
        left=pose.evaluate(phase_frame(1-eps));middle=pose.evaluate(phase_frame(0));right=pose.evaluate(phase_frame(eps))
        max_angle=0.;max_derivative=0.
        def qdiff(a,b):return [x-y for x,y in zip(a,b)]
        for a,b,c in zip(left['relative'],middle['relative'],right['relative']):
            dot=abs(sum(x*y for x,y in zip(a['rotation'],c['rotation'])));angle=math.degrees(2*math.acos(min(1.,dot)))
            max_angle=max(max_angle,angle)
            va=np.array(qdiff(b['rotation'],a['rotation']))/eps;vb=np.array(qdiff(c['rotation'],b['rotation']))/eps
            max_derivative=max(max_derivative,float(np.linalg.norm(va-vb)*2*180/math.pi))
        METRICS.append(dict(test='periodic loop',angle_across_probe_deg=max_angle,derivative_difference_deg_per_cycle=max_derivative))
        self.assertLessEqual(max_angle,T['loop_rotation_continuity_deg']);self.assertLessEqual(max_derivative,T['loop_derivative_difference_deg_per_cycle'])

    def test_real_m3_states_order_pause_reset_and_zero_speed(self):
        states=json.loads((BASE/'trajectories/m3_ref_a01/trajectory.json').read_text())
        for state in states[:26]:self.owner.apply(self.stage,self.token,state)
        records={}
        for t in (6,6.125,6.25):
            result=self.owner.evaluate(self.stage,self.token,t)
            self.assertEqual(result['frame']['body_pose_mapping'],'existing_baked_cycle_m4_v1')
            self.assertTrue(result['frame']['body_animation_evaluated'])
            records[t]=(self.owner.expected_pose,self.owner.expected_matrix,self.owner.pose_controls)
        for t in (6.25,6,6.125):
            self.owner.evaluate(self.stage,self.token,t);self.assertEqual(records[t],(self.owner.expected_pose,self.owner.expected_matrix,self.owner.pose_controls))
        self.owner.set_paused(self.stage,self.token,True);before=self.owner.layer.ExportToString()
        with self.assertRaises(ValueError):self.owner.evaluate(self.stage,self.token,6)
        self.owner.set_paused(self.stage,self.token,False);self.assertEqual(before,self.owner.layer.ExportToString())
        self.owner.reset(self.stage,self.token);self.assertEqual(before,self.owner.layer.ExportToString())
        self.owner.apply(self.stage,self.token,states[0]);self.assertEqual(self.owner.pose_controls['weight'],0)

    def test_pose_failure_was_atomic(self):
        self.owner._write(self.stage,phase_frame(.25));before=self.owner.layer.ExportToString();expected=deepcopy(self.owner.expected_pose)
        with patch.object(self.owner.pose,'guard',side_effect=ValueError('injected composed pose failure')):
            with self.assertRaises(ValueError):self.owner._write(self.stage,phase_frame(.5))
        self.assertEqual(before,self.owner.layer.ExportToString());self.assertEqual(expected,self.owner.expected_pose)

    def test_competing_joint_opinion_and_static_owner_refused(self):
        other=static.BottlenoseActor();self.addCleanup(other.close)
        with self.assertRaises(ValueError):other.acquire(self.stage,'Other')
        with Usd.EditContext(self.stage,self.stage.GetSessionLayer()):
            self.owner.pose.animation.GetRotationsAttr().Set(Vt.QuatfArray([Gf.Quatf(1)]*20))
        self.assertEqual(self.owner.status(self.stage)['transport_state'],'frozen_guard_failure')
        before=self.owner.layer.ExportToString()
        with self.assertRaises(ValueError):self.owner.evaluate(self.stage,self.token,0)
        self.assertEqual(before,self.owner.layer.ExportToString())

    def test_release_restored_only_owned_layer(self):
        self.owner.release(self.token)
        self.assertEqual(self.stage.GetRootLayer().ExportToString(),self.before)
        self.assertEqual(self.stage.GetSessionLayer().ExportToString(),self.session)
        self.assertTrue(self.stage.GetPrimAtPath('/World/OtherAnimal'))


if __name__=='__main__':
    output=Path(sys.argv[1]);assert not output.exists()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    output.write_text(json.dumps(dict(passed=result.wasSuccessful(),tests=result.testsRun,failures=[(str(t),e) for t,e in result.failures],errors=[(str(t),e) for t,e in result.errors],metrics=METRICS,tolerance_sha256=hashlib.sha256((BASE/'animation/m4_acceptance_v1.json').read_bytes()).hexdigest()),indent=2)+'\n')
    sys.exit(0 if result.wasSuccessful() else 1)
