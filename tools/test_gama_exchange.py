"""CPU-only tests; no Kit/GAMA launch and no live scene changes."""
import asyncio
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge"
spec = importlib.util.spec_from_file_location("gama_exchange_test", MODULE / "exchange.py")
exchange = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exchange)


def example():
    return json.loads((ROOT / "integrations/gama/examples/step_v1.json").read_text())


class ExchangeTests(unittest.TestCase):
    def test_manual_example_and_default_version(self):
        data = example()
        del data["schema_version"]
        checked = exchange.validate_step(data)
        self.assertEqual(checked["schema_version"], "1.0")
        checked["agents"][0]["position_m"][0] = 0
        self.assertEqual(data["agents"][0]["position_m"][0], 125.4)

    def test_position_units_and_cardinal_headings(self):
        data = example()
        for heading, expected in ((0, (0, 0, 1)), (90, (1, 0, 0)),
                                  (180, (0, 0, -1)), (270, (-1, 0, 0))):
            data["agents"][0]["heading_deg"] = heading
            result = exchange.preview_transforms(data, .01)[0]
            for actual, want in zip(result["forward_y_up"], expected):
                self.assertAlmostEqual(actual, want)
            for actual, want in zip(result["position_scene_units"], (12540, -80, 45610)):
                self.assertAlmostEqual(actual, want)
            self.assertAlmostEqual(result["speed_scene_units_per_s"], 240)
        with self.assertRaises(ValueError):
            exchange.preview_transforms(data, 0)

    def test_bad_numeric_values(self):
        for value in (float("nan"), float("inf"), True, "12.5", -1, 10**1000):
            with self.subTest(value=repr(value)[:30]):
                data = example()
                data["time_s"] = value
                with self.assertRaises(ValueError):
                    exchange.validate_step(data)
        for field, value in (("heading_deg", 360), ("speed_mps", -1), ("depth_m", -1)):
            data = example()
            data["agents"][0][field] = value
            with self.assertRaises(ValueError):
                exchange.validate_step(data)

    def test_duplicate_ids_unsafe_names_and_unknown_fields(self):
        data = example()
        data["agents"].append(deepcopy(data["agents"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            exchange.validate_step(data)
        for field, value in (("id", "../../World"), ("asset_path", "/tmp/foreign.usd"),
                             ("pixel_x", 500), ("state", "invented")):
            data = example()
            data["agents"][0][field] = value
            with self.assertRaises(ValueError):
                exchange.validate_step(data)

    def test_depth_is_mean_plane_not_wave_relative(self):
        data = example()
        data["agents"][0]["depth_m"] = .9
        with self.assertRaisesRegex(ValueError, "disagrees"):
            exchange.validate_step(data)
        data["agents"][0].update(position_m=[1, 2, 3], depth_m=0, altitude_m=2, state="flying")
        exchange.validate_step(data)  # This layer does NOT certify species/state biology.

    def test_buffer_retry_order_seed_and_failed_update_atomicity(self):
        buffer = exchange.StepBuffer()
        data = example()
        self.assertFalse(buffer.accept(data)["duplicate"])
        self.assertTrue(buffer.accept(data)["duplicate"])
        for change in ({"time_s": 1}, {"seed": 42}, {"agents": []}):
            bad = {**data, **change}
            with self.assertRaises(ValueError):
                buffer.accept(bad)
            self.assertEqual(buffer.latest, data)
            self.assertEqual(buffer.accepted_steps, 1)
        changed_species = deepcopy(data)
        changed_species["time_s"] += 1
        changed_species["agents"][0]["species"] = "minke_whale"
        with self.assertRaises(ValueError):
            buffer.accept(changed_species)
        data["time_s"] += 1
        self.assertFalse(buffer.accept(data)["duplicate"])
        self.assertEqual(buffer.accepted_steps, 2)
        buffer.reset()
        self.assertIsNone(buffer.latest)
        self.assertEqual(buffer.accepted_steps, 0)

    def test_empty_snapshot_and_detached_status(self):
        buffer = exchange.StepBuffer()
        buffer.accept(example())
        leaked = buffer.latest
        leaked["agents"].clear()
        self.assertEqual(len(buffer.latest["agents"]), 1)
        buffer.accept({"time_s": 20, "seed": 184729, "agents": []})
        self.assertEqual(buffer.latest["agents"], [])

    def test_schema_matches_supported_states(self):
        schema = json.loads((ROOT / "integrations/gama/step_v1.schema.json").read_text())
        self.assertEqual(set(schema["$defs"]["agent"]["properties"]["state"]["enum"]), exchange.STATES)
        self.assertEqual(schema["properties"]["agents"]["maxItems"], exchange.MAX_AGENTS)

    def test_extension_lifecycle_and_routes_without_scene_dependencies(self):
        # Mock only the Kit Services interface. Importing USD, settings, renderer,
        # or existing MARLIN modules is intentionally unsupported here.
        routes = {}
        registrations = []

        class Router:
            def __init__(self, **kwargs):
                pass

            def post(self, path):
                def register(fn):
                    routes[path] = fn
                    return fn
                return register

            get = post

        omni = types.ModuleType("omni")
        omni.ext = types.ModuleType("omni.ext")
        omni.ext.IExt = object
        core = types.ModuleType("omni.services.core")
        core.main = types.SimpleNamespace(register_router=registrations.append,
                                          deregister_router=registrations.remove)
        routers = types.ModuleType("omni.services.core.routers")
        routers.ServiceAPIRouter = Router
        package = types.ModuleType("gama_bridge_test")
        package.__path__ = [str(MODULE)]
        modules = {"omni": omni, "omni.ext": omni.ext,
                   "omni.services": types.ModuleType("omni.services"),
                   "omni.services.core": core, "omni.services.core.routers": routers,
                   "gama_bridge_test": package, "gama_bridge_test.exchange": exchange}
        with patch.dict(sys.modules, modules):
            spec = importlib.util.spec_from_file_location("gama_bridge_test.extension", MODULE / "extension.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            extension = module.GamaBridgeExtension()
            extension.on_startup("test")
            result = asyncio.run(routes["/integration/gama/steps"](example()))
            self.assertTrue(result["ok"])
            self.assertFalse(result["rendered"])
            result = asyncio.run(routes["/integration/gama/steps"]({}))
            self.assertFalse(result["ok"])
            status = asyncio.run(routes["/integration/gama/status"]())
            self.assertEqual(status["accepted_steps"], 1)
            asyncio.run(routes["/integration/gama/reset"]())
            self.assertEqual(extension._buffer.accepted_steps, 0)
            extension.on_shutdown()
            self.assertEqual(registrations, [])


if __name__ == "__main__":
    unittest.main()
