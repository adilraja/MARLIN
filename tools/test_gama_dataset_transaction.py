"""M7 offline dataset transactions: actual USD/actor, fake Kit and RGB only.

Run with Blender's USD Python and -B. No live endpoints or renderer are used.
The M6 fixture stays unchanged; this module adds target-absent capture support.
"""
import asyncio
from copy import deepcopy
import importlib
import hashlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest import mock

from pxr import Usd, UsdGeom, UsdLux

import test_gama_paired_transaction as m6

actor = m6.actor
state_identity = importlib.import_module(m6.package.__name__ + ".paired_state_v2")
GSDS = [.5, 1., 2., 3., 4.]


def background_hash(stage):
    """Independently compare physical USD after removing the owned target.

    source_content_hash excludes cameras and /Render using the same declared
    physical identity boundary. This private test clone never edits the source.
    """
    private = Usd.Stage.Open(stage.Flatten(False))
    if private.GetPrimAtPath(actor.ROOT):
        private.RemovePrim(actor.ROOT)
    return state_identity.source_content_hash(private)


class DatasetRuntime(m6.FakeRuntime):
    def __init__(self, stage, directory):
        super().__init__(stage, directory)
        self.variant_observations = []

    async def capture(self, target):
        self.capture_count += 1
        if self.capture_count == self.fail_capture_at:
            raise RuntimeError("Injected renderer capture failure")
        if self.capture_count == self.cancel_capture_at:
            raise asyncio.CancelledError()
        target = Path(target)
        if target.exists():
            raise AssertionError("A capture probe must receive a fresh target path")
        stage = self.stage()
        prim = stage.GetPrimAtPath(actor.ACTOR)
        matrix = (UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
                  if prim else None)
        observation = {
            "target_root_present": bool(stage.GetPrimAtPath(actor.ROOT)),
            "target_actor_present": bool(prim),
            "matrix": [list(row) for row in matrix] if matrix is not None else None,
            "background_hash": background_hash(stage),
            "clock": self.ocean_clock(),
            "timeline": self.timeline.seconds,
            "gate": self.gate.paused,
            "busy": self.lock._busy,
            "source_state": deepcopy(self.owner.buffer.latest),
        }
        self.variant_observations.append(observation)
        m6.write_fixture_png(target)
        self.captured_targets.append(target)
        await asyncio.sleep(0)
        return target


