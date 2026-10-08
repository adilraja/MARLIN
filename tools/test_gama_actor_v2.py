"""Composed-USD acceptance checks for the opt-in v2 porpoise actor.

Run with Blender's USD Python and -B; these tests need no Kit or renderer.
Acceptance tolerances are declared here before any transform is compared.
"""
from copy import deepcopy
import importlib
import json
import math
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from pxr import Gf, Sdf, Usd, UsdGeom

POSITION_TOLERANCE_M = 1e-5
HEADING_TOLERANCE_DEG = 1e-4

package = types.ModuleType("_gama_actor_v2_test")
package.__path__ = [str(Path(__file__).resolve().parents[1] /
    "source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge")]
sys.modules[package.__name__] = package
actor = importlib.import_module("_gama_actor_v2_test.actor_v2")
legacy = importlib.import_module("_gama_actor_v2_test.actor")


def stage_with_units(units=.01):
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageUpAxis(stage, "Y")
    UsdGeom.SetStageMetersPerUnit(stage, units)
    return stage


class PorpoiseActorTests(unittest.TestCase):
    observed_position_errors_m = []
    observed_heading_errors_deg = []

    @classmethod
    def tearDownClass(cls):
        if cls.observed_position_errors_m:
            print(json.dumps({
                "composed_transform_comparisons": len(cls.observed_position_errors_m),
                "position_tolerance_m": POSITION_TOLERANCE_M,
                "heading_tolerance_deg": HEADING_TOLERANCE_DEG,
                "maximum_position_error_m": max(cls.observed_position_errors_m),
                "maximum_heading_error_deg": max(cls.observed_heading_errors_deg),
            }, sort_keys=True))

    def setUp(self):
        self.stage = stage_with_units()
        UsdGeom.Xform.Define(self.stage, "/World/Cetaceans/ExistingAnimal")
        UsdGeom.Camera.Define(self.stage, "/World/Camera")
        self.original = self.stage.GetRootLayer().ExportToString()
        self.session = self.stage.GetSessionLayer().ExportToString()
        self.owner = actor.PorpoiseActor()
        self.addCleanup(self.owner.close)
        self.token = self.owner.acquire(self.stage, "Porpoise_001")["ownership_token"]

    def step(self, index=0, state="shallow_swim", heading=90, depth=.8):
        return {"schema_version": "2.0", "run_id": "M4_Test", "step_index": index,
            "simulation_time_s": index * .5, "simulation_step_s": .5, "seed": 184729,
            "agents": [{"agent_id": "Porpoise_001", "species": "harbour_porpoise",
                "behavioural_state": state, "horizontal_position_m": [12, 2],
                "heading_deg": heading, "speed_mps": .6,
                "vertical_reference": "mean_sea_level", "depth_m": depth}]}

    def composed_pose(self):
        prim = self.stage.GetPrimAtPath(actor.ACTOR)
        matrix = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        return list(matrix.ExtractTranslation()), list(matrix.TransformDir(Gf.Vec3d(0, 0, 1)))

    def assert_pose(self, payload):
        position, forward = self.composed_pose()
        animal = payload["agents"][0]
        units = UsdGeom.GetStageMetersPerUnit(self.stage)
        expected = [animal["horizontal_position_m"][0], -animal["depth_m"],
                    animal["horizontal_position_m"][1]]
        position_error = math.sqrt(sum((actual * units - reference) ** 2
                                      for actual, reference in zip(position, expected)))
        self.observed_position_errors_m.append(position_error)
        self.assertLessEqual(position_error, POSITION_TOLERANCE_M)
        heading = math.degrees(math.atan2(forward[0], forward[2])) % 360
        error = abs((heading - animal["heading_deg"] + 180) % 360 - 180)
        self.observed_heading_errors_deg.append(error)
        self.assertLessEqual(error, HEADING_TOLERANCE_DEG)
        self.assertAlmostEqual(forward[1], 0, places=10)
        self.assertAlmostEqual(sum(value * value for value in forward), 1, places=10)
        reported = self.owner.status(self.stage)["world_pose"]
        self.assertEqual(reported["position_scene_units"], position)
        self.assertEqual(reported["forward_y_up"], forward)

    def test_four_cardinal_headings_use_composed_transform(self):
        for index, heading in enumerate((0, 90, 180, 270)):
            payload = self.step(index=index, heading=heading, depth=1.35)
            self.owner.apply(self.stage, self.token, payload)
            self.assert_pose(payload)
        self.assertEqual(self.owner.status(self.stage)["accepted_steps"], 4)

    def test_retained_actual_gama_trajectory_matches_composed_transforms(self):
        record = Path(__file__).resolve().parents[1] / (
            "experiments/gama_marlin_v1/trajectories/m3_seed_184729_a/trajectory.json")
        trajectory = json.loads(record.read_text())
        self.assertEqual(len(trajectory), 41)
        states = set()
        for payload in trajectory:
            self.owner.apply(self.stage, self.token, payload)
            self.assert_pose(payload)
            states.add(payload["agents"][0]["behavioural_state"])
        self.assertEqual(states, {"surface", "shallow_swim", "descent", "submerged_swim", "ascent"})
        self.assertEqual(self.owner.buffer.accepted_steps, len(trajectory))

    def test_all_states_and_fixed_vertical_datum(self):
        for index, state in enumerate(("surface", "shallow_swim", "descent", "submerged_swim", "ascent")):
            payload = self.step(index=index, state=state, depth=index * .75)
            self.owner.apply(self.stage, self.token, payload)
            self.assert_pose(payload)
            model = UsdGeom.XformCommonAPI(self.stage.GetPrimAtPath(actor.ACTOR + "/Model"))
            _, rotation, scale, _, _ = model.GetXformVectors(Usd.TimeCode.Default())
            self.assertEqual(list(rotation), [-90, 0, 0])
            self.assertEqual(list(scale), [100, 100, 100])
        self.assertEqual(self.stage.GetRootLayer().ExportToString(), self.original)

    def test_actual_reference_has_expected_calibrated_metric_dimensions(self):
        bounds = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default", "render"]).ComputeWorldBound(
            self.stage.GetPrimAtPath(actor.ACTOR)).ComputeAlignedRange()
        metric = [value * .01 for value in bounds.GetSize()]
        expected = [.4192374050617218, .4327882081270218, 1.6014894247055054]
        for actual, reference in zip(metric, expected):
            self.assertLessEqual(abs(actual - reference), POSITION_TOLERANCE_M)

    def test_explicit_stage_units_are_used_for_composed_pose(self):
        self.owner.release(self.token)
        UsdGeom.SetStageMetersPerUnit(self.stage, 1)
        self.token = self.owner.acquire(self.stage, "Porpoise_001")["ownership_token"]
        payload = self.step(heading=270, depth=3)
        self.owner.apply(self.stage, self.token, payload)
        self.assert_pose(payload)
        model = UsdGeom.XformCommonAPI(self.stage.GetPrimAtPath(actor.ACTOR + "/Model"))
        self.assertEqual(list(model.GetXformVectors(Usd.TimeCode.Default())[2]), [1, 1, 1])

    def test_duplicate_is_idempotent_and_does_not_create_animal(self):
        payload = self.step()
        self.owner.apply(self.stage, self.token, payload)
        layer = self.owner.layer.ExportToString()
        session = self.stage.GetSessionLayer().ExportToString()
        for _ in range(3):
            result = self.owner.apply(self.stage, self.token, deepcopy(payload))
            self.assertTrue(result["duplicate"])
        self.assertEqual(self.owner.buffer.accepted_steps, 1)
        self.assertEqual(self.owner.layer.ExportToString(), layer)
        self.assertEqual(self.stage.GetSessionLayer().ExportToString(), session)
        self.assertEqual(self.owner.status(self.stage)["actor_count"], 1)

    def test_invalid_unknown_and_out_of_order_updates_are_atomic(self):
        self.owner.apply(self.stage, self.token, self.step(index=1))
        invalid = []
        missing = self.step(index=2)
        del missing["agents"][0]["depth_m"]
        invalid.append(missing)
        unknown = self.step(index=2)
        unknown["agents"][0]["agent_id"] = "Other_Porpoise"
        invalid.append(unknown)
        invalid.append(self.step(index=0))
        conflicting = self.step(index=1, heading=180)
        invalid.append(conflicting)
        ambiguous = self.step(index=2)
        ambiguous["agents"][0]["position_m"] = [12, -.8, 2]
        invalid.append(ambiguous)
        nonfinite = self.step(index=2)
        nonfinite["agents"][0]["horizontal_position_m"][0] = math.nan
        invalid.append(nonfinite)
        before = self.owner.layer.ExportToString()
        latest = self.owner.buffer.latest
        for payload in invalid:
            with self.assertRaises(ValueError):
                self.owner.apply(self.stage, self.token, payload)
            self.assertEqual(self.owner.layer.ExportToString(), before)
            self.assertEqual(self.owner.buffer.latest, latest)
            self.assertEqual(self.owner.buffer.accepted_steps, 1)

    def test_reset_keeps_ownership_and_pose_then_accepts_new_run(self):
        self.owner.apply(self.stage, self.token, self.step(index=5))
        pose = self.composed_pose()
        layer = self.owner.layer.identifier
        self.owner.reset(self.stage, self.token)
        self.assertEqual(self.owner.token, self.token)
        self.assertEqual(self.owner.layer.identifier, layer)
        self.assertEqual(self.composed_pose(), pose)
        status = self.owner.status(self.stage)
        self.assertEqual(status["accepted_steps"], 0)
        self.assertIsNone(status["latest"])
        self.assertEqual(status["transport_state"], "awaiting_first_update")
        payload = self.step(index=0, heading=180)
        payload["run_id"] = "Restarted_Run"
        self.owner.apply(self.stage, self.token, payload)
        self.assertEqual(self.owner.buffer.accepted_steps, 1)
        self.assert_pose(payload)

    def test_interrupted_replay_freezes_and_reconnect_continues(self):
        with patch.object(actor.time, "monotonic", return_value=100):
            self.owner.apply(self.stage, self.token, self.step())
            self.assertEqual(self.owner.status(self.stage)["transport_state"], "holding_last_state")
        before = self.owner.layer.ExportToString()
        pose = self.composed_pose()
        with patch.object(actor.time, "monotonic", return_value=103):
            status = self.owner.status(self.stage)
            self.assertEqual(status["transport_state"], "frozen_updates_missing")
            self.assertEqual(status["motion_policy"], "freeze_and_report")
            self.assertEqual(self.composed_pose(), pose)
            self.assertEqual(self.owner.layer.ExportToString(), before)
            self.assertTrue(self.owner.apply(self.stage, self.token, self.step())["duplicate"])
            self.owner.apply(self.stage, self.token, self.step(index=1, heading=180))
            self.assertEqual(self.owner.status(self.stage)["transport_state"], "holding_last_state")
        self.assertEqual(self.owner.buffer.accepted_steps, 2)
        self.assert_pose(self.step(index=1, heading=180))

    def test_token_capture_and_foreign_stage_guards_preserve_pose(self):
        before = self.owner.layer.ExportToString()
        for stage, token, paused in ((self.stage, "wrong", False),
                                     (self.stage, self.token, True),
                                     (stage_with_units(), self.token, False)):
            with self.assertRaises(ValueError):
                self.owner.apply(stage, token, self.step(), paused=paused)
            self.assertEqual(self.owner.layer.ExportToString(), before)
            self.assertEqual(self.owner.buffer.accepted_steps, 0)
        with self.assertRaises(ValueError):
            self.owner.reset(self.stage, self.token, paused=True)
        with self.assertRaises(ValueError):
            self.owner.release(self.token, paused=True)

    def test_stage_metadata_change_freezes_and_can_be_explicitly_recovered(self):
        self.owner.apply(self.stage, self.token, self.step())
        before = self.owner.layer.ExportToString()
        UsdGeom.SetStageMetersPerUnit(self.stage, 1)
        with self.assertRaises(ValueError):
            self.owner.apply(self.stage, self.token, self.step(index=1))
        self.assertEqual(self.owner.status(self.stage)["transport_state"], "frozen_guard_failure")
        self.assertEqual(self.owner.layer.ExportToString(), before)
        UsdGeom.SetStageMetersPerUnit(self.stage, .01)
        self.owner.apply(self.stage, self.token, self.step(index=1))
        self.assert_pose(self.step(index=1))

    def test_foreign_parent_translation_freezes_updates_and_duplicates(self):
        self.owner.apply(self.stage, self.token, self.step())
        before = self.owner.layer.ExportToString()
        latest = self.owner.buffer.latest
        with Usd.EditContext(self.stage, self.stage.GetRootLayer()):
            parent = UsdGeom.Xform.Define(self.stage, actor.ROOT)
            UsdGeom.XformCommonAPI(parent).SetTranslate(Gf.Vec3d(1000, 0, 0))
        foreign_opinion = self.stage.GetRootLayer().ExportToString()
        self.assertEqual(self.owner.status(self.stage)["transport_state"], "frozen_guard_failure")
        for payload in (self.step(), self.step(index=1, heading=180)):
            with self.assertRaises(ValueError):
                self.owner.apply(self.stage, self.token, payload)
            self.assertEqual(self.owner.layer.ExportToString(), before)
            self.assertEqual(self.owner.buffer.latest, latest)
            self.assertEqual(self.owner.buffer.accepted_steps, 1)
            self.assertEqual(self.owner.status(self.stage)["transport_state"], "frozen_guard_failure")
        self.assertEqual(self.stage.GetRootLayer().ExportToString(), foreign_opinion)

    def test_stronger_actor_override_freezes_duplicate_and_status(self):
        self.owner.apply(self.stage, self.token, self.step())
        before = self.owner.layer.ExportToString()
        latest = self.owner.buffer.latest
        with Usd.EditContext(self.stage, self.stage.GetSessionLayer()):
            motion = UsdGeom.XformCommonAPI(self.stage.GetPrimAtPath(actor.ACTOR))
            motion.SetTranslate(Gf.Vec3d(12345, 0, 0))
        status = self.owner.status(self.stage)
        self.assertEqual(status["transport_state"], "frozen_guard_failure")
        self.assertTrue(status["guard_error"])
        self.assertEqual(status["world_pose"]["position_scene_units"], [12345, 0, 0])
        with self.assertRaises(ValueError):
            self.owner.apply(self.stage, self.token, self.step())
        self.assertEqual(self.owner.layer.ExportToString(), before)
        self.assertEqual(self.owner.buffer.latest, latest)
        self.assertEqual(self.owner.buffer.accepted_steps, 1)

    def test_matching_stronger_override_rejects_next_pose_and_rolls_back(self):
        self.owner.apply(self.stage, self.token, self.step())
        old_position, _ = self.composed_pose()
        with Usd.EditContext(self.stage, self.stage.GetSessionLayer()):
            motion = UsdGeom.XformCommonAPI(self.stage.GetPrimAtPath(actor.ACTOR))
            motion.SetTranslate(Gf.Vec3d(*old_position))
        self.assertEqual(self.owner.status(self.stage)["transport_state"], "holding_last_state")
        before = self.owner.layer.ExportToString()
        latest = self.owner.buffer.latest
        expected_matrix = Gf.Matrix4d(self.owner.expected_matrix)
        last_received = self.owner.last_received
        stronger_layer = self.stage.GetSessionLayer().ExportToString()
        payload = self.step(index=1, heading=180)
        payload["agents"][0]["horizontal_position_m"] = [14, 7]
        with self.assertRaises(ValueError):
            self.owner.apply(self.stage, self.token, payload)
        self.assertEqual(self.owner.layer.ExportToString(), before)
        self.assertEqual(self.owner.buffer.latest, latest)
        self.assertEqual(self.owner.buffer.accepted_steps, 1)
        self.assertEqual(self.owner.expected_matrix, expected_matrix)
        self.assertEqual(self.owner.last_received, last_received)
        self.assertEqual(self.stage.GetSessionLayer().ExportToString(), stronger_layer)
        self.assert_pose(latest)

    def test_missing_owned_layer_blocks_updates_without_replacement(self):
        paths = self.stage.GetSessionLayer().subLayerPaths
        paths.remove(self.owner.layer.identifier)
        with self.assertRaises(ValueError):
            self.owner.apply(self.stage, self.token, self.step())
        self.assertEqual(self.owner.status(self.stage)["transport_state"], "frozen_guard_failure")
        self.assertFalse(self.stage.GetPrimAtPath(actor.ROOT))
        self.assertEqual(self.owner.buffer.accepted_steps, 0)

    def test_root_collision_and_double_ownership_are_refused(self):
        with self.assertRaises(ValueError):
            self.owner.acquire(self.stage, "Porpoise_001")
        other = actor.PorpoiseActor()
        self.addCleanup(other.close)
        with self.assertRaises(ValueError):
            other.acquire(self.stage, "Porpoise_002")

    def test_stage_metadata_must_be_authored_and_agent_id_must_be_safe(self):
        for configure in (lambda stage: None,
                          lambda stage: UsdGeom.SetStageUpAxis(stage, "Y"),
                          lambda stage: UsdGeom.SetStageMetersPerUnit(stage, .01)):
            other = actor.PorpoiseActor()
            self.addCleanup(other.close)
            stage = Usd.Stage.CreateInMemory()
            configure(stage)
            with self.assertRaises(ValueError):
                other.acquire(stage, "Porpoise_001")
        other = actor.PorpoiseActor()
        self.addCleanup(other.close)
        for unsafe in ("/World/Animal", "../Animal", "", None):
            with self.assertRaises(ValueError):
                other.acquire(stage_with_units(), unsafe)

    def test_release_removes_only_owned_layer_and_restores_session(self):
        self.owner.apply(self.stage, self.token, self.step())
        self.owner.release(self.token)
        self.assertFalse(self.stage.GetPrimAtPath(actor.ROOT))
        self.assertTrue(self.stage.GetPrimAtPath("/World/Cetaceans/ExistingAnimal"))
        self.assertTrue(self.stage.GetPrimAtPath("/World/Camera"))
        self.assertEqual(self.stage.GetRootLayer().ExportToString(), self.original)
        self.assertEqual(self.stage.GetSessionLayer().ExportToString(), self.session)
        self.assertFalse(self.owner.status(self.stage)["owned"])

    def test_empty_root_cleanup_requires_unowned_stage_and_capture_gate(self):
        before = self.stage.GetRootLayer().ExportToString()
        with self.assertRaises(ValueError):
            self.owner.cleanup_empty_root(self.stage)
        self.assertEqual(self.stage.GetRootLayer().ExportToString(), before)
        self.owner.release(self.token)
        Sdf.CreatePrimInLayer(self.stage.GetRootLayer(), actor.ROOT)
        before = self.stage.GetRootLayer().ExportToString()
        with self.assertRaises(ValueError):
            self.owner.cleanup_empty_root(self.stage, paused=True)
        with self.assertRaises(ValueError):
            self.owner.cleanup_empty_root(None)
        self.assertEqual(self.stage.GetRootLayer().ExportToString(), before)

    def test_empty_root_cleanup_removes_only_empty_over_and_is_idempotent(self):
        self.owner.release(self.token)
        Sdf.CreatePrimInLayer(self.stage.GetRootLayer(), actor.ROOT)
        result = self.owner.cleanup_empty_root(self.stage)
        self.assertTrue(result["removed"])
        self.assertFalse(self.stage.GetPrimAtPath(actor.ROOT))
        self.assertEqual(self.stage.GetRootLayer().ExportToString(), self.original)
        self.assertEqual(self.stage.GetSessionLayer().ExportToString(), self.session)
        self.assertFalse(self.owner.cleanup_empty_root(self.stage)["removed"])

    def test_empty_root_cleanup_preserves_typed_authored_and_foreign_content(self):
        self.owner.release(self.token)
        layer = self.stage.GetRootLayer()
        def attribute(spec):
            Sdf.AttributeSpec(spec, "keep", Sdf.ValueTypeNames.Float).default = 1.0
        cases = {
            "typed_definition": lambda spec: (setattr(spec, "specifier", Sdf.SpecifierDef), setattr(spec, "typeName", "Xform")),
            "typed_over": lambda spec: setattr(spec, "typeName", "Xform"),
            "custom_data": lambda spec: setattr(spec, "customData", {"keep": "foreign"}),
            "root_attribute": attribute,
            "foreign_child": lambda spec: Sdf.CreatePrimInLayer(layer, actor.ROOT + "/Keep"),
            "foreign_variants": lambda spec: Sdf.VariantSpec(Sdf.VariantSetSpec(spec, "Keep"), "VersionA"),
        }
        for name, configure in cases.items():
            with self.subTest(name=name):
                layer.ImportFromString(self.original)
                configure(Sdf.CreatePrimInLayer(layer, actor.ROOT))
                before = layer.ExportToString()
                with self.assertRaises(ValueError):
                    self.owner.cleanup_empty_root(self.stage)
                self.assertEqual(layer.ExportToString(), before)
        layer.ImportFromString(self.original)
        Sdf.CreatePrimInLayer(self.stage.GetSessionLayer(), actor.ROOT)
        before = self.stage.GetSessionLayer().ExportToString()
        with self.assertRaises(ValueError):
            self.owner.cleanup_empty_root(self.stage)
        self.assertEqual(self.stage.GetSessionLayer().ExportToString(), before)

    def test_diagnostic_camera_cleanup_is_bounded_to_numeric_rtx_exposure_overs(self):
        visual = importlib.import_module("_gama_actor_v2_test.visual_v2")
        self.owner.release(self.token)
        layer = self.stage.GetRootLayer()
        def create_camera():
            layer.ImportFromString(self.original)
            spec = Sdf.CreatePrimInLayer(layer, actor.ROOT + "/DiagnosticCamera")
            for name in ("exposure:fStop", "exposure:responsivity", "exposure:time"):
                Sdf.AttributeSpec(spec, name, Sdf.ValueTypeNames.Float).default = 1.0
            return spec
        camera = create_camera()
        self.assertTrue(visual._is_diagnostic_camera_over(camera))
        self.assertTrue(self.owner.cleanup_empty_root(self.stage)["removed"])
        self.assertEqual(layer.ExportToString(), self.original)
        def extra_attribute(spec):
            Sdf.AttributeSpec(spec, "keep", Sdf.ValueTypeNames.Float).default = 1.0
        def connection(spec):
            spec.attributes["exposure:time"].connectionPathList.explicitItems = [Sdf.Path("/World/Other.time")]
        def time_sample(spec):
            layer.SetTimeSample(spec.attributes["exposure:time"].path, 0, 1.0)
        def boolean_default(spec):
            attr = spec.attributes["exposure:time"]
            spec.RemoveProperty(attr)
            Sdf.AttributeSpec(spec, "exposure:time", Sdf.ValueTypeNames.Bool).default = True
        cases = {
            "typed_camera": lambda spec: setattr(spec, "typeName", "Camera"),
            "custom_metadata": lambda spec: setattr(spec, "customData", {"keep": "foreign"}),
            "foreign_child": lambda spec: Sdf.CreatePrimInLayer(layer, str(spec.path) + "/Keep"),
            "extra_attribute": extra_attribute,
            "connection": connection,
            "time_sample": time_sample,
            "boolean_default": boolean_default,
            "nonfinite_default": lambda spec: setattr(spec.attributes["exposure:time"], "default", math.inf),
            "missing_default": lambda spec: spec.attributes["exposure:time"].ClearDefaultValue(),
            "attribute_metadata": lambda spec: setattr(spec.attributes["exposure:time"], "documentation", "keep"),
        }
        for name, configure in cases.items():
            with self.subTest(name=name):
                camera = create_camera()
                configure(camera)
                before = layer.ExportToString()
                self.assertFalse(visual._is_diagnostic_camera_over(camera))
                with self.assertRaises(ValueError):
                    self.owner.cleanup_empty_root(self.stage)
                self.assertEqual(layer.ExportToString(), before)

    def test_replacement_stage_cleanup_targets_saved_stage_only(self):
        foreign = stage_with_units()
        UsdGeom.Xform.Define(foreign, actor.ROOT)
        before = foreign.GetRootLayer().ExportToString()
        with self.assertRaises(ValueError):
            self.owner.apply(foreign, self.token, self.step())
        self.owner.close()
        self.assertFalse(self.stage.GetPrimAtPath(actor.ROOT))
        self.assertEqual(foreign.GetRootLayer().ExportToString(), before)

    def test_v1_and_v2_have_independent_layers_and_release(self):
        old = legacy.IsolatedActor()
        self.addCleanup(old.close)
        old_token = old.acquire(self.stage)["ownership_token"]
        old_layer = old.layer.ExportToString()
        self.owner.apply(self.stage, self.token, self.step())
        self.assertEqual(old.layer.ExportToString(), old_layer)
        self.assertTrue(self.stage.GetPrimAtPath(legacy.ACTOR))
        self.assertTrue(self.stage.GetPrimAtPath(actor.ACTOR))
        self.owner.release(self.token)
        self.assertTrue(self.stage.GetPrimAtPath(legacy.ACTOR))
        self.assertEqual(old.layer.ExportToString(), old_layer)
        old.release(old_token)
        self.assertEqual(self.stage.GetSessionLayer().ExportToString(), self.session)


if __name__ == "__main__":
    unittest.main()
