"""Synthetic in-memory USD tests for target removal and direct amodal labels.

These scenes are deliberately simple fixtures, not GAMA or rendering evidence.
Run with the installed Blender USD Python and -B; no Kit process is contacted.
"""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys
import types
import unittest

from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge"
SERVICE = ROOT / "source/extensions/cris.madil.render_service/cris/madil/render_service"


def package(name, path):
    module = types.ModuleType(name)
    module.__path__ = [str(path)]
    sys.modules[name] = module
    return name


dataset = importlib.import_module(package("_gama_dataset_test", BRIDGE) + ".dataset_state_v2")
paired = importlib.import_module("_gama_dataset_test.paired_state_v2")
geometry = importlib.import_module(package("_gama_dataset_geometry", SERVICE) + ".calibration_geometry")
projection_module = importlib.import_module("_gama_dataset_geometry.capture_projection")
for name, path in (("cris", SERVICE), ("cris.madil", SERVICE), ("cris.madil.render_service", SERVICE)):
    if name not in sys.modules:
        package(name, path)
sys.modules["cris.madil.render_service.capture_projection"] = projection_module


class DatasetStateTests(unittest.TestCase):
    def setUp(self):
        self.stage = Usd.Stage.CreateInMemory()
        UsdGeom.SetStageUpAxis(self.stage, "Y")
        UsdGeom.SetStageMetersPerUnit(self.stage, 1)
        self.actor = UsdGeom.Xform.Define(self.stage, dataset.TARGET_ACTOR)
        UsdGeom.XformCommonAPI(self.actor).SetTranslate(Gf.Vec3d(1, -1, 2))
        self.mesh = UsdGeom.Mesh.Define(self.stage, dataset.TARGET_ACTOR + "/Model")
        self.mesh.CreatePointsAttr([(-1, 0, -.5), (-1, 0, .5), (1, 0, .5), (1, 0, -.5)])
        self.mesh.CreateFaceVertexCountsAttr([4]); self.mesh.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
        self.ocean = UsdGeom.Mesh.Define(self.stage, "/World/Ocean")
        self.ocean.CreatePointsAttr([(0, 0, 0), (1, 0, 0), (0, 0, 1)])
        self.other = UsdGeom.Mesh.Define(self.stage, "/World/Cetaceans/UnrelatedAnimal")
        self.other.CreatePointsAttr([(0, 0, 0), (1000, 0, 0), (0, 0, 1000)])
        self.light = UsdLux.DistantLight.Define(self.stage, "/World/Sun")
        self.light.CreateIntensityAttr(1000)
        self.config = geometry.CalibrationConfig(meters_per_scene_unit=1, image_width_px=640,
            image_height_px=480, focal_length_mm=50, pixel_pitch_um=5,
            height_above_target_m=100, target_width_m=2, target_height_m=1, target_plane_y_m=-1)
        self.camera = geometry.build_camera(self.stage, self.config, "/CaptureCamera", (1, 0, 2))
        self.state = {"schema_version": "2.0", "run_id": "M7_Synthetic_Fixture", "step_index": 0,
            "simulation_time_s": 0, "simulation_step_s": .5, "seed": 184729,
            "agents": [{"agent_id": "Porpoise_001", "species": "harbour_porpoise", "behavioural_state": "surface",
                "horizontal_position_m": [1, 2], "heading_deg": 0, "speed_mps": .5,
                "vertical_reference": "mean_sea_level", "depth_m": 1}]}
        self.renderer = {"/rtx/rendermode": "RaytracedLighting"}
        self.deps = [{"path": "/synthetic/porpoise_texture.png", "sha256": "a" * 64, "status": "local_hashed"}]
        self.clock = {"source_timeline_seconds": 0, "ocean": {"elapsed": 3}}

    def prepare(self):
        return dataset.prepare_variants(self.stage, self.state, self.renderer, self.deps, self.clock)

    def background(self, stage=None, **overrides):
        args = {"stage": stage or self.stage, "state": self.state, "renderer": self.renderer,
                "deps": self.deps, "clock": self.clock}
        args.update(overrides)
        return dataset.background_record(**args)["background_hash"]

    def projection(self, stage=None):
        stage = stage or self.stage
        return {**projection_module.image_projection(stage, "/CaptureCamera", (640, 480), Usd.TimeCode.Default()),
                "render_product": {"camera": "/CaptureCamera"}, "actual_viewport_resolution": [640, 480]}

    def test_positive_record_preserves_exact_m6_identity(self):
        actual = self.prepare()["present_record"]
        expected = paired.resolved_record(self.stage, self.state, self.renderer, self.deps, self.clock)
        self.assertEqual(actual, expected)

    def test_private_target_removal_leaves_original_and_other_animals_unchanged(self):
        original = self.stage.GetRootLayer().ExportToString()
        value = self.prepare()
        absent = value["absent_stage"]
        self.assertIsNot(absent, self.stage)
        self.assertFalse(absent.GetPrimAtPath(dataset.TARGET_ROOT))
        self.assertTrue(self.stage.GetPrimAtPath(dataset.TARGET_ACTOR))
        self.assertTrue(absent.GetPrimAtPath(self.other.GetPath()))
        self.assertEqual(self.stage.GetRootLayer().ExportToString(), original)
        removal = value["removal_record"]
        self.assertEqual(removal["operation"], "RemovePrim")
        self.assertEqual(removal["before_target_mesh_count"], 1)
        self.assertEqual(removal["after_target_mesh_count"], 0)
        self.assertEqual(set(removal["before_root_paths"]) - set(removal["after_root_paths"]), {dataset.TARGET_ROOT})

    def test_negative_identity_binds_source_parent_and_exact_removal(self):
        value = self.prepare()
        negative = value["absent_record"]
        self.assertNotEqual(negative["resolved_scene_state_hash"], value["present_record"]["resolved_scene_state_hash"])
        self.assertEqual(negative["identity"]["gama_source_state"], self.state)
        self.assertEqual(negative["identity"]["parent_positive_scene_state_hash"], value["present_record"]["resolved_scene_state_hash"])
        self.assertEqual(negative["identity"]["removal_operation"]["prim_path"], dataset.TARGET_ROOT)
        self.assertEqual(negative["identity"]["dependencies"], self.deps)
        self.assertFalse(negative["identity"]["biological_approval"])
        self.assertEqual(negative["background_hash"], value["background_hash"])

    def test_background_identity_is_equal_with_common_target_dependency_records(self):
        value = self.prepare()
        self.assertEqual(self.background(), self.background(value["absent_stage"]))
        self.assertEqual(value["background_hash"], self.background())
        self.assertNotEqual(self.background(value["absent_stage"]), self.background(value["absent_stage"], deps=[]))

    def test_background_excludes_target_and_camera_but_detects_unrelated_scene_edits(self):
        before = self.background()
        UsdGeom.XformCommonAPI(self.actor).SetTranslate(Gf.Vec3d(9, -1, 4))
        self.camera.GetFocalLengthAttr().Set(70)
        self.assertEqual(before, self.background())
        self.ocean.GetPointsAttr().Set([(0, .2, 0), (1, 0, 0), (0, 0, 1)])
        self.assertNotEqual(before, self.background())

    def test_background_clock_settings_and_dependency_changes_are_detected(self):
        before = self.background()
        for arguments in ({"clock": {"source_timeline_seconds": 1}},
                          {"renderer": {"/rtx/rendermode": "PathTracing"}},
                          {"deps": [{**self.deps[0], "sha256": "b" * 64}]}):
            self.assertNotEqual(before, self.background(**arguments))

    def test_hidden_or_inactive_present_target_cannot_be_declared_removed(self):
        UsdGeom.Imageable(self.actor).GetVisibilityAttr().Set("invisible")
        with self.assertRaisesRegex(ValueError, "physically remove"):
            dataset.variant_record(self.stage, self.state, self.renderer, self.deps, self.clock, False, "a" * 64)
        self.stage.GetPrimAtPath(dataset.TARGET_ROOT).SetActive(False)
        with self.assertRaisesRegex(ValueError, "physically remove"):
            dataset.variant_record(self.stage, self.state, self.renderer, self.deps, self.clock, False, "a" * 64)

    def test_negative_requires_valid_parent_hash_and_physical_target_absence(self):
        value = self.prepare()
        for parent in (None, "bad", True):
            with self.subTest(parent=parent), self.assertRaises(ValueError):
                dataset.variant_record(value["absent_stage"], self.state, self.renderer, self.deps, self.clock, False, parent)

    def test_animated_physical_geometry_and_malformed_state_are_rejected_read_only(self):
        self.ocean.GetPointsAttr().Set([(0, .2, 0), (1, 0, 0), (0, 0, 1)], Usd.TimeCode(1))
        before = self.stage.GetRootLayer().ExportToString()
        with self.assertRaisesRegex(ValueError, "zero remaining"):
            self.prepare()
        bad = deepcopy(self.state); bad["agents"][0]["depth_m"] = float("nan")
        with self.assertRaises(ValueError):
            dataset.prepare_variants(self.stage, bad, self.renderer, self.deps, self.clock)
        self.assertEqual(before, self.stage.GetRootLayer().ExportToString())

    def test_actual_camera_amodal_box_and_class_zero_yolo_are_correct(self):
        value = dataset.annotation(self.stage, self.projection(), self.state, True)
        label = value["annotation"]
        for actual, expected in zip(label["amodal_bbox_xyxy_px"], [220, 190, 420, 290]):
            self.assertAlmostEqual(actual, expected, places=4)
        self.assertEqual(label["vertex_count"], 4)
        self.assertEqual(label["mesh_paths"], [str(self.mesh.GetPath())])
        self.assertEqual(label["rendered_visibility"], "unknown")
        self.assertFalse(label["biological_approval"])
        self.assertEqual(label["original_gama_depth_m"], 1)
        self.assertIsNone(label["visible_mask"])
        parts = value["yolo_label"].split()
        self.assertEqual(parts[0], "0")
        for actual, expected in zip(map(float, parts[1:]), [.5, .5, 200 / 640, 100 / 480]):
            self.assertAlmostEqual(actual, expected, places=6)

    def test_composed_parent_mesh_scale_is_applied_to_vertex_projection(self):
        UsdGeom.XformCommonAPI(self.mesh).SetScale(Gf.Vec3f(2, 1, 1))
        label = dataset.annotation(self.stage, self.projection(), self.state, True)["annotation"]
        self.assertAlmostEqual(label["amodal_bbox_coco_xywh_px"][2], 400, places=4)
        self.assertAlmostEqual(label["world_bounds_max_m"][0] - label["world_bounds_min_m"][0], 4)

    def test_image_clipping_uses_actual_clipped_box_for_yolo(self):
        UsdGeom.XformCommonAPI(self.actor).SetTranslate(Gf.Vec3d(4, -1, 2))
        value = dataset.annotation(self.stage, self.projection(), self.state, True)
        label = value["annotation"]
        self.assertTrue(label["bbox_clipped_to_image"])
        self.assertAlmostEqual(label["amodal_bbox_xyxy_px"][2], 640)
        self.assertAlmostEqual(label["amodal_bbox_coco_xywh_px"][2], 120, places=4)
        self.assertAlmostEqual(float(value["yolo_label"].split()[3]), 120 / 640, places=6)

    def test_out_of_frame_target_remains_physically_present_with_empty_label(self):
        UsdGeom.XformCommonAPI(self.actor).SetTranslate(Gf.Vec3d(20, -1, 2))
        value = dataset.annotation(self.stage, self.projection(), self.state, True)
        self.assertTrue(value["annotation"]["target_present"])
        self.assertFalse(value["annotation"]["intersects_image"])
        self.assertEqual(value["annotation"]["annotation_status"], "physically_present_outside_image")
        self.assertEqual(value["yolo_label"], "")

    def test_negative_has_no_box_or_yolo_even_with_other_animals_present(self):
        value = self.prepare()
        absent = value["absent_stage"]
        label = dataset.annotation(absent, self.projection(absent), self.state, False)
        self.assertFalse(label["annotation"]["target_present"])
        self.assertIsNone(label["annotation"]["amodal_bbox_xyxy_px"])
        self.assertEqual(label["annotation"]["vertex_count"], 0)
        self.assertEqual(label["yolo_label"], "")
        self.assertTrue(absent.GetPrimAtPath(self.other.GetPath()))

    def test_invisible_or_submerged_animal_is_still_a_present_amodal_target(self):
        UsdGeom.Imageable(self.actor).GetVisibilityAttr().Set("invisible")
        self.state["agents"][0].update(behavioural_state="submerged_swim", depth_m=3)
        value = dataset.annotation(self.stage, self.projection(), self.state, True)
        self.assertTrue(value["annotation"]["target_present"])
        self.assertEqual(value["annotation"]["target_usd_visibility"], "invisible")
        self.assertEqual(value["annotation"]["rendered_visibility"], "unknown")
        self.assertEqual(value["annotation"]["original_gama_depth_m"], 3)
        self.assertTrue(value["yolo_label"].startswith("0 "))

    def test_corrupted_projection_and_vertices_behind_camera_are_rejected(self):
        projection = self.projection()
        projection["capture_view_matrix"][3][0] += 1
        with self.assertRaisesRegex(ValueError, "disagrees"):
            dataset.annotation(self.stage, projection, self.state, True)
        UsdGeom.XformCommonAPI(self.actor).SetTranslate(Gf.Vec3d(1, 1000, 2))
        with self.assertRaisesRegex(ValueError, "in front"):
            dataset.annotation(self.stage, self.projection(), self.state, True)

    def test_annotation_presence_mismatch_and_wrong_class_are_rejected(self):
        with self.assertRaises(ValueError):
            dataset.annotation(self.stage, self.projection(), self.state, False)
        state = deepcopy(self.state); state["agents"][0]["species"] = "bottlenose_dolphin"
        with self.assertRaises(ValueError):
            dataset.annotation(self.stage, self.projection(), state, True)

    def test_annotations_are_read_only_detached_and_finite_json(self):
        before = self.stage.GetRootLayer().ExportToString()
        value = dataset.annotation(self.stage, self.projection(), self.state, True)
        self.assertEqual(json.loads(json.dumps(value, allow_nan=False)), value)
        self.assertEqual(before, self.stage.GetRootLayer().ExportToString())


if __name__ == "__main__":
    unittest.main()