class DatasetTransactionTests(unittest.TestCase):
    # Reuse fixture construction and source/restoration assertions without
    # inheriting M6 TestCase methods or executing the sealed M6 suite again.
    assert_restored = m6.PairedTransactionTests.assert_restored
    assert_source_unchanged = m6.PairedTransactionTests.assert_source_unchanged
    report = m6.PairedTransactionTests.report

    def setUp(self):
        m6.PairedTransactionTests.setUp(self)
        self.rt = DatasetRuntime(self.stage, Path(self.temporary.name))
        self.rt.owner = self.owner

    def execute(self, token=None):
        dataset = importlib.import_module(m6.package.__name__ + ".dataset_v2")
        # Supply the actual projection module at its canonical import path,
        # while avoiding the Kit-only render-service package initializer.
        cris = types.ModuleType("cris")
        madil = types.ModuleType("cris.madil")
        render_service = types.ModuleType("cris.madil.render_service")
        for module in (cris, madil, render_service):
            module.__path__ = []
        cris.madil, madil.render_service = madil, render_service
        render_service.capture_projection = m6.projection
        with mock.patch.dict(sys.modules, {
                "cris": cris, "cris.madil": madil, "cris.madil.render_service": render_service,
                "cris.madil.render_service.capture_projection": m6.projection}):
            return asyncio.run(dataset.run(self.owner, self.token if token is None else token,
                                          runtime=self.rt))

    def check_capture_files(self, item, directory):
        annotation = directory / item["annotation_file"]
        label = directory / item["yolo_file"]
        self.assertEqual(hashlib.sha256(annotation.read_bytes()).hexdigest(), item["annotation_sha256"])
        self.assertEqual(hashlib.sha256(label.read_bytes()).hexdigest(), item["yolo_sha256"])
        metadata = json.loads(annotation.read_text())
        self.assertEqual(metadata["target_present"], item["target_present"])
        if item["target_present"]:
            self.assertIn("amodal", json.dumps(metadata).lower())
            values = label.read_text().split()
            self.assertEqual(len(values), 5)
            self.assertEqual(values[0], "0")
            self.assertTrue(all(0 <= float(value) <= 1 for value in values[1:]))
            self.assertGreater(float(values[3]), 0)
            self.assertGreater(float(values[4]), 0)
        else:
            self.assertEqual(label.read_bytes(), b"")
        return metadata

    def test_five_present_and_five_removed_targets_share_one_frozen_background(self):
        result = self.execute()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["capture_count"], 10)
        self.assertEqual(self.rt.freeze_count, 1)
        self.assertEqual(self.rt.capture_count, 30)
        self.assertEqual(len(set(self.rt.captured_targets)), 30)
        report = self.report(result)
        self.assertEqual(report["source_state"], self.step)
        self.assertEqual([item["variant"] for item in report["captures"]], ["present"] * 5 + ["absent"] * 5)
        self.assertEqual([item["target_present"] for item in report["captures"]], [True] * 5 + [False] * 5)
        self.assertEqual([item["gsd_cm_px"] for item in report["captures"]], GSDS * 2)
        parent_hash = result["parent_scene_hash"]
        background = result["background_scene_hash"]
        self.assertEqual({item["parent_scene_hash"] for item in report["captures"]}, {parent_hash})
        self.assertEqual({item["background_scene_hash"] for item in report["captures"]}, {background})
        present_hashes = {item["resolved_scene_state_hash"] for item in report["captures"][:5]}
        absent_hashes = {item["resolved_scene_state_hash"] for item in report["captures"][5:]}
        self.assertEqual(len(present_hashes), 1)
        self.assertEqual(len(absent_hashes), 1)
        self.assertTrue(present_hashes.isdisjoint(absent_hashes))
        self.assertIn("RemovePrim", json.dumps(report["target_removal"]))
        self.assertIn(actor.ROOT, json.dumps(report["target_removal"]))
        directory = Path(result["directory"])
        for positive, negative in zip(report["captures"][:5], report["captures"][5:]):
            self.assertEqual(positive["camera_condition"], negative["camera_condition"])
            self.assertEqual(positive["projection_before_capture"], negative["projection_before_capture"])
            self.check_capture_files(positive, directory)
            self.check_capture_files(negative, directory)
        observations = self.rt.variant_observations
        self.assertEqual([item["target_root_present"] for item in observations], [True] * 15 + [False] * 15)
        self.assertEqual([item["target_actor_present"] for item in observations], [True] * 15 + [False] * 15)
        self.assertEqual(len({item["background_hash"] for item in observations}), 1)
        expected_matrix = [list(row) for row in self.owner.expected_matrix]
        for observation in observations:
            self.assertEqual(observation["matrix"], expected_matrix if observation["target_actor_present"] else None)
            self.assertEqual(observation["source_state"], self.step)
            self.assertEqual(observation["clock"], self.rt.ocean)
            self.assertEqual(observation["timeline"], .25)
            self.assertTrue(observation["gate"] and observation["busy"])
        self.assert_restored()

    def test_invisible_physically_present_target_is_not_relabelled_as_absent(self):
        UsdGeom.Imageable(self.stage.GetPrimAtPath(actor.ACTOR)).MakeInvisible()
        self.before["root"] = self.stage.GetRootLayer().ExportToString()
        self.rt.fail_capture_at = 4
        result = self.execute()
        self.assertFalse(result["ok"])
        self.assertEqual(result["capture_count"], 1)
        item = self.report(result)["captures"][0]
        self.assertEqual(item["variant"], "present")
        self.assertTrue(item["target_present"])
        self.check_capture_files(item, Path(result["directory"]))
        self.assertTrue(all(item["target_actor_present"] for item in self.rt.variant_observations))
        self.assert_restored()

    def test_failure_in_first_absent_probe_retains_positives_and_restores_source(self):
        self.rt.fail_capture_at = 16
        result = self.execute()
        self.assertFalse(result["ok"])
        self.assertEqual(result["capture_count"], 5)
        self.assertFalse(result["recovery_required"])
        report = self.report(result)
        self.assertIn("Injected renderer capture failure", report["error"])
        self.assertTrue(all(item["target_present"] for item in report["captures"]))
        self.assert_restored()

    def test_cancelled_absent_probe_preserves_failure_evidence_and_restores_source(self):
        self.rt.cancel_capture_at = 16
        with self.assertRaises(asyncio.CancelledError):
            self.execute()
        manifests = list(self.rt.output_root.glob("*/manifest.json"))
        self.assertEqual(len(manifests), 1)
        report = json.loads(manifests[0].read_text())
        self.assertFalse(report["passed"])
        self.assertEqual(report["error"], "CancelledError")
        self.assertEqual(len(report["captures"]), 5)
        self.assert_restored()

    def test_failed_restore_from_absent_stage_retains_original_and_keeps_gates_closed(self):
        self.rt.fail_capture_at = 16
        self.rt.fail_attach_at = {3}
        result = self.execute()
        self.assertFalse(result["ok"])
        self.assertTrue(result["recovery_required"])
        self.assertNotEqual(self.rt.stage(), self.stage)
        self.assertFalse(self.rt.stage().GetPrimAtPath(actor.ROOT))
        self.assertTrue(self.rt.gate.paused and self.rt.lock._busy)
        self.assertFalse(self.rt.timeline.playing)
        self.assert_source_unchanged()

    def test_refused_target_removal_is_rejected_before_any_dataset_capture(self):
        original = Usd.Stage.RemovePrim
        def refuse_owned_target(stage, path):
            return False if str(path) == actor.ROOT else original(stage, path)
        with mock.patch.object(Usd.Stage, "RemovePrim", refuse_owned_target):
            result = self.execute()
        self.assertFalse(result["ok"])
        self.assertEqual(result["capture_count"], 0)
        self.assertEqual(self.rt.capture_count, 0)
        self.assert_restored()

    def test_background_change_on_absent_stage_is_detected_before_negative_capture(self):
        def mutate_negative(runtime):
            if runtime.stage() != self.stage and not runtime.stage().GetPrimAtPath(actor.ROOT):
                UsdLux.DistantLight(runtime.stage().GetPrimAtPath("/World/Environment/Sun")).GetIntensityAttr().Set(999.)
        self.rt.update_hook = mutate_negative
        result = self.execute()
        self.assertFalse(result["ok"])
        self.assertEqual(result["capture_count"], 5)
        self.assertEqual(self.rt.capture_count, 15)
        self.assertIn("chang", self.report(result)["error"].lower())
        self.assert_restored()

    def test_target_reappearing_on_absent_stage_is_rejected_even_with_same_background(self):
        def reintroduce_negative_target(runtime):
            if runtime.stage() != self.stage and not runtime.stage().GetPrimAtPath(actor.ROOT):
                UsdGeom.Xform.Define(runtime.stage(), actor.ROOT)
        self.rt.update_hook = reintroduce_negative_target
        result = self.execute()
        self.assertFalse(result["ok"])
        self.assertEqual(result["capture_count"], 5)
        self.assertEqual(self.rt.capture_count, 15)
        self.assert_restored()

    def test_initial_private_stage_attach_failure_restores_without_capture(self):
        self.rt.fail_attach_at = {1}
        result = self.execute()
        self.assertFalse(result["ok"])
        self.assertFalse(result["recovery_required"])
        self.assertEqual(result["capture_count"], 0)
        self.assert_restored()

    def test_invalid_ownership_token_is_rejected_before_mutation(self):
        with self.assertRaises(ValueError):
            self.execute(token="unrelated-owner-token")
        self.assertEqual(self.rt.freeze_count, 0)
        self.assertEqual(self.rt.attach_count, 0)
        self.assertFalse(self.rt.output_root.exists())
        self.assert_restored()

    def test_existing_capture_or_controller_gate_is_not_taken_over(self):
        for busy, paused in ((True, False), (False, True), (True, True)):
            with self.subTest(busy=busy, paused=paused):
                self.rt.lock._busy, self.rt.gate.paused = busy, paused
                with self.assertRaises(ValueError):
                    self.execute()
                self.assertEqual((self.rt.lock._busy, self.rt.gate.paused), (busy, paused))
                self.assertEqual(self.rt.attach_count, 0)
                self.assertFalse(self.rt.output_root.exists())
                self.assert_source_unchanged()


if __name__ == "__main__":
    unittest.main()
