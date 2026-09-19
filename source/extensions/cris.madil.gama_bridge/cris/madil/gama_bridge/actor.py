"""One opt-in actor in a removable private USD layer. No autonomous movement."""
from pathlib import Path
import secrets
from pxr import Gf, Sdf, Usd, UsdGeom
from .exchange import StepBuffer, preview_transforms

ROOT = "/MarlinGamaFixture"
ACTOR = ROOT + "/Bottlenose_001"
AGENT_ID = "Gama_Bottlenose_001"
SPECIES = "bottlenose_dolphin"
ASSET = Path(__file__).resolve().parents[6] / "assets/cetaceans/bottlenose_dolphin/usd/bottlenose_dolphin.usd"


class IsolatedActor:
    def __init__(self):
        self.stage = None
        self.layer = None
        self.token = None
        self.buffer = StepBuffer()
        self.calibration = None

    def acquire(self, stage, paused=False, profile="coastal_candidate_v1"):
        if paused:
            raise ValueError("Capture is paused/busy; ownership cannot change")
        if self.stage is not None:
            raise ValueError("Release existing ownership before acquiring again")
        if stage is None or UsdGeom.GetStageUpAxis(stage) != UsdGeom.Tokens.y:
            raise ValueError("An open Y-up stage is required")
        units = UsdGeom.GetStageMetersPerUnit(stage)
        if not 0 < units < float("inf"):
            raise ValueError("Invalid stage units")
        if stage.GetPrimAtPath(ROOT):
            raise ValueError("Integration root already exists; refusing to overwrite it")
        if not ASSET.is_file():
            raise ValueError("Allowlisted bottlenose asset is unavailable")
        source = Usd.Stage.Open(str(ASSET))
        source_prim = source.GetDefaultPrim()
        if not source_prim:
            roots = list(source.GetPseudoRoot().GetChildren())
            if len(roots) != 1:
                raise ValueError("Asset has no unambiguous reference root")
            source_prim = roots[0]
        layer = Sdf.Layer.CreateAnonymous("marlin_gama_fixture.usda")
        # Construct off-stage, then attach atomically. No inherited parent transforms.
        isolated = Usd.Stage.Open(layer)
        root = UsdGeom.Xform.Define(isolated, ROOT)
        root.GetPrim().SetCustomDataByKey("marlin:owner", "gama_fixture")
        actor = UsdGeom.Xform.Define(isolated, ACTOR)
        UsdGeom.XformCommonAPI(actor).SetTranslate(Gf.Vec3d(0, -.8 / units, 0))
        UsdGeom.XformCommonAPI(actor).SetRotate(Gf.Vec3f(0, 0, 0))
        model = UsdGeom.Xform.Define(isolated, ACTOR + "/Model")
        model.GetPrim().GetReferences().AddReference(str(ASSET), source_prim.GetPath())
        # Preserve the visually checked upright/forward correction, calibrating
        # only this owned reference. Never change the asset or gallery.
        UsdGeom.XformCommonAPI(model).SetRotate(Gf.Vec3f(-90, 0, 0))
        from .calibration import measure
        calibration = measure(model.GetPrim(), ASSET, profile)
        UsdGeom.XformCommonAPI(model).SetScale(Gf.Vec3f(calibration["scale_multiplier_relative_to_legacy"] / units))
        root.GetPrim().SetCustomDataByKey("marlin:calibration_profile", calibration["profile"])
        root.GetPrim().SetCustomDataByKey("marlin:axial_length_m", calibration["axial_length_m"])
        stage.GetSessionLayer().subLayerPaths.insert(0, layer.identifier)
        self.stage, self.layer, self.units = stage, layer, units
        self.token = secrets.token_urlsafe(24)
        self.buffer.reset()
        self.calibration = calibration
        return {"ownership_token": self.token, "actor_path": ACTOR,
                "agent_id": AGENT_ID, "species": SPECIES,
                "meters_per_scene_unit": units, "calibration": calibration}

    def _guard(self, stage, token, paused):
        if self.stage is None or token != self.token:
            raise ValueError("Explicit ownership token required")
        if paused:
            raise ValueError("Capture is paused/busy; fixture is frozen")
        if stage != self.stage:
            raise ValueError("Active stage changed; fixture is frozen")
        if (self.layer.identifier not in stage.GetSessionLayer().subLayerPaths or
                not stage.GetPrimAtPath(ACTOR)):
            raise ValueError("Owned layer/actor is missing; fixture is frozen")
        if UsdGeom.GetStageMetersPerUnit(stage) != self.units or UsdGeom.GetStageUpAxis(stage) != "Y":
            raise ValueError("Stage coordinates changed; fixture is frozen")

    def apply(self, stage, token, payload, paused=False):
        self._guard(stage, token, paused)
        transforms = preview_transforms(payload, self.units)
        if len(transforms) != 1 or transforms[0]["id"] != AGENT_ID or payload["agents"][0]["species"] != SPECIES:
            raise ValueError("Fixture accepts exactly its one allowlisted bottlenose agent")
        if payload["agents"][0]["state"] != "shallow_swim":
            raise ValueError("Only the engineering shallow_swim state is supported")
        # Validate ordering on a detached buffer before authoring anything.
        candidate = StepBuffer()
        if self.buffer.latest is not None:
            candidate.accept(self.buffer.latest)
        result = candidate.accept(payload)
        if result["duplicate"]:
            return {**result, "applied": True, "rendered": False}
        transform = transforms[0]
        before = self.layer.ExportToString()
        try:
            with Usd.EditContext(stage, self.layer):
                motion = UsdGeom.XformCommonAPI(stage.GetPrimAtPath(ACTOR))
                if not motion.SetTranslate(Gf.Vec3d(*transform["position_scene_units"])):
                    raise ValueError("Could not author actor translation")
                if not motion.SetRotate(Gf.Vec3f(0, transform["heading_deg"], 0)):
                    raise ValueError("Could not author actor heading")
                prim = stage.GetPrimAtPath(ROOT)
                prim.SetCustomDataByKey("marlin:time_s", float(payload["time_s"]))
                prim.SetCustomDataByKey("marlin:seed", str(payload["seed"]))
        except Exception:
            self.layer.ImportFromString(before)
            raise
        self.buffer.accept(payload)
        return {**result, "applied": True, "rendered": False,
                "actor_path": ACTOR, **transform}

    def release(self, token, paused=False):
        if self.stage is None or token != self.token:
            raise ValueError("Explicit ownership token required")
        if paused:
            raise ValueError("Capture is paused/busy; cannot release during capture")
        self.close()

    def close(self):
        # Operate on the saved stage, never a replacement capture/foreign stage.
        if self.stage is not None:
            paths = self.stage.GetSessionLayer().subLayerPaths
            if self.layer.identifier in paths:
                paths.remove(self.layer.identifier)
        self.stage = self.layer = self.token = None
        self.buffer.reset()
        self.calibration = None

    def status(self):
        pose = None
        if self.stage is not None and self.stage.GetPrimAtPath(ACTOR):
            matrix = UsdGeom.Xformable(self.stage.GetPrimAtPath(ACTOR)).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            pose = {"position_scene_units": list(matrix.ExtractTranslation()),
                    "forward_y_up": list(matrix.TransformDir(Gf.Vec3d(0, 0, 1)))}
        return {"owned": self.stage is not None, "actor_path": ACTOR, "world_pose": pose,
                "calibration": self.calibration,
                "accepted_steps": self.buffer.accepted_steps, "latest": self.buffer.latest,
                "motion_policy": "hold_last_state_without_updates"}
