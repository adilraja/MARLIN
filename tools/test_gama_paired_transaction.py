"""Offline transaction tests: actual USD/actor, explicitly fake Kit and RGB.

Run with Blender's USD Python and -B. No live service, renderer, GAMA execution
or generated runtime directory is used. Fake PNGs are unit-test fixtures only.
"""
import ast
import asyncio
from copy import deepcopy
import importlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
import zlib

from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux, UsdRender

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge"
SERVICE = ROOT / "source/extensions/cris.madil.render_service/cris/madil/render_service"
package = types.ModuleType("_gama_pair_transaction_test")
package.__path__ = [str(BRIDGE)]
sys.modules[package.__name__] = package
actor = importlib.import_module(package.__name__ + ".actor_v2")
paired = importlib.import_module(package.__name__ + ".paired_v2")
render_package = types.ModuleType("_gama_pair_transaction_render")
render_package.__path__ = [str(SERVICE)]
sys.modules[render_package.__name__] = render_package
geometry = importlib.import_module(render_package.__name__ + ".calibration_geometry")
projection = importlib.import_module(render_package.__name__ + ".capture_projection")

# Reuse the actual isolated USD sampling helper without importing Kit modules.
tree = ast.parse((SERVICE / "hidef_marine.py").read_text())
freeze_node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "freeze_stage")
namespace = {"Usd": Usd}
exec(compile(ast.Module(body=[freeze_node], type_ignores=[]), "hidef_marine.freeze_stage", "exec"), namespace)
freeze_stage = namespace["freeze_stage"]

ORDERS = [[.5, 1., 2., 3., 4.], [4., 2., .5, 3., 1.]]
ORIGINAL_CAMERA = "/World/Cameras/Original"
GSD_TOLERANCE_CM_PX = 1e-6  # USD focal/aperture values are float32.
FOOTPRINT_TOLERANCE_M = 1e-5


def write_fixture_png(path):
    def chunk(kind, content):
        return struct.pack(">I", len(content)) + kind + content + struct.pack(">I", zlib.crc32(kind + content))
    header = struct.pack(">IIBBBBB", 1024, 768, 8, 2, 0, 0, 0)
    pixels = zlib.compress((b"\x00" + b"\x30\x50\x70" * 1024) * 768)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", pixels) + chunk(b"IEND", b""))


class FakeTimeline:
    def __init__(self):
        self.seconds, self.playing = .25, True

    def get_current_time(self):
        return self.seconds

    def set_current_time(self, value):
        self.seconds = value

    def is_playing(self):
        return self.playing

    def pause(self):
        self.playing = False

    def play(self):
        self.playing = True


class FakeViewport:
    def __init__(self, runtime):
        self.runtime = runtime
        self.camera_path = ORIGINAL_CAMERA
        self.resolution = (800, 600)
        self.fill_frame = True
        self.updates_enabled = True
        self.render_product_path = "/Render/FakeProduct"

    @property
    def time(self):
        return self.runtime.timeline.seconds * self.runtime.stage().GetTimeCodesPerSecond()

    @property
    def view(self):
        return UsdGeom.Camera(self.runtime.stage().GetPrimAtPath(self.camera_path)).GetCamera(self.time).frustum.ComputeViewMatrix()

    @property
    def projection(self):
        return UsdGeom.Camera(self.runtime.stage().GetPrimAtPath(self.camera_path)).GetCamera(self.time).frustum.ComputeProjectionMatrix()


