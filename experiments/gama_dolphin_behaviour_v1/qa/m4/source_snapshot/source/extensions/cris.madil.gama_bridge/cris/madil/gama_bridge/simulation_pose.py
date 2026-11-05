"""Existing Model 61A bake evaluated at explicit phase; no global timeline."""
import hashlib
import json
import math
from pathlib import Path

from pxr import Gf, Sdf, Usd, UsdSkel, Vt
from cris.madil.render_service.skeletal_animation import baked_joint_local, _normalized_bone_name
from .actor_v3 import REPO, _fingerprint_value

PROFILE = REPO / 'source/extensions/cris.madil.gama_bridge/config/animation_model61a_m4_v1.json'


def cubic(a,b,c,d,u):
    return .5*((2*b)+(-a+c)*u+(2*a-5*b+4*c-d)*u*u+(-a+3*b-3*c+d)*u*u*u)


def normalized(q):
    length=math.sqrt(sum(v*v for v in q))
    if not math.isfinite(length) or length<1e-12:raise ValueError('Invalid quaternion')
    return [v/length for v in q]


def quaternion_cubic(values,u):
    values=[normalized(q) for q in values]
    for index in (0,2,3):
        reference=values[1] if index in (0,2) else values[2]
        if sum(a*b for a,b in zip(values[index],reference))<0:values[index]=[-v for v in values[index]]
    return normalized([cubic(*(q[k] for q in values),u) for k in range(4)])


class InstanceSwimPose:
    def __init__(self,stage,model_path,animation_path):
        self.stage,self.animation_path=stage,animation_path
        self.profile=json.loads(PROFILE.read_text())
        path=REPO/self.profile['clip']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=self.profile['clip_sha256']:
            raise ValueError('Preserved swim bake changed')
        payload=json.loads(path.read_text())
        skeletons=[p for p in Usd.PrimRange(stage.GetPrimAtPath(model_path)) if p.IsA(UsdSkel.Skeleton)]
        if len(skeletons)!=1:raise ValueError('Exactly one existing skeleton required')
        self.skeleton=UsdSkel.Skeleton(skeletons[0]);self.joints=self.skeleton.GetJointsAttr().Get()
        self.rest=self.skeleton.GetRestTransformsAttr().Get()
        if payload.get('transform_space')!='rest_relative' or len(payload['bone_names'])!=len(self.joints):
            raise ValueError('Incompatible rest-relative bake')
        if [_normalized_bone_name(n) for n in payload['bone_names']]!=[str(j).rsplit('/',1)[-1] for j in self.joints]:
            raise ValueError('Existing skeleton/bake joint order differs')
        frames=payload['frames']
        if len(frames)<4 or frames[0]['frame']!=payload['start_frame'] or frames[-1]['frame']!=payload['end_frame']:
            raise ValueError('Incomplete loop samples')
        for frame in frames:
            for key,size in (('translations',3),('rotations',4),('scales',3)):
                if len(frame[key])!=len(self.joints) or any(len(v)!=size or any(type(x) not in (int,float) or not math.isfinite(x) for x in v) for v in frame[key]):
                    raise ValueError('Malformed baked joint sample')
        for key in ('translations','rotations','scales'):
            if frames[0][key]!=frames[-1][key]:raise ValueError('Existing bake endpoints are not identical')
        for frame in frames:
            if (any(abs(x)>1e-12 for x in frame['translations'][0]) or
                any(abs(a-b)>1e-12 for a,b in zip(frame['rotations'][0],[1,0,0,0])) or
                any(abs(x-1)>1e-12 for x in frame['scales'][0])):
                raise ValueError('Synthetic root contains motion; explicit adaptation required')
        self.frames=frames[:-1]
        self.binding=UsdSkel.BindingAPI(self.skeleton.GetPrim())
        self.animation=UsdSkel.Animation.Define(stage,animation_path)
        self.animation.GetJointsAttr().Set(self.joints)
        self.binding.CreateAnimationSourceRel().SetTargets([Sdf.Path(animation_path)])
        self.expected_attributes=None

    def evaluate(self,frame):
        phase=frame['animation_phase_cycles'];speed=frame['agent']['speed_mps']
        if not math.isfinite(phase) or not 0<=phase<1:raise ValueError('Explicit normalized phase required')
        u=min(1.,max(0.,speed/self.profile['full_cycle_speed_mps']))
        weight=u*u*u*(10+u*(-15+6*u))
        f=phase*len(self.frames);index=math.floor(f);fraction=f-index
        samples=[self.frames[(index+i)%len(self.frames)] for i in (-1,0,1,2)]
        local=[];relative=[]
        for j in range(len(self.joints)):
            translation=[cubic(*(v['translations'][j][k] for v in samples),fraction)*weight for k in range(3)]
            scale=[1+(cubic(*(v['scales'][j][k] for v in samples),fraction)-1)*weight for k in range(3)]
            q=quaternion_cubic([v['rotations'][j] for v in samples],fraction)
            blend=Gf.Slerp(weight,Gf.Quatd(1),Gf.Quatd(q[0],Gf.Vec3d(*q[1:])))
            rotation=[blend.GetReal(),*blend.GetImaginary()]
            if j==0:
                # The inspected synthetic root has no locomotion. Lock it exactly;
                # MAIN_18 retains the existing cyclic trunk rotation below it.
                translation,rotation,scale=[0.,0.,0.],[1.,0.,0.,0.],[1.,1.,1.]
            local.append(baked_joint_local(self.rest[j],translation,rotation,scale))
            relative.append(dict(translation=translation,rotation=rotation,scale=scale))
        return dict(local=Vt.Matrix4dArray(local),relative=relative,phase=phase,weight=weight,
                    mapping='existing_baked_cycle_m4_v1',manoeuvre_pose='limited; existing cycle with recorded root attitude')

    def write(self,evaluation):
        if not self.animation.SetTransforms(evaluation['local']):raise ValueError('Could not author explicit joint pose')
        return self.attribute_record()

    def attribute_record(self):
        return {name:_fingerprint_value(self.animation.GetPrim().GetAttribute(name).Get())
                for name in ('joints','translations','rotations','scales')}

    def guard(self,expected):
        if self.binding.GetAnimationSourceRel().GetTargets()!=[Sdf.Path(self.animation_path)]:
            raise ValueError('Competing animation binding; actor is frozen')
        if any(a.GetTimeSamples() for a in self.animation.GetPrim().GetAttributes()):
            raise ValueError('Time-sampled animation writer; actor is frozen')
        if self.attribute_record()!=expected:raise ValueError('Competing composed joint-pose writer; actor is frozen')
