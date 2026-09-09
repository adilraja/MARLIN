"""Independent, reversible playback of the validated petrel test rig.

No Kit/timeline dependency: advance() receives elapsed application time.
Only a private session sublayer is authored; source assets are never edited.
"""
import math
from pathlib import Path

from pxr import Gf, Sdf, Usd, UsdSkel, Vt


ASSET = (Path(__file__).resolve().parents[6] /
         'assets/birds/european_storm_petrel/usd/european_storm_petrel_rigged.usd')


class PetrelPlayback:
    def __init__(self, stage, name='PetrelRigTest'):
        if not Sdf.Path.IsValidIdentifier(name):
            raise ValueError('Invalid animal name')
        self.stage, self.name = stage, name
        root = stage.GetPrimAtPath('/World/Cetaceans/' + name)
        if not root:
            raise ValueError('Spawn the animated petrel preview first')
        skeletons = [p for p in Usd.PrimRange(root) if p.IsA(UsdSkel.Skeleton)]
        if len(skeletons) != 1:
            raise ValueError('Expected exactly one petrel skeleton')
        self.skeleton_path = skeletons[0].GetPath()
        self.source = Usd.Stage.Open(str(ASSET))
        if not self.source:
            raise ValueError('Validated petrel animation asset is missing')
        animations = [UsdSkel.Animation(p) for p in self.source.Traverse()
                      if p.IsA(UsdSkel.Animation)]
        if len(animations) != 1:
            raise ValueError('Expected one source wingbeat animation')
        self.clip = animations[0]
        self.joints = self.clip.GetJointsAttr().Get()
        if list(UsdSkel.Skeleton(skeletons[0]).GetJointsAttr().Get()) != list(self.joints):
            raise ValueError('Target is not the validated petrel rig')
        # Static pose exports have modified rest transforms, and must not be
        # driven with the animated asset's joint-local samples.
        source_skeleton = next(UsdSkel.Skeleton(p) for p in self.source.Traverse()
                               if p.IsA(UsdSkel.Skeleton))
        self.rest_transforms = source_skeleton.GetRestTransformsAttr().Get()
        if UsdSkel.Skeleton(skeletons[0]).GetRestTransformsAttr().Get() != self.rest_transforms:
            raise ValueError('Use --pose animation, not a static pose export')
        times = self.clip.GetRotationsAttr().GetTimeSamples()
        if len(times) < 2:
            raise ValueError('Wingbeat clip has no time samples')
        self.first, self.last = times[0], times[-1]
        self.fps = self.source.GetTimeCodesPerSecond()
        self.duration = (self.last - self.first) / self.fps
        if self.duration <= 0:
            raise ValueError('Invalid clip duration')
        self.phase = 0.0
        self.speed = 1.0
        self.paused = False
        self.mode = 'flap'
        self.blend = self.blend_start = self.blend_target = 1.0
        self.transition_elapsed = self.transition_duration = 0.0
        self.layer = Sdf.Layer.CreateAnonymous('petrel_playback.usda')
        self.animation_path = self.skeleton_path.GetParentPath().AppendChild('MarlinPetrelPlayback')
        stage.GetSessionLayer().subLayerPaths.insert(0, self.layer.identifier)
        try:
            with Usd.EditContext(stage, self.layer):
                self.output = UsdSkel.Animation.Define(stage, self.animation_path)
                self.output.CreateJointsAttr().Set(self.joints)
                UsdSkel.BindingAPI.Apply(skeletons[0]).CreateAnimationSourceRel().SetTargets([self.animation_path])
            self._write_pose()
            if not self.is_valid():
                raise ValueError('A stronger animation binding prevents independent playback')
        except Exception:
            self.close()
            raise

    def is_valid(self):
        prim = self.stage.GetPrimAtPath(self.skeleton_path)
        return bool(prim and prim.IsA(UsdSkel.Skeleton)
                    and UsdSkel.Skeleton(prim).GetJointsAttr().Get() == self.joints
                    and UsdSkel.Skeleton(prim).GetRestTransformsAttr().Get() == self.rest_transforms
                    and UsdSkel.BindingAPI(prim).GetAnimationSourceRel().GetTargets() == [self.animation_path])

    def control(self, action='start', mode=None, speed=None, transition_seconds=0.5):
        if action not in ('start', 'pause', 'resume'):
            raise ValueError('Unknown playback action')
        if mode is not None and mode not in ('flap', 'glide'):
            raise ValueError('Mode must be flap or glide')
        if speed is not None and (not math.isfinite(speed) or not 0.05 <= speed <= 4):
            raise ValueError('Speed must be finite and between 0.05 and 4')
        if not math.isfinite(transition_seconds) or not 0 <= transition_seconds <= 10:
            raise ValueError('Transition must be finite and between 0 and 10 seconds')
        self.paused = action == 'pause'
        if speed is not None:
            self.speed = speed
        if mode is not None:
            self.mode = mode
            self.blend_start = self.blend
            self.blend_target = float(mode == 'flap')
            self.transition_elapsed = 0.0
            self.transition_duration = transition_seconds
            if transition_seconds == 0:
                self.blend = self.blend_target
                self._write_pose()

    def advance(self, dt):
        if not math.isfinite(dt) or dt < 0:
            raise ValueError('Elapsed time must be finite and non-negative')
        if self.paused:
            return
        self.phase = (self.phase + dt * self.speed) % self.duration
        self.transition_elapsed += dt
        t = min(1.0, self.transition_elapsed / self.transition_duration) if self.transition_duration else 1.0
        t = t * t * (3.0 - 2.0 * t)
        self.blend = self.blend_start + (self.blend_target - self.blend_start) * t
        self._write_pose()

    def _write_pose(self):
        time = self.first + self.phase * self.fps
        attrs = (self.clip.GetTranslationsAttr(), self.clip.GetRotationsAttr(), self.clip.GetScalesAttr())
        glide = [a.Get(self.first) for a in attrs]
        flap = [a.Get(time) for a in attrs]
        if any(x is None or len(x) != len(self.joints) for x in glide + flap):
            raise ValueError('Incomplete joint samples')
        b = self.blend
        translations = Vt.Vec3fArray([(1-b)*a+b*c for a, c in zip(glide[0], flap[0])])
        rotations = Vt.QuatfArray([Gf.Slerp(b, a, c) for a, c in zip(glide[1], flap[1])])
        scales = Vt.Vec3hArray([(1-b)*a+b*c for a, c in zip(glide[2], flap[2])])
        with Usd.EditContext(self.stage, self.layer):
            # Default-only values are independent of the global timeline.
            self.output.CreateTranslationsAttr().Set(translations)
            self.output.CreateRotationsAttr().Set(rotations)
            self.output.CreateScalesAttr().Set(scales)

    def status(self):
        return dict(name=self.name, mode=self.mode, paused=self.paused,
                    speed=self.speed, phase_seconds=self.phase,
                    duration_seconds=self.duration, flap_weight=self.blend,
                    independent_of_timeline=True)

    def close(self):
        paths = self.stage.GetSessionLayer().subLayerPaths
        if self.layer.identifier in paths:
            paths.remove(self.layer.identifier)
