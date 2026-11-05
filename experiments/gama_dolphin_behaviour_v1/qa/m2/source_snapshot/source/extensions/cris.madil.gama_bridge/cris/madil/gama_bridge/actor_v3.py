"""Explicit-time Model 61A ownership. No timeline or update subscription."""
from copy import deepcopy
import hashlib
import json
import math
import time

from pxr import Gf, Usd, UsdGeom
from .actor import IsolatedActor, ASSET as LEGACY_ASSET
from .exchange_v2 import _identifier
from .exchange_v3 import StepBuffer
from .stage_coordinates import inspect_stage

REPO = LEGACY_ASSET.parents[4]
CONFIG = REPO / 'source/extensions/cris.madil.gama_bridge/config/model61a_engineering_v1.json'
ROOT = '/MarlinGamaBottlenose'
ACTOR = ROOT + '/Bottlenose_001'
MISSING_UPDATE_AFTER_S = 2.0


def matrix_for(frame, units):
    a = frame['agent']
    # USD row vectors: local roll, nose-up pitch, then world heading.
    matrix = (Gf.Matrix4d(1).SetRotate(Gf.Rotation(Gf.Vec3d(0, 0, 1), a['roll_deg'])) *
              Gf.Matrix4d(1).SetRotate(Gf.Rotation(Gf.Vec3d(1, 0, 0), -a['pitch_deg'])) *
              Gf.Matrix4d(1).SetRotate(Gf.Rotation(Gf.Vec3d(0, 1, 0), a['heading_deg'])))
    x, z = a['horizontal_position_m']
    matrix.SetTranslateOnly(Gf.Vec3d(x / units, -a['depth_m'] / units, z / units))
    return matrix


def _value(value):
    if isinstance(value, (str, bool, int, float, type(None))):
        return value
    try:
        return [_value(v) for v in value]
    except TypeError:
        return str(value)


def _fingerprint_value(value):
    # Mesh arrays expose a buffer: hash all bytes without repeatedly expanding
    # tens of thousands of unchanged vertices through Python/JSON.
    try:
        view = memoryview(value)
        return {'buffer_sha256': hashlib.sha256(view.tobytes()).hexdigest(),
                'format': view.format, 'shape': list(view.shape)}
    except TypeError:
        return _value(value)


