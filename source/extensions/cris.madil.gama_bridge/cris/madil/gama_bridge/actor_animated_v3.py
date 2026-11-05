"""Opt-in instance pose on the same exclusive v3 namespace; M2 stays static."""
from copy import deepcopy
import hashlib
import json
from pxr import Usd, UsdSkel

from .actor_v3 import BottlenoseActor, ROOT, ACTOR, _fingerprint_value
from .simulation_pose import InstanceSwimPose

ANIMATION = ACTOR + '/Animations/ExplicitSwimPose'


class AnimatedBottlenoseActor(BottlenoseActor):
    def __init__(self):
        super().__init__()
        self.pose = None
        self.expected_pose = self.pose_controls = None

    def _body_signature(self):
        # All source geometry/calibration stays immutable. Only the exact owned
        # animation relationship is excluded, then separately guarded below.
        records=[]
        for prim in Usd.PrimRange(self.stage.GetPrimAtPath(ACTOR+'/Model')):
            attrs=[]
            for attr in prim.GetAttributes():
                if attr.GetTimeSamples():raise ValueError('Unexpected time-sampled source-body attribute')
                attrs.append((attr.GetName(),str(attr.GetTypeName()),_fingerprint_value(attr.Get())))
            relations=[]
            for relation in prim.GetRelationships():
                targets=[str(p) for p in relation.GetTargets()]
                if relation.GetName()=='skel:animationSource':
                    if targets not in ([],[ANIMATION]):raise ValueError('Foreign animation binding')
                    continue
                relations.append((relation.GetName(),targets))
            records.append((str(prim.GetPath()),str(prim.GetTypeName()),prim.IsActive(),attrs,relations))
        return hashlib.sha256(json.dumps(records,sort_keys=True,allow_nan=False).encode()).hexdigest()

    def acquire(self,stage,agent_id,paused=False):
        result=super().acquire(stage,agent_id,paused)
        try:
            with Usd.EditContext(stage,self.layer):
                self.pose=InstanceSwimPose(stage,ACTOR+'/Model',ANIMATION)
                initial=dict(animation_phase_cycles=0.,agent=dict(speed_mps=0.))
                evaluation=self.pose.evaluate(initial)
                self.expected_pose=self.pose.write(evaluation)
            # Binding adds no source mesh, joint-rest or material change.
            if self._body_signature()!=self.expected_body:raise ValueError('Animation binding changed immutable body data')
            self.expected_layer=self.layer.ExportToString()
            self.pose_controls=self._controls(evaluation)
        except Exception:
            self.close();raise
        return {**result,'body_pose_mapping':'existing_baked_cycle_m4_v1','animation_path':ANIMATION,
                'manoeuvre_pose':'limited; existing swim cycle with trajectory root attitude'}

    @staticmethod
    def _controls(evaluation):
        return {k:deepcopy(evaluation[k]) for k in ('phase','weight','mapping','manoeuvre_pose')}

    def _guard(self,stage,token,paused):
        super()._guard(stage,token,paused)
        if self.pose is not None:self.pose.guard(self.expected_pose)

    def _write(self,stage,frame):
        if self.pose is None:raise ValueError('Animated instance has not been acquired')
        frame=deepcopy(frame)
        frame['body_pose_mapping']='existing_baked_cycle_m4_v1'
        frame['body_animation_evaluated']=True
        evaluation=self.pose.evaluate(frame)
        before=self.layer.ExportToString()
        saved=(self.expected_matrix,deepcopy(self.frame),self.expected_layer,deepcopy(self.expected_pose),deepcopy(self.pose_controls))
        try:
            super()._write(stage,frame)
            with Usd.EditContext(stage,self.layer):
                expected_pose=self.pose.write(evaluation)
                stage.GetPrimAtPath(ROOT).SetCustomDataByKey('marlin:pose_mapping','existing_baked_cycle_m4_v1')
            self.pose.guard(expected_pose)
            self.expected_pose=expected_pose;self.pose_controls=self._controls(evaluation)
            self.expected_layer=self.layer.ExportToString()
        except Exception:
            self.layer.ImportFromString(before)
            self.expected_matrix,self.frame,self.expected_layer,self.expected_pose,self.pose_controls=saved
            raise

    def evaluate(self,stage,token,seconds,paused=False):
        super().evaluate(stage,token,seconds,paused)
        return {'frame':deepcopy(self.frame),'rendered':False}

    def status(self,stage=None,paused=False):
        result=super().status(stage,paused)
        return {**result,'body_pose_mapping':'existing_baked_cycle_m4_v1',
                'pose_controls':deepcopy(self.pose_controls),
                'composed_joint_attributes':self.pose.attribute_record() if self.pose else None,
                'expected_joint_attributes':deepcopy(self.expected_pose),
                'animation_path':ANIMATION if self.pose else None,'timeline_driven':False,
                'manoeuvre_pose':'limited; existing swim cycle, no bespoke banking/steering/dive offsets'}

    def close(self):
        super().close()
        self.pose=self.expected_pose=self.pose_controls=None
