"""Real USD coordinate checks and mocked Kit route tests, with no live writes."""
import asyncio
from copy import deepcopy
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from pxr import Usd, UsdGeom

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge"
PACKAGE = "_gama_v2_stage_test"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(MODULE)]
sys.modules[PACKAGE] = package
coordinates = importlib.import_module(PACKAGE + ".stage_coordinates")


def example():
    return json.loads((ROOT / "integrations/gama/examples/step_v2.json").read_text())


def explicit_stage(units=.01, axis="Y"):
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageMetersPerUnit(stage, units)
    UsdGeom.SetStageUpAxis(stage, axis)
    UsdGeom.Xform.Define(stage, "/World/ExistingAnimal")
    return stage


class CoordinateTests(unittest.TestCase):
    def test_missing_stage_and_unauthored_usd_defaults(self):
        self.assertFalse(coordinates.inspect_stage(None)["suitable_for_v2"])
        stage = Usd.Stage.CreateInMemory()
        report = coordinates.inspect_stage(stage)
        self.assertFalse(report["meters_per_unit_authored"])
        self.assertFalse(report["up_axis_authored"])
        self.assertFalse(report["suitable_for_v2"])
        with self.assertRaisesRegex(ValueError, "explicitly authored"):
            coordinates.preview_on_stage(example(), stage)

    def test_inspected_unit_changes_change_preview_without_any_usd_authoring(self):
        stage = explicit_stage()
        for units in (.01, 1.0, .1):
            UsdGeom.SetStageMetersPerUnit(stage, units)
            before = (stage.GetRootLayer().ExportToString(), stage.GetSessionLayer().ExportToString())
            preview = coordinates.preview_on_stage(example(), stage)
            self.assertEqual(preview["stage_coordinates"]["meters_per_scene_unit"], units)
            self.assertTrue(preview["stage_coordinates"]["suitable_for_v2"])
            self.assertEqual(preview["transforms"][0]["position_scene_units"], [1.25/units, -.8/units, -2.5/units])
            self.assertFalse(preview["rendered"])
            self.assertEqual(before, (stage.GetRootLayer().ExportToString(), stage.GetSessionLayer().ExportToString()))

    def test_wrong_axis_nonpositive_and_nonfinite_units_rejected(self):
        for units, axis in ((.01, "Z"), (0, "Y"), (-1, "Y"), (float("inf"), "Y"), (float("nan"), "Y")):
            with self.subTest(units=units, axis=axis):
                stage = explicit_stage(units, axis)
                before = stage.GetRootLayer().ExportToString()
                report = coordinates.inspect_stage(stage)
                self.assertFalse(report["suitable_for_v2"])
                # Non-finite metadata is diagnostic null, never invalid JSON.
                json.dumps(report, allow_nan=False)
                with self.assertRaises(ValueError):
                    coordinates.preview_on_stage(example(), stage)
                self.assertEqual(stage.GetRootLayer().ExportToString(), before)

    def test_invalid_input_does_not_even_inspect_a_stage(self):
        bad = example()
        bad["agents"][0]["position_m"] = [1, 2, 3]
        with patch.object(coordinates, "inspect_stage", side_effect=AssertionError("stage was accessed")):
            with self.assertRaises(ValueError):
                coordinates.preview_on_stage(bad, object())


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.routes = {}
        self.registrations = []
        self.stage = explicit_stage()
        self.stage_reads = 0
        routes = self.routes

        class Router:
            def __init__(self, **kwargs):
                pass

            def post(self, path):
                def register(fn):
                    routes[path] = fn
                    return fn
                return register

            get = post

        def get_stage():
            self.stage_reads += 1
            return self.stage

        omni = types.ModuleType("omni")
        omni.ext = types.ModuleType("omni.ext")
        omni.ext.IExt = object
        omni.usd = types.ModuleType("omni.usd")
        omni.usd.get_context = lambda: types.SimpleNamespace(get_stage=get_stage)
        core = types.ModuleType("omni.services.core")
        core.main = types.SimpleNamespace(register_router=self.registrations.append,
                                          deregister_router=self.registrations.remove)
        routers = types.ModuleType("omni.services.core.routers")
        routers.ServiceAPIRouter = Router
        modules = {"omni": omni, "omni.ext": omni.ext, "omni.usd": omni.usd,
                   "omni.services": types.ModuleType("omni.services"),
                   "omni.services.core": core, "omni.services.core.routers": routers}
        self.patcher = patch.dict(sys.modules, modules)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        spec = importlib.util.spec_from_file_location(PACKAGE + ".extension", MODULE / "extension.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.extension = module.GamaBridgeExtension()
        self.extension.on_startup("test")
        self.addCleanup(self.extension.on_shutdown)

    def call(self, path, *args):
        return asyncio.run(self.routes[path](*args))

    def test_v2_validation_buffer_isolated_from_v1_and_actor(self):
        before = self.stage.GetRootLayer().ExportToString()
        data = example()
        self.assertTrue(self.call("/integration/gama/v2/validate", data)["ok"])
        first = self.call("/integration/gama/v2/steps", data)
        self.assertTrue(first["accepted"])
        self.assertTrue(self.call("/integration/gama/v2/steps", data)["duplicate"])
        self.assertEqual(self.call("/integration/gama/v2/status")["accepted_steps"], 1)
        self.assertEqual(self.call("/integration/gama/status")["accepted_steps"], 0)
        self.assertFalse(self.call("/integration/gama/v2/status")["scene_control_enabled"])
        self.call("/integration/gama/reset")
        self.assertEqual(self.call("/integration/gama/v2/status")["accepted_steps"], 1)
        bad = deepcopy(data)
        bad["agents"][0]["depth_m"] = -1
        self.assertFalse(self.call("/integration/gama/v2/steps", bad)["ok"])
        self.assertEqual(self.call("/integration/gama/v2/status")["latest"], data)
        self.call("/integration/gama/v2/reset")
        self.assertIsNone(self.call("/integration/gama/v2/status")["latest"])
        self.assertEqual(self.stage_reads, 0)
        self.assertIsNone(self.extension._actor)
        self.assertEqual(self.stage.GetRootLayer().ExportToString(), before)

    def test_version_mismatch_rejected_on_both_routes_without_stage_access(self):
        v1 = json.loads((ROOT / "integrations/gama/examples/step_v1.json").read_text())
        self.assertFalse(self.call("/integration/gama/v2/steps", v1)["ok"])
        self.assertFalse(self.call("/integration/gama/steps", example())["ok"])
        self.assertFalse(self.call("/integration/gama/v2/preview", {})["ok"])
        self.assertEqual(self.stage_reads, 0)

    def test_read_only_current_stage_probe_and_conversion_preview(self):
        before = self.stage.GetRootLayer().ExportToString()
        stage_result = self.call("/integration/gama/stage")
        self.assertEqual(stage_result["stage_coordinates"]["up_axis"], "Y")
        preview = self.call("/integration/gama/v2/preview", example())
        self.assertTrue(preview["ok"])
        self.assertEqual(preview["transforms"][0]["position_scene_units"], [125, -80, -250])
        self.assertEqual(self.stage_reads, 2)
        self.assertIsNone(self.extension._actor)
        self.assertEqual(self.stage.GetRootLayer().ExportToString(), before)
        self.assertEqual(self.extension._buffer_v2.accepted_steps, 0)

    def test_missing_stage_probe_reports_unavailable_and_preview_fails(self):
        self.stage = None
        self.assertFalse(self.call("/integration/gama/stage")["stage_coordinates"]["stage_available"])
        self.assertFalse(self.call("/integration/gama/v2/preview", example())["ok"])


if __name__ == "__main__":
    unittest.main()