class BottlenoseActor(IsolatedActor):
    root_path, actor_path = ROOT, ACTOR
    species = 'bottlenose_dolphin'
    asset = REPO / 'assets/cetaceans/model_61a_-_bottlenose_dolphin/usd/model_61a_-_bottlenose_dolphin.usd'
    initial_depth_m = .2

    def __init__(self):
        super().__init__()
        self.buffer = StepBuffer()
        self.last_received = self.expected_matrix = self.expected_body = None
        self.expected_layer = self.frame = None
        self.paused = False

    def _calibrate(self, model, units, profile):
        record = json.loads(CONFIG.read_text())
        if record['asset'] != str(self.asset.relative_to(REPO)):
            raise ValueError('Engineering profile asset differs from allowlist')
        for dependency in record['dependencies']:
            if hashlib.sha256((REPO / dependency['path']).read_bytes()).hexdigest() != dependency['sha256']:
                raise ValueError('Model 61A dependency changed: ' + dependency['path'])
        api = UsdGeom.XformCommonAPI(model)
        api.SetRotate(Gf.Vec3f(*record['model_rotation_deg_xyz']))
        api.SetScale(Gf.Vec3f(record['meters_per_native_unit'] / units))
        return {k: v for k, v in record.items() if k != 'dependencies'}

    def acquire(self, stage, agent_id, paused=False):
        _identifier(agent_id, 'agent_id')
        if self.stage is not None:
            raise ValueError('Release existing ownership before acquiring again')
        coordinates = inspect_stage(stage)
        if not coordinates['suitable_for_v2']:
            raise ValueError('; '.join(coordinates['rejection_reasons']))
        self.agent_id = agent_id
        result = super().acquire(stage, paused)
        try:
            self.expected_matrix = self._matrix(stage.GetPrimAtPath(ACTOR))
            with Usd.EditContext(stage, self.layer):
                motion = UsdGeom.Xformable(stage.GetPrimAtPath(ACTOR))
                motion.ClearXformOpOrder()
                motion.AddTransformOp(UsdGeom.XformOp.PrecisionDouble).Set(self.expected_matrix)
                stage.GetPrimAtPath(ROOT).SetCustomDataByKey('marlin:owner', 'gama_v3')
            self.expected_body = self._body_signature()
            self.expected_layer = self.layer.ExportToString()
        except Exception:
            self.close()
            raise
        return {**result, 'body_pose_mapping': 'static_rest_pose_m2', 'rendered': False}

    @staticmethod
    def _matrix(prim):
        return UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())

    def _body_signature(self):
        records = []
        for prim in Usd.PrimRange(self.stage.GetPrimAtPath(ACTOR + '/Model')):
            attrs = []
            for attr in prim.GetAttributes():
                times = attr.GetTimeSamples()
                if times:
                    raise ValueError('Time-sampled body attribute conflicts with static M2 ownership')
                attrs.append((attr.GetName(), str(attr.GetTypeName()), _fingerprint_value(attr.Get())))
            relations = [(r.GetName(), [str(p) for p in r.GetTargets()]) for r in prim.GetRelationships()]
            if any(name == 'skel:animationSource' and targets for name, targets in relations):
                raise ValueError('Bound skeletal animation conflicts with static M2 ownership')
            records.append((str(prim.GetPath()), str(prim.GetTypeName()), prim.IsActive(), attrs, relations))
        return hashlib.sha256(json.dumps(records, sort_keys=True, allow_nan=False).encode()).hexdigest()

    def _guard(self, stage, token, paused):
        super()._guard(stage, token, paused)
        if not inspect_stage(stage)['suitable_for_v2']:
            raise ValueError('Explicit stage coordinates changed; actor is frozen')
        if self.layer.ExportToString() != self.expected_layer:
            raise ValueError('Owned layer changed outside the owner; actor is frozen')
        for path, expected in ((ROOT, Gf.Matrix4d(1)), (ACTOR, self.expected_matrix)):
            prim = stage.GetPrimAtPath(path)
            if any(attr.GetTimeSamples() for attr in prim.GetAttributes()):
                raise ValueError('Time-sampled motion writer detected; actor is frozen')
            actual = self._matrix(prim)
            if any(not math.isfinite(actual[i][j]) or abs(actual[i][j]-expected[i][j]) > 1e-10
                   for i in range(4) for j in range(4)):
                raise ValueError('Competing composed transform writer detected; actor is frozen')
        if self._body_signature() != self.expected_body:
            raise ValueError('Competing model calibration/body writer detected; actor is frozen')

    def _ready(self, stage, token, paused):
        self._guard(stage, token, paused)
        if self.paused:
            raise ValueError('Owner is paused; pose and phase held')

    def _write(self, stage, frame):
        expected = matrix_for(frame, self.units)
        if any(not math.isfinite(expected[i][j]) for i in range(4) for j in range(4)):
            raise ValueError('Resolved scene transform exceeds finite numeric range')
        before = self.layer.ExportToString()
        try:
            with Usd.EditContext(stage, self.layer):
                if not stage.GetPrimAtPath(ACTOR).GetAttribute('xformOp:transform').Set(expected):
                    raise ValueError('Could not write root transform')
                stage.GetPrimAtPath(ROOT).SetCustomDataByKey('marlin:evaluation', json.dumps(frame, sort_keys=True))
            actual = self._matrix(stage.GetPrimAtPath(ACTOR))
            if any(abs(actual[i][j]-expected[i][j]) > 1e-10 for i in range(4) for j in range(4)):
                raise ValueError('USD composition did not apply requested root pose')
        except Exception:
            self.layer.ImportFromString(before)
            raise
        self.expected_matrix, self.frame = expected, deepcopy(frame)
        self.expected_layer = self.layer.ExportToString()

    def apply(self, stage, token, payload, paused=False):
        self._ready(stage, token, paused)
        candidate = deepcopy(self.buffer)
        result = candidate.accept(payload)
        if candidate.latest['agents'][0]['agent_id'] != self.agent_id:
            raise ValueError('Ownership is bound to a different agent_id')
        if not result['duplicate']:
            self._write(stage, candidate.evaluate(candidate.latest['simulation_time_s']))
            self.buffer = candidate
        self.last_received = time.monotonic()
        return {**result, 'applied': not result['duplicate'], 'frame': deepcopy(self.frame)}

    def evaluate(self, stage, token, seconds, paused=False):
        self._ready(stage, token, paused)
        frame = self.buffer.evaluate(seconds)
        self._write(stage, frame)
        return {'frame': deepcopy(frame), 'rendered': False}

    def set_paused(self, stage, token, value, paused=False):
        self._guard(stage, token, paused)
        if type(value) is not bool:
            raise ValueError('paused must be a boolean')
        self.paused = value
        return {'paused': value, 'pose_held': True, 'phase_held': True}

    def reset(self, stage, token, paused=False):
        self._guard(stage, token, paused)
        self.buffer.reset()
        self.last_received = None
        return {'reset': True, 'pose_held': True, 'phase_held': True, 'paused': self.paused}

    def status(self, stage=None, paused=False):
        result = super().status()
        transport, error = 'unowned', None
        elapsed = None if self.last_received is None else max(0, time.monotonic()-self.last_received)
        if self.stage is not None:
            try:
                self._guard(stage, self.token, paused)
                transport = ('paused' if self.paused else 'awaiting_first_update' if elapsed is None else
                             'frozen_updates_missing' if elapsed > MISSING_UPDATE_AFTER_S else 'holding_last_state')
            except ValueError as failure:
                transport, error = 'frozen_guard_failure', str(failure)
        return {**result, 'transport_state': transport, 'guard_error': error,
                'seconds_since_update': elapsed, 'missing_update_after_s': MISSING_UPDATE_AFTER_S,
                'paused': self.paused, 'frame': deepcopy(self.frame),
                'composed_matrix': _value(self._matrix(self.stage.GetPrimAtPath(ACTOR)))
                    if self.stage is not None and self.stage.GetPrimAtPath(ACTOR) else None,
                'body_fingerprint': self.expected_body, 'body_pose_mapping': 'static_rest_pose_m2',
                'autonomous_controller': False, 'update_subscription_count': 0, 'rendered': False}

    def close(self):
        super().close()
        self.last_received = self.expected_matrix = self.expected_body = None
        self.expected_layer = self.frame = None
        self.paused = False
