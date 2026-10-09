"""In-memory composed-USD checks for frozen scene and camera identities.

Run with the installed Blender USD Python and -B. All scene/state inputs below
are explicitly synthetic fixtures, not captured or GAMA-generated evidence.
"""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys
import types
import unittest

from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux, UsdShade

package = types.ModuleType("_gama_paired_state_test")
package.__path__ = [str(Path(__file__).resolve().parents[1] /
    "source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge")]
sys.modules[package.__name__] = package
helper = importlib.import_module(package.__name__ + ".paired_state_v2")


class PairedStateTests(unittest.TestCase):
    def setUp(self):
        self.stage = Usd.Stage.CreateInMemory()
        UsdGeom.SetStageUpAxis(self.stage, "Y")
        UsdGeom.SetStageMetersPerUnit(self.stage, 1)
        actor = UsdGeom.Xform.Define(self.stage, helper.ACTOR_PATH)
        UsdGeom.XformCommonAPI(actor).SetTranslate(Gf.Vec3d(1, -.2, 2))
        self.mesh = UsdGeom.Mesh.Define(self.stage, helper.ACTOR_PATH + "/Model")
        self.mesh.CreatePointsAttr([(0, 0, 0), (1, 0, 0), (0, 0, 1)])
        self.mesh.CreateFaceVertexCountsAttr([3])
        self.mesh.CreateFaceVertexIndicesAttr([0, 1, 2])
        self.ocean = UsdGeom.Mesh.Define(self.stage, "/World/Ocean")
        self.ocean.CreatePointsAttr([(0, 0, 0), (1, 0, 0), (0, 0, 1)])
        self.light = UsdLux.DistantLight.Define(self.stage, "/World/Sun")
        self.light.CreateIntensityAttr(1000)
        self.material = UsdShade.Material.Define(self.stage, "/World/Looks/OceanMaterial")
        self.shader = UsdShade.Shader.Define(self.stage, "/World/Looks/OceanMaterial/Shader")
        self.shader.CreateIdAttr("UsdPreviewSurface")
        self.shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(.4)
        self.camera = UsdGeom.Camera.Define(self.stage, "/PairCamera")
        self.camera.GetFocalLengthAttr().Set(35)
        UsdGeom.XformCommonAPI(self.camera).SetTranslate(Gf.Vec3d(1, 10, 2))
        self.state = {"schema_version": "2.0", "run_id": "M6_Synthetic_Fixture", "step_index": 0,
                      "simulation_time_s": 0.0, "simulation_step_s": .5, "seed": 184729,
                      "agents": [{"agent_id": "Porpoise_001", "species": "harbour_porpoise",
                                  "behavioural_state": "surface", "horizontal_position_m": [1, 2],
                                  "heading_deg": 0, "speed_mps": .5,
                                  "vertical_reference": "mean_sea_level", "depth_m": .2}]}
        self.settings = {"/rtx/rendermode": "RaytracedLighting", "/rtx/post/motionblur/enabled": False}
        self.dependencies = [{"path": "/synthetic/porpoise.usd", "sha256": "a" * 64, "status": "local_hashed"}]
        self.clock = {"source_timeline_seconds": 0.0, "source_time_code": 0.0,
                      "ocean": {"elapsed": 3.5, "update_accumulator": .01, "amplitude": .2}}

    def record(self, **overrides):
        values = {"stage": self.stage, "source_state": self.state, "renderer_settings": self.settings,
                  "dependencies": self.dependencies, "environment_clock": self.clock}
        values.update(overrides)
        return helper.resolved_record(**values)

    def condition(self, **overrides):
        values = {"stage": self.stage, "camera_path": "/PairCamera", "gsd_cm_px": .5,
                  "anchor_m": [1, 0, 2], "reference_plane_y_m": 0, "resolution": [1280, 720]}
        values.update(overrides)
        return helper.camera_condition(**values)

    def test_identity_is_deterministic_detached_and_read_only(self):
        before = self.stage.GetRootLayer().ExportToString()
        session_before = self.stage.GetSessionLayer().ExportToString()
        original_state = deepcopy(self.state)
        first = self.record()
        self.assertEqual(first, self.record())
        self.assertEqual(first["remaining_time_samples"], 0)
        self.assertEqual(first["excluded_camera_paths"], ["/PairCamera"])
        self.assertEqual(first["identity"]["pose_mapping"], "static_pose_proxy_v1")
        self.assertEqual(first["identity"]["animation_phase"]["applicability"], "not_applicable")
        self.assertFalse(first["pixel_identical_rgb_verified"])
        first["identity"]["gama_source_state"]["agents"][0]["depth_m"] = 99
        first["identity"]["environment_clock"]["ocean"]["elapsed"] = 99
        self.assertEqual(self.state, original_state)
        self.assertEqual(self.clock["ocean"]["elapsed"], 3.5)
        self.assertEqual(self.stage.GetRootLayer().ExportToString(), before)
        self.assertEqual(self.stage.GetSessionLayer().ExportToString(), session_before)

    def test_camera_changes_and_additional_cameras_do_not_change_scene_hash(self):
        before = self.record()["resolved_scene_state_hash"]
        old_condition = self.condition()["camera_condition_hash"]
        self.camera.GetFocalLengthAttr().Set(70)
        UsdGeom.XformCommonAPI(self.camera).SetTranslate(Gf.Vec3d(10, 50, 20))
        UsdGeom.Camera.Define(self.stage, "/AnotherCamera")
        UsdGeom.Mesh.Define(self.stage, "/PairCamera/CameraOnlyHelper").CreatePointsAttr([(0, 0, 0)])
        self.assertEqual(before, self.record()["resolved_scene_state_hash"])
        self.assertNotEqual(old_condition, self.condition()["camera_condition_hash"])

    def test_render_subtree_and_camera_time_samples_are_excluded_before_static_check(self):
        before = self.record()["resolved_scene_state_hash"]
        self.camera.GetFocalLengthAttr().Set(70, Usd.TimeCode(1))
        render = UsdGeom.Xform.Define(self.stage, "/Render/Transient")
        render.GetPrim().CreateAttribute("backend:frame", Sdf.ValueTypeNames.Int).Set(9, Usd.TimeCode(1))
        self.assertEqual(before, self.record()["resolved_scene_state_hash"])
        with self.assertRaisesRegex(ValueError, "camera must be resolved"):
            self.condition()

    def test_animal_transform_mesh_ocean_light_material_and_metadata_change_hash(self):
        edits = (
            lambda: UsdGeom.XformCommonAPI(self.stage.GetPrimAtPath(helper.ACTOR_PATH)).SetTranslate(Gf.Vec3d(2, -.2, 2)),
            lambda: self.mesh.GetPointsAttr().Set([(0, 0, 0), (2, 0, 0), (0, 0, 1)]),
            lambda: self.ocean.GetPointsAttr().Set([(0, .1, 0), (1, 0, 0), (0, 0, 1)]),
            lambda: self.light.GetIntensityAttr().Set(1200),
            lambda: self.shader.GetInput("roughness").Set(.8),
            lambda: self.stage.SetStartTimeCode(4),
        )
        original = self.stage.GetRootLayer().ExportToString()
        before = self.record()["resolved_scene_state_hash"]
        for index, edit in enumerate(edits):
            with self.subTest(edit=index):
                edit()
                self.assertNotEqual(before, self.record()["resolved_scene_state_hash"])
                self.stage.GetRootLayer().ImportFromString(original)

    def test_environment_clock_renderer_source_pose_and_dependency_content_change_hash(self):
        before = self.record()["resolved_scene_state_hash"]
        clock = deepcopy(self.clock)
        clock["ocean"]["elapsed"] += .1
        settings = deepcopy(self.settings)
        settings["/rtx/rendermode"] = "PathTracing"
        state = deepcopy(self.state)
        state["agents"][0]["depth_m"] += .1
        dependencies = deepcopy(self.dependencies)
        dependencies[0]["sha256"] = "b" * 64
        for name, value in (("environment_clock", clock), ("renderer_settings", settings),
                            ("source_state", state), ("dependencies", dependencies)):
            with self.subTest(name=name):
                self.assertNotEqual(before, self.record(**{name: value})["resolved_scene_state_hash"])

    def test_dependency_order_is_canonical_and_unresolved_limit_is_explicit(self):
        dependencies = self.dependencies + [{"path": "runtime://uninspected", "sha256": None,
                                             "status": "runtime_or_unresolved"}]
        first = self.record(dependencies=dependencies)
        second = self.record(dependencies=list(reversed(dependencies)))
        self.assertEqual(first["resolved_scene_state_hash"], second["resolved_scene_state_hash"])
        self.assertEqual(first["unresolved_dependencies"], ["runtime://uninspected"])
        self.assertIn("not inspected", first["content_identity_limitation"])

    def test_remaining_time_samples_are_rejected_without_changing_source(self):
        self.mesh.GetPointsAttr().Set([(0, 0, 0), (2, 0, 0), (0, 0, 1)], Usd.TimeCode(1))
        before = self.stage.GetRootLayer().ExportToString()
        with self.assertRaisesRegex(ValueError, "zero remaining time samples"):
            self.record()
        self.assertEqual(self.stage.GetRootLayer().ExportToString(), before)

    def test_source_content_hash_preserves_animation_and_does_not_mutate_source(self):
        points = self.mesh.GetPointsAttr()
        points.Set([(0, 0, 0), (2, 0, 0), (0, 0, 1)], Usd.TimeCode(1))
        original = self.stage.GetRootLayer().ExportToString()
        first = helper.source_content_hash(self.stage)
        self.assertEqual(first, helper.source_content_hash(self.stage))
        self.assertEqual(points.GetNumTimeSamples(), 1)
        self.assertEqual(self.stage.GetRootLayer().ExportToString(), original)
        points.Set([(0, 0, 0), (3, 0, 0), (0, 0, 1)], Usd.TimeCode(1))
        self.assertNotEqual(first, helper.source_content_hash(self.stage))
        with self.assertRaisesRegex(ValueError, "zero remaining time samples"):
            self.record()

    def test_source_content_hash_excludes_camera_and_render_animation(self):
        self.mesh.GetPointsAttr().Set([(0, 0, 0), (2, 0, 0), (0, 0, 1)], Usd.TimeCode(1))
        first = helper.source_content_hash(self.stage)
        self.camera.GetFocalLengthAttr().Set(70, Usd.TimeCode(1))
        UsdGeom.XformCommonAPI(self.camera).SetTranslate(Gf.Vec3d(10, 50, 20))
        backend = UsdGeom.Xform.Define(self.stage, "/Render/Transient")
        backend.GetPrim().CreateAttribute("backend:frame", Sdf.ValueTypeNames.Int).Set(12, Usd.TimeCode(1))
        self.assertEqual(first, helper.source_content_hash(self.stage))

    def test_source_content_hash_detects_an_additional_physical_time_sample(self):
        first = helper.source_content_hash(self.stage)
        self.ocean.GetPointsAttr().Set([(0, .1, 0), (1, 0, 0), (0, 0, 1)], Usd.TimeCode(2))
        self.assertNotEqual(first, helper.source_content_hash(self.stage))

    def test_unloaded_payload_is_rejected(self):
        layer = Sdf.Layer.CreateAnonymous("synthetic_payload.usda")
        stage = Usd.Stage.Open(layer)
        UsdGeom.Cube.Define(stage, "/Cube")
        prim = self.stage.DefinePrim("/World/Payload")
        prim.GetPayloads().AddPayload(layer.identifier, "/Cube")
        self.stage.Unload("/World/Payload")
        with self.assertRaisesRegex(ValueError, "payloads must be loaded"):
            self.record()

    def test_malformed_gama_source_fails_without_mutating_stage(self):
        before = self.stage.GetRootLayer().ExportToString()
        for kind in ("unknown", "nonfinite", "two_agents", "zero_agents", "none"):
            state = deepcopy(self.state)
            if kind == "unknown":
                state["agents"][0]["absolute_y_m"] = -.2
            elif kind == "nonfinite":
                state["agents"][0]["depth_m"] = float("nan")
            elif kind == "two_agents":
                state["agents"].append(deepcopy(state["agents"][0]))
            elif kind == "zero_agents":
                state["agents"] = []
            else:
                state = None
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.record(source_state=state)
            self.assertEqual(self.stage.GetRootLayer().ExportToString(), before)

    def test_missing_actor_wrong_units_or_axis_are_rejected(self):
        for change in (lambda: self.stage.RemovePrim(helper.ACTOR_PATH),
                       lambda: UsdGeom.SetStageUpAxis(self.stage, "Z"),
                       lambda: UsdGeom.SetStageMetersPerUnit(self.stage, 0)):
            original = self.stage.GetRootLayer().ExportToString()
            change()
            with self.assertRaises(ValueError):
                self.record()
            self.stage.GetRootLayer().ImportFromString(original)

    def test_nonfinite_json_metadata_bad_dependencies_and_unsupported_values_rejected(self):
        for name, value in (("renderer_settings", {"bad": float("inf")}),
                            ("environment_clock", {"time": float("nan")}),
                            ("renderer_settings", {1: "not_a_string_key"}),
                            ("environment_clock", object()),
                            ("dependencies", [{"path": "a", "sha256": "bad"}]),
                            ("dependencies", [{"path": "a", "sha256": None}]),
                            ("dependencies", self.dependencies * 2)):
            with self.subTest(name=name, value=str(value)), self.assertRaises(ValueError):
                self.record(**{name: value})

    def test_camera_condition_records_composed_parent_transform_and_actual_optics(self):
        parent = UsdGeom.Xform.Define(self.stage, "/CameraParent")
        UsdGeom.XformCommonAPI(parent).SetTranslate(Gf.Vec3d(3, 4, 5))
        camera = UsdGeom.Camera.Define(self.stage, "/CameraParent/Camera")
        UsdGeom.XformCommonAPI(camera).SetTranslate(Gf.Vec3d(1, 2, 3))
        camera.GetFocalLengthAttr().Set(50)
        condition = self.condition(camera_path="/CameraParent/Camera")
        self.assertEqual(condition["camera_condition"]["composed_camera_matrix"][3][:3], [4, 6, 8])
        self.assertEqual(condition["camera_condition"]["focal_length"], 50)
        self.assertEqual(condition["camera_condition"]["resolution_px"], [1280, 720])
        self.assertFalse(condition["actual_render_product_camera_verified"])

    def test_camera_condition_hash_tracks_camera_conditions_only(self):
        before = self.condition()["camera_condition_hash"]
        for arguments in ({"gsd_cm_px": 1}, {"anchor_m": [2, 0, 2]},
                          {"reference_plane_y_m": -1}, {"resolution": [640, 360]}):
            self.assertNotEqual(before, self.condition(**arguments)["camera_condition_hash"])
        self.light.GetIntensityAttr().Set(2000)
        self.assertEqual(before, self.condition()["camera_condition_hash"])

    def test_camera_exposure_changes_condition_but_not_frozen_scene_identity(self):
        scene_hash = self.record()["resolved_scene_state_hash"]
        condition_hash = self.condition()["camera_condition_hash"]
        exposure = self.camera.GetPrim().CreateAttribute("exposure:fStop", Sdf.ValueTypeNames.Float)
        exposure.Set(5)
        self.camera.GetPrim().CreateAttribute("rtx:exposureBias", Sdf.ValueTypeNames.Double).Set(1.5)
        first = self.condition()
        self.assertNotEqual(condition_hash, first["camera_condition_hash"])
        self.assertEqual(first["camera_condition"]["authored_exposure_attributes"], {"exposure:fStop": 5, "rtx:exposureBias": 1.5})
        exposure.Set(8)
        self.assertNotEqual(first["camera_condition_hash"], self.condition()["camera_condition_hash"])
        self.assertEqual(scene_hash, self.record()["resolved_scene_state_hash"])

    def test_nonfinite_or_nonnumeric_camera_exposure_is_rejected(self):
        prim = self.camera.GetPrim()
        prim.CreateAttribute("exposure:time", Sdf.ValueTypeNames.Double).Set(float("nan"))
        with self.assertRaises(ValueError):
            self.condition()
        prim.RemoveProperty("exposure:time")
        prim.CreateAttribute("rtx:invalidExposure", Sdf.ValueTypeNames.String).Set("invalid")
        with self.assertRaises(ValueError):
            self.condition()

    def test_camera_condition_rejects_invalid_conditions_read_only(self):
        before = self.stage.GetRootLayer().ExportToString()
        for arguments in ({"camera_path": "/Missing"}, {"camera_path": helper.ACTOR_PATH},
                          {"gsd_cm_px": True}, {"gsd_cm_px": float("inf")},
                          {"anchor_m": [1, 2]}, {"anchor_m": [1, False, 2]},
                          {"reference_plane_y_m": float("nan")}, {"resolution": [1280, 0]}):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                self.condition(**arguments)
            self.assertEqual(self.stage.GetRootLayer().ExportToString(), before)

    def test_all_records_are_finite_json_serializable(self):
        for value in (self.record(), self.condition()):
            self.assertEqual(json.loads(json.dumps(value, allow_nan=False)), value)


if __name__ == "__main__":
    unittest.main()