class FakeRuntime:
    def __init__(self, stage, directory):
        self.current_stage = self.original_stage = stage
        # Model the real omni.usd context's strong ownership of its attached
        # stage. USD Python stage handles alone may become weak cache handles.
        self.context_cache = Usd.StageCache()
        self.context_cache.Insert(stage)
        self.timeline = FakeTimeline()
        self.viewport = FakeViewport(self)
        self.lock = types.SimpleNamespace(_busy=False)
        self.gate = types.SimpleNamespace(paused=False)
        self.marine = types.SimpleNamespace(same_settings=lambda left, right: left == right)
        self.output_root = directory / "outputs"
        self.png = directory / "fake_renderer.png"
        write_fixture_png(self.png)
        self.settings = {"rtx_mode": "OriginalMode", "exposure": .25}
        self.selected = ["/World/Ocean"]
        self.display_value = 1023
        self.ocean = {"running": True, "elapsed": 123.4, "accumulator": .05}
        self.freeze_count = self.attach_count = self.update_count = self.capture_count = 0
        self.delays = []
        self.captured_poses = []
        self.captured_targets = []
        self.fail_capture_at = self.cancel_capture_at = None
        self.fail_attach_at = set()
        self.attach_hook = None
        self.selection_read_count = 0
        self.fail_selection_read_at = None
        self.update_hook = None
        self.sleep_hook = None
        self.publish_render_product()

    def stage(self):
        return self.current_stage

    def selection(self):
        self.selection_read_count += 1
        if self.selection_read_count == self.fail_selection_read_at:
            raise RuntimeError("Injected final selection verification read failure")
        return list(self.selected)

    def select(self, paths):
        self.selected = list(paths)

    def renderer(self):
        return deepcopy(self.settings)

    def restore_renderer(self, values):
        self.settings = deepcopy(values)

    def display(self):
        return self.display_value

    def set_display(self, value):
        self.display_value = value

    def ocean_clock(self):
        return deepcopy(self.ocean)

    def freeze(self, stage, seconds):
        self.freeze_count += 1
        if not self.gate.paused or not self.lock._busy or self.timeline.playing:
            raise AssertionError("Snapshot must be sampled after controller/timeline freeze")
        return freeze_stage(stage, Usd.TimeCode(seconds * stage.GetTimeCodesPerSecond()))

    def retain(self, stage):
        cache = Usd.StageCache()
        cache.Insert(stage)
        return cache

    def dependencies(self, stage):
        return []

    def preflight(self):
        return {"test_fixture": True, "free_mib": 8192}

    async def attach(self, stage):
        self.attach_count += 1
        if self.attach_count in self.fail_attach_at:
            raise RuntimeError("Injected stage attachment failure")
        self.context_cache.Clear()
        self.context_cache.Insert(stage)
        self.current_stage = stage
        self.settings = {"rtx_mode": "StageOpenDefault", "exposure": 7}
        if self.attach_hook is not None:
            self.attach_hook(self)
        await asyncio.sleep(0)

    def publish_render_product(self):
        product = UsdRender.Product.Define(self.stage(), self.viewport.render_product_path)
        product.CreateCameraRel().SetTargets([self.viewport.camera_path])
        product.CreateResolutionAttr().Set(Gf.Vec2i(*self.viewport.resolution))
        product.GetPrim().CreateAttribute("pixelAspectRatio", importlib.import_module("pxr.Sdf").ValueTypeNames.Float).Set(1.)

    async def update(self):
        self.update_count += 1
        self.publish_render_product()
        if self.update_hook is not None:
            self.update_hook(self)
        await asyncio.sleep(0)

    async def sleep(self, seconds):
        self.delays.append(seconds)
        if self.sleep_hook is not None:
            self.sleep_hook(self)
        await asyncio.sleep(0)

    def camera(self, stage, gsd, anchor, plane):
        config = geometry.CalibrationConfig(meters_per_scene_unit=.01, image_width_px=1024,
            image_height_px=768, focal_length_mm=50, pixel_pitch_um=5,
            height_above_target_m=gsd * 100, target_plane_y_m=plane,
            target_width_m=2, target_height_m=1)
        camera = geometry.build_camera(stage, config, paired.CAMERA, (anchor[0], 0, anchor[1]))
        camera.CreateClippingRangeAttr(Gf.Vec2f(1, 100000))

    def projection(self, stage):
        return projection.record_projection(stage, self.viewport)

    async def capture(self, target):
        self.capture_count += 1
        if self.capture_count == self.fail_capture_at:
            raise RuntimeError("Injected renderer capture failure")
        if self.capture_count == self.cancel_capture_at:
            raise asyncio.CancelledError()
        target = Path(target)
        if target.exists():
            raise AssertionError("A capture probe must receive a fresh target path")
        matrix = UsdGeom.Xformable(self.stage().GetPrimAtPath(actor.ACTOR)).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        self.captured_poses.append({"matrix": [list(row) for row in matrix],
            "clock": self.ocean_clock(), "timeline": self.timeline.seconds,
            "gate": self.gate.paused, "busy": self.lock._busy})
        write_fixture_png(target)
        self.captured_targets.append(target)
        await asyncio.sleep(0)
        return target

    def difference(self, previous, current):
        return 0.0


class PairedTransactionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        stage = self.stage = Usd.Stage.CreateInMemory()
        UsdGeom.SetStageUpAxis(stage, "Y")
        UsdGeom.SetStageMetersPerUnit(stage, .01)
        UsdGeom.Xform.Define(stage, "/World/Cetaceans/UnrelatedAnimal")
        ocean = UsdGeom.Mesh.Define(stage, "/World/Ocean")
        ocean.CreatePointsAttr().Set([Gf.Vec3f(-5, 0, -5), Gf.Vec3f(5, 0, -5), Gf.Vec3f(5, 0, 5)], 0)
        ocean.GetPointsAttr().Set([Gf.Vec3f(-5, 3, -5), Gf.Vec3f(5, 3, -5), Gf.Vec3f(5, 3, 5)], 10)
        ocean.CreateFaceVertexCountsAttr([3])
        ocean.CreateFaceVertexIndicesAttr([0, 1, 2])
        light = UsdLux.DistantLight.Define(stage, "/World/Environment/Sun")
        light.CreateIntensityAttr().Set(150., 0)
        light.GetIntensityAttr().Set(250., 10)
        camera_config = geometry.CalibrationConfig(.01, 800, 600, 50, 5, 50, 2, 1, 0)
        geometry.build_camera(stage, camera_config, ORIGINAL_CAMERA)
        self.owner = actor.PorpoiseActor()
        self.addCleanup(self.owner.close)
        self.token = self.owner.acquire(stage, "Porpoise_001")["ownership_token"]
        self.step = json.loads((ROOT / "experiments/gama_marlin_v1/trajectories/m3_seed_184729_a/trajectory.json").read_text())[8]
        self.owner.apply(stage, self.token, self.step)
        self.rt = FakeRuntime(stage, Path(self.temporary.name))
        self.before = {"root": stage.GetRootLayer().ExportToString(),
            "session": stage.GetSessionLayer().ExportToString(), "owned": self.owner.layer.ExportToString(),
            "pose": deepcopy(self.owner.status()["world_pose"]), "state": self.owner.buffer.latest}

    def execute(self, orders=ORDERS, delay=1.25):
        return asyncio.run(paired.run(self.owner, self.token, orders, delay, runtime=self.rt))

    def report(self, result):
        return json.loads(Path(result["manifest"]).read_text())

    def assert_restored(self):
        self.assertEqual(self.rt.stage(), self.stage)
        self.assertEqual(self.rt.viewport.camera_path, ORIGINAL_CAMERA)
        self.assertEqual(self.rt.viewport.resolution, (800, 600))
        self.assertTrue(self.rt.viewport.fill_frame)
        self.assertEqual(self.rt.selection(), ["/World/Ocean"])
        self.assertEqual(self.rt.renderer(), {"rtx_mode": "OriginalMode", "exposure": .25})
        self.assertEqual(self.rt.display(), 1023)
        self.assertEqual(self.rt.timeline.seconds, .25)
        self.assertTrue(self.rt.timeline.playing)
        self.assertFalse(self.rt.gate.paused)
        self.assertFalse(self.rt.lock._busy)
        self.assert_source_unchanged()

    def assert_source_unchanged(self):
        self.assertEqual(self.stage.GetRootLayer().ExportToString(), self.before["root"])
        self.assertEqual(self.stage.GetSessionLayer().ExportToString(), self.before["session"])
        self.assertEqual(self.owner.layer.ExportToString(), self.before["owned"])
        self.assertEqual(self.owner.status()["world_pose"], self.before["pose"])
        self.assertEqual(self.owner.buffer.latest, self.before["state"])
        self.assertEqual(self.owner.buffer.accepted_steps, 1)

    def test_two_orders_and_delays_share_one_resolved_scene_and_camera_protocol(self):
        result = self.execute()
        self.assertTrue(result["ok"], result)
        report = self.report(result)
        self.assertEqual(result["capture_count"], 10)
        self.assertEqual(self.rt.freeze_count, 1)
        self.assertEqual(self.rt.capture_count, 30)
        self.assertEqual(self.rt.delays.count(1.25), 5)
        self.assertTrue(all(check["matches"] for check in report["state_checks"]))
        self.assertEqual({check["resolved_scene_state_hash"] for check in report["state_checks"]}, {result["resolved_scene_state_hash"]})
        self.assertEqual(report["frozen_sampled_attributes"], 2)
        self.assertEqual(report["source_state"], self.step)
        conditions = {}
        for item in report["captures"]:
            gsd = item["gsd_cm_px"]
            record = item["camera_condition"]["camera_condition"]
            matrix = record["composed_camera_matrix"]
            agent = self.step["agents"][0]
            x, z = agent["horizontal_position_m"]
            plane = -agent["depth_m"]
            self.assertAlmostEqual(matrix[3][0] * .01, x, places=10)
            self.assertAlmostEqual(matrix[3][2] * .01, z, places=10)
            separation = matrix[3][1] * .01 - plane
            self.assertAlmostEqual(separation, gsd * 100, places=8)
            measured = separation * record["horizontal_aperture"] / (record["focal_length"] * 1024) * 100
            self.assertLessEqual(abs(measured - gsd), GSD_TOLERANCE_CM_PX)
            footprint = separation * record["horizontal_aperture"] / record["focal_length"]
            self.assertLessEqual(abs(footprint - 1024 * gsd / 100), FOOTPRINT_TOLERANCE_M)
            self.assertEqual(record["resolution_px"], [1024, 768])
            self.assertEqual(item["projection_before_capture"]["render_product"]["camera"], paired.CAMERA)
            self.assertEqual(item["projection_after_capture"]["render_product"]["resolution"], [1024, 768])
            if gsd in conditions:
                self.assertEqual(item["camera_condition"], conditions[gsd])
            conditions[gsd] = item["camera_condition"]
        self.assertEqual(len(conditions), 5)
        expected_matrix = [list(row) for row in self.owner.expected_matrix]
        for captured in self.rt.captured_poses:
            for actual, expected in zip(captured["matrix"], expected_matrix):
                for a, b in zip(actual, expected):
                    self.assertAlmostEqual(a, b, places=10)
            self.assertEqual(captured["clock"], self.rt.ocean)
            self.assertEqual(captured["timeline"], .25)
            self.assertTrue(captured["gate"] and captured["busy"])
        self.assert_restored()

    def test_invalid_conditions_and_delay_are_rejected_before_any_mutation(self):
        cases = (([], 0), ([[.5, 1, 2, 3, 3]], 0), ([[True, 1, 2, 3, 4]], 0),
                 (ORDERS, -1), (ORDERS, 6), (ORDERS, float("nan")), (ORDERS, True))
        for orders, delay in cases:
            with self.subTest(orders=orders, delay=delay):
                with self.assertRaises(ValueError):
                    self.execute(orders, delay)
                self.assertEqual(self.rt.freeze_count, 0)
                self.assertEqual(self.rt.attach_count, 0)
                self.assertFalse(self.rt.output_root.exists())
                self.assert_restored()

    def test_existing_capture_lock_or_gate_is_not_taken_over(self):
        for busy, paused in ((True, False), (False, True), (True, True)):
            self.rt.lock._busy, self.rt.gate.paused = busy, paused
            with self.subTest(busy=busy, paused=paused):
                with self.assertRaises(ValueError):
                    self.execute()
                self.assertEqual(self.rt.lock._busy, busy)
                self.assertEqual(self.rt.gate.paused, paused)
                self.assertEqual(self.rt.attach_count, 0)
                self.assertFalse(self.rt.output_root.exists())
                self.assert_source_unchanged()

    def test_capture_failure_preserves_partial_evidence_and_restores_everything(self):
        self.rt.fail_capture_at = 4
        result = self.execute()
        self.assertFalse(result["ok"])
        self.assertEqual(result["capture_count"], 1)
        self.assertFalse(result["recovery_required"])
        self.assertIn("Injected renderer capture failure", self.report(result)["error"])
        self.assert_restored()

    def test_each_probe_writes_a_fresh_unique_target_instead_of_prior_output(self):
        stale_output = b"stale prior renderer output is not a valid PNG"
        self.rt.png.write_bytes(stale_output)
        self.rt.fail_capture_at = 4
        result = self.execute()
        self.assertFalse(result["ok"])
        self.assertEqual(result["capture_count"], 1)
        self.assertEqual(len(self.rt.captured_targets), 3)
        self.assertEqual(len(set(self.rt.captured_targets)), 3)
        report = self.report(result)
        group = Path(result["directory"])
        expected = [group / probe["file"] for probe in report["captures"][0]["settling_probes"]]
        self.assertEqual(self.rt.captured_targets, expected)
        for target in self.rt.captured_targets:
            self.assertNotEqual(target, self.rt.png)
            self.assertTrue(target.is_file())
            header = target.read_bytes()[:24]
            self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", header[16:24]), (1024, 768))
        self.assertEqual(self.rt.png.read_bytes(), stale_output)
        self.assert_restored()

    def test_cancelled_capture_restores_and_retains_failed_manifest(self):
        self.rt.cancel_capture_at = 4
        with self.assertRaises(asyncio.CancelledError):
            self.execute()
        manifests = list(self.rt.output_root.glob("paired_*/manifest.json"))
        self.assertEqual(len(manifests), 1)
        report = json.loads(manifests[0].read_text())
        self.assertFalse(report["passed"])
        self.assertEqual(report["error"], "CancelledError")
        self.assertEqual(len(report["captures"]), 1)
        self.assert_restored()

    def test_initial_stage_attach_failure_restores_and_releases_gate(self):
        self.rt.fail_attach_at = {1}
        result = self.execute()
        self.assertFalse(result["ok"])
        self.assertFalse(result["recovery_required"])
        self.assertEqual(result["capture_count"], 0)
        self.assert_restored()

    def test_failed_original_stage_restore_keeps_controllers_frozen(self):
        self.rt.fail_capture_at = 1
        self.rt.fail_attach_at = {2}
        result = self.execute()
        self.assertFalse(result["ok"])
        self.assertTrue(result["recovery_required"])
        self.assertNotEqual(self.rt.stage(), self.stage)
        self.assertTrue(self.rt.gate.paused and self.rt.lock._busy)
        self.assertFalse(self.rt.timeline.playing)
        self.assertFalse(self.report(result)["restoration_checks"]["original_stage"])
        self.assert_source_unchanged()

    def test_new_rtx_camera_placeholder_on_original_stage_is_removed_boundedly(self):
        def create_placeholder(runtime):
            if runtime.attach_count == 2:
                spec = Sdf.CreatePrimInLayer(self.stage.GetRootLayer(), paired.CAMERA)
                for name in ("exposure:fStop", "exposure:responsivity", "exposure:time"):
                    Sdf.AttributeSpec(spec, name, Sdf.ValueTypeNames.Float).default = 1.
        self.rt.attach_hook = create_placeholder
        self.rt.fail_capture_at = 1
        result = self.execute()
        self.assertFalse(result["ok"])
        self.assertFalse(result["recovery_required"])
        self.assertEqual(self.report(result)["new_pair_camera_overs_removed"], [self.stage.GetRootLayer().identifier])
        self.assertFalse(self.stage.GetPrimAtPath(paired.CAMERA))
        self.assert_restored()

    def test_foreign_camera_placeholder_is_preserved_and_keeps_controllers_frozen(self):
        def create_foreign_placeholder(runtime):
            if runtime.attach_count == 2:
                spec = Sdf.CreatePrimInLayer(self.stage.GetRootLayer(), paired.CAMERA)
                Sdf.AttributeSpec(spec, "foreign:keep", Sdf.ValueTypeNames.String).default = "preserve"
        self.rt.attach_hook = create_foreign_placeholder
        self.rt.fail_capture_at = 1
        result = self.execute()
        self.assertFalse(result["ok"])
        self.assertTrue(result["recovery_required"])
        self.assertEqual(self.stage.GetPrimAtPath(paired.CAMERA).GetAttribute("foreign:keep").Get(), "preserve")
        self.assertIn("Foreign authored content", " ".join(self.report(result)["restoration_errors"]))
        self.assertTrue(self.rt.gate.paused and self.rt.lock._busy)
        self.assertFalse(self.rt.timeline.playing)
        self.assertEqual(self.owner.layer.ExportToString(), self.before["owned"])
        self.assertEqual(self.owner.buffer.latest, self.before["state"])

    def test_final_verification_read_failure_is_reported_and_keeps_gate_frozen(self):
        self.rt.fail_capture_at = 1
        self.rt.fail_selection_read_at = 2
        result = self.execute()
        self.assertFalse(result["ok"])
        self.assertTrue(result["recovery_required"])
        report = self.report(result)
        self.assertFalse(report["restoration_checks"]["verification_completed"])
        self.assertIn("verification: Injected final selection", " ".join(report["restoration_errors"]))
        self.assertEqual(self.rt.stage(), self.stage)
        self.assertTrue(self.rt.gate.paused and self.rt.lock._busy)
        self.assertFalse(self.rt.timeline.playing)
        self.assert_source_unchanged()

    def test_mutation_during_render_updates_is_detected_on_private_copy(self):
        def mutate(runtime):
            if runtime.stage() != self.stage and runtime.update_count == 2:
                light = UsdLux.DistantLight(runtime.stage().GetPrimAtPath("/World/Environment/Sun"))
                light.GetIntensityAttr().Set(999.)
        self.rt.update_hook = mutate
        result = self.execute()
        self.assertFalse(result["ok"])
        self.assertIn("Resolved biological/environmental state changed", self.report(result)["error"])
        self.assertFalse(self.report(result)["state_checks"][-1]["matches"])
        self.assert_restored()

    def test_environment_clock_advance_during_delay_is_rejected(self):
        def advance(runtime):
            runtime.ocean["elapsed"] += .1
        self.rt.sleep_hook = advance
        result = self.execute()
        self.assertFalse(result["ok"])
        self.assertIn("Biological or environmental time advanced", self.report(result)["error"])
        self.assertTrue(result["recovery_required"])
        self.assertTrue(self.rt.gate.paused and self.rt.lock._busy)
        self.assert_source_unchanged()


if __name__ == "__main__":
    unittest.main()
