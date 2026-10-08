"""One record-driven porpoise; shares the existing removable-layer lifecycle."""
import hashlib
import json
import math
import time

from pxr import Gf, Sdf, Usd, UsdGeom
from .actor import IsolatedActor, ASSET as LEGACY_ASSET
from .exchange import IDENTIFIER
from .exchange_v2 import StepBuffer, preview_transforms
from .stage_coordinates import inspect_stage

ROOT = "/MarlinGamaPorpoise"
ACTOR = ROOT + "/Porpoise_001"
REPO = LEGACY_ASSET.parents[4]
CALIBRATION = REPO / "experiments/gsd_pilot_v1/wildlife/harbour_porpoise.json"
ASSET = REPO / "assets/cetaceans/model_75a_-_harbor_porpoise/working/calibration_v1/usd/harbour_porpoise_static_candidate.usd"
MISSING_UPDATE_AFTER_S = 2.0
_SAVED_STAGE = object()


class PorpoiseActor(IsolatedActor):
    root_path, actor_path = ROOT, ACTOR
    agent_id = "Porpoise_001"
    species, asset = "harbour_porpoise", ASSET
    initial_depth_m = .2

    def __init__(self):
        super().__init__()
        self.buffer = StepBuffer()
        self.last_received = None
        self.expected_matrix = None

    def acquire(self, stage, agent_id, paused=False):
        if not isinstance(agent_id, str) or not IDENTIFIER.fullmatch(agent_id):
            raise ValueError("agent_id must be a safe identifier")
        coordinates = inspect_stage(stage)
        if not coordinates["suitable_for_v2"]:
            raise ValueError("; ".join(coordinates["rejection_reasons"]))
        if self.stage is not None:
            raise ValueError("Release existing ownership before acquiring again")
        self.agent_id = agent_id
        result = super().acquire(stage, paused)
        self.last_received = None
        self.expected_matrix = self._matrix(stage.GetPrimAtPath(ACTOR))
        return {**result, "pose_mapping": "static_pose_proxy_v1",
                "motion_policy": "freeze_and_report",
                "missing_update_after_s": MISSING_UPDATE_AFTER_S}

    def _calibrate(self, model, units, profile):
        record = json.loads(CALIBRATION.read_text())
        if record["asset"]["path"] != str(self.asset.relative_to(REPO)):
            raise ValueError("Recorded porpoise asset differs from the allowlist")
        for dependency in record["asset"]["dependencies"]:
            path = REPO / dependency["path"]
            if hashlib.sha256(path.read_bytes()).hexdigest() != dependency["sha256"]:
                raise ValueError("Recorded porpoise asset dependency hash changed")
        spawn = record["spawn"]
        UsdGeom.XformCommonAPI(model).SetRotate(Gf.Vec3f(*spawn["model_rotation"]))
        UsdGeom.XformCommonAPI(model).SetScale(Gf.Vec3f(spawn["metres_per_native_unit"] / units))
        root = model.GetPrim().GetStage().GetPrimAtPath(ROOT)
        root.SetCustomDataByKey("marlin:owner", "gama_v2")
        root.SetCustomDataByKey("marlin:pose_mapping", "static_pose_proxy_v1")
        return {"profile": record["calibration_id"],
                "axial_length_m": record["geometry"]["corrected_metric_bounds_relative_to_root"]["dimensions_xyz"][2],
                "record": str(CALIBRATION), "asset_sha256": record["asset"]["sha256"],
                "biological_calibration_verified": False,
                "pose_mapping": "static_pose_proxy_v1",
                "pose_note": "All five labels use the existing static upright mesh; no dive pitch, rig animation or breathing pose is claimed"}

    def _guard(self, stage, token, paused):
        super()._guard(stage, token, paused)
        if not inspect_stage(stage)["suitable_for_v2"]:
            raise ValueError("Explicit stage coordinates changed; porpoise is frozen")
        self._require_matrix(self._matrix(stage.GetPrimAtPath(ROOT)), Gf.Matrix4d(1), "Owned parent transform changed")
        self._require_matrix(self._matrix(stage.GetPrimAtPath(ACTOR)), self.expected_matrix, "Owned composed transform was overridden")

    @staticmethod
    def _matrix(prim):
        return UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())

    @staticmethod
    def _require_matrix(actual, expected, message):
        if expected is None or any(not math.isfinite(actual[i][j]) or abs(actual[i][j] - expected[i][j]) > 1e-10 for i in range(4) for j in range(4)):
            raise ValueError(message + "; porpoise is frozen")

    def apply(self, stage, token, payload, paused=False):
        self._guard(stage, token, paused)
        transform = preview_transforms(payload, self.units)[0]
        if transform["id"] != self.agent_id:
            raise ValueError("Unknown agent: this ownership is bound to one agent_id")
        candidate = StepBuffer()
        if self.buffer.latest is not None:
            candidate.accept(self.buffer.latest)
        result = candidate.accept(payload)
        if result["duplicate"]:
            self.last_received = time.monotonic()
            return {**result, "applied": True, "actor_path": ACTOR}
        before = self.layer.ExportToString()
        heading = float(Gf.Vec3f(0, transform["heading_deg"], 0)[1])
        expected = Gf.Matrix4d(1).SetRotate(Gf.Rotation(Gf.Vec3d(0, 1, 0), heading))
        expected.SetTranslateOnly(Gf.Vec3d(*transform["position_scene_units"]))
        try:
            with Usd.EditContext(stage, self.layer):
                motion = UsdGeom.XformCommonAPI(stage.GetPrimAtPath(ACTOR))
                if not motion.SetTranslate(Gf.Vec3d(*transform["position_scene_units"])):
                    raise ValueError("Could not author porpoise translation")
                if not motion.SetRotate(Gf.Vec3f(0, transform["heading_deg"], 0)):
                    raise ValueError("Could not author porpoise heading")
                root = stage.GetPrimAtPath(ROOT)
                for key in ("run_id", "step_index", "simulation_time_s", "seed"):
                    root.SetCustomDataByKey("marlin:" + key, str(payload[key]))
                root.SetCustomDataByKey("marlin:behavioural_state", payload["agents"][0]["behavioural_state"])
            self._require_matrix(self._matrix(stage.GetPrimAtPath(ACTOR)), expected, "USD composition did not apply the requested pose")
        except Exception:
            self.layer.ImportFromString(before)
            raise
        self.buffer.accept(payload)
        self.expected_matrix = expected
        self.last_received = time.monotonic()
        return {**result, "applied": True, "actor_path": ACTOR, **transform,
                "pose_mapping": "static_pose_proxy_v1"}

    def reset(self, stage, token, paused=False):
        self._guard(stage, token, paused)
        self.buffer.reset()
        self.last_received = None
        # Hold the composed pose. A different run requires another explicit step.

    def cleanup_empty_root(self, stage, paused=False):
        """Explicit repair for diagnostic placeholders left by viewport camera UI.

        Only an empty over, optionally containing the diagnostic camera's
        allowlisted RTX exposure overrides, qualifies. No defined camera or
        animal can be removed. This cannot take over a scene actor.
        """
        if paused or self.stage is not None or stage is None:
            raise ValueError("Cleanup requires an unowned active stage outside capture")
        prim = stage.GetPrimAtPath(ROOT)
        if not prim:
            return {"removed": False}
        stack = prim.GetPrimStack()
        if len(stack) != 1:
            raise ValueError("Refusing to remove a composed/nonempty private root")
        spec = stack[0]
        from .visual_v2 import _is_diagnostic_camera_over
        children = list(spec.nameChildren.values())
        safe_camera_child = (len(children) == 1 and children[0].name == "DiagnosticCamera"
                             and _is_diagnostic_camera_over(children[0]))
        if (spec.layer != stage.GetRootLayer() or spec.specifier != Sdf.SpecifierOver or
                set(spec.ListInfoKeys()) != {"specifier"} or len(spec.properties) or spec.variantSets or
                (children and not safe_camera_child)):
            raise ValueError("Refusing to remove any authored private-root content")
        edit = Sdf.BatchNamespaceEdit()
        edit.Add(ROOT, Sdf.Path.emptyPath)
        layer = spec.layer
        if not layer.Apply(edit):
            raise ValueError("Could not remove the empty diagnostic ancestor")
        return {"removed": True, "path": ROOT, "layer": layer.identifier}

    def status(self, stage=_SAVED_STAGE, paused=False):
        result = super().status()
        inspected_stage = self.stage if stage is _SAVED_STAGE else stage
        root = inspected_stage.GetPrimAtPath(ROOT) if inspected_stage is not None else None
        root_diagnostics = None if not root else {
            "children": [str(p.GetPath()) for p in root.GetChildren()],
            "opinions": [{"layer": spec.layer.identifier, "specifier": str(spec.specifier),
                          "type_name": spec.typeName, "custom_data": dict(spec.customData),
                          "fields": list(spec.ListInfoKeys()), "properties": list(spec.properties.keys()),
                          "children": list(spec.nameChildren.keys()),
                          "diagnostic_camera": ({"fields": {k: str(spec.nameChildren["DiagnosticCamera"].GetInfo(k)) for k in spec.nameChildren["DiagnosticCamera"].ListInfoKeys()},
                                                 "properties": list(spec.nameChildren["DiagnosticCamera"].properties.keys()),
                                                 "children": list(spec.nameChildren["DiagnosticCamera"].nameChildren.keys())}
                                                if "DiagnosticCamera" in spec.nameChildren else None)}
                         for spec in root.GetPrimStack()]}
        elapsed = None if self.last_received is None else max(0, time.monotonic() - self.last_received)
        transport = "unowned"
        error = None
        if self.stage is not None:
            try:
                self._guard(self.stage if stage is _SAVED_STAGE else stage, self.token, paused)
                transport = ("awaiting_first_update" if elapsed is None else
                             "frozen_updates_missing" if elapsed > MISSING_UPDATE_AFTER_S else "holding_last_state")
            except ValueError as failure:
                transport, error = "frozen_guard_failure", str(failure)
        return {**result, "agent_id": self.agent_id, "species": self.species,
                "actor_count": int(self.stage is not None and bool(self.stage.GetPrimAtPath(ACTOR))),
                "root_present_on_active_stage": bool(root), "root_diagnostics": root_diagnostics,
                "motion_policy": "freeze_and_report", "transport_state": transport,
                "seconds_since_update": elapsed, "missing_update_after_s": MISSING_UPDATE_AFTER_S,
                "guard_error": error, "autonomous_controller": False,
                "pose_mapping": "static_pose_proxy_v1"}

    def close(self):
        super().close()
        self.last_received = None
        self.expected_matrix = None
