"""CPU-only v2 contract checks; never launch Kit/GAMA or change a USD scene.

These tests certify exchange interpretation and ordering, not animal biology.
Run with: python3 -B tools/test_gama_exchange_v2.py
"""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge"
package = types.ModuleType("_gama_exchange_v2_test")
package.__path__ = [str(MODULE)]
sys.modules[package.__name__] = package
exchange = importlib.import_module(f"{package.__name__}.exchange_v2")

MAX_SAFE_INTEGER = 2**53 - 1
STATES = {"surface", "shallow_swim", "descent", "submerged_swim", "ascent"}
STEP_FIELDS = {
    "schema_version", "run_id", "step_index", "simulation_time_s",
    "simulation_step_s", "seed", "agents",
}
AGENT_FIELDS = {
    "agent_id", "species", "behavioural_state", "horizontal_position_m",
    "heading_deg", "speed_mps", "vertical_reference", "depth_m",
}


def step(index=4, dt=0.25):
    """An engineering fixture; deliberately independent of the JSON example."""
    return {
        "schema_version": "2.0",
        "run_id": "M2_fixture",
        "step_index": index,
        "simulation_time_s": index * dt,
        "simulation_step_s": dt,
        "seed": 184729,
        "agents": [{
            "agent_id": "Porpoise_001",
            "species": "harbour_porpoise",
            "behavioural_state": "shallow_swim",
            "horizontal_position_m": [12, -4],
            "heading_deg": 90,
            "speed_mps": 0.6,
            "vertical_reference": "mean_sea_level",
            "depth_m": 0.8,
        }],
    }


class ValidationTests(unittest.TestCase):
    def assert_invalid(self, payload):
        with self.assertRaises(ValueError):
            exchange.validate_step(payload)

    def test_example_and_fixture_are_detached_snapshots(self):
        example = json.loads((ROOT / "integrations/gama/examples/step_v2.json").read_text())
        for original in (example, step()):
            with self.subTest(run_id=original["run_id"]):
                before = deepcopy(original)
                result = exchange.validate_step(original)
                self.assertEqual(result, before)
                self.assertIsNot(result, original)
                result["agents"][0]["horizontal_position_m"][0] += 100
                self.assertEqual(original, before)

    def test_all_fields_are_required_and_objects_are_strict(self):
        for field in STEP_FIELDS:
            with self.subTest(missing_step_field=field):
                payload = step()
                del payload[field]
                self.assert_invalid(payload)
        for field in AGENT_FIELDS:
            with self.subTest(missing_agent_field=field):
                payload = step()
                del payload["agents"][0][field]
                self.assert_invalid(payload)
        for payload in (None, [], "step", True, 1):
            with self.subTest(non_object=payload):
                self.assert_invalid(payload)
        for value in (None, [], "agent", True, 1):
            payload = step()
            payload["agents"] = [value]
            self.assert_invalid(payload)

    def test_exact_version_is_required_without_v1_fallback(self):
        for value in ("1.0", "2", "2.1", "", 2.0, 2, True, None, []):
            with self.subTest(version=value):
                payload = step()
                payload["schema_version"] = value
                self.assert_invalid(payload)

    def test_unknown_fields_and_ambiguous_vertical_inputs_are_rejected(self):
        for field, value in (("time_s", 1), ("position_m", [1, 0, 2]),
                             ("ocean_state", {}), ("unexpected", None)):
            with self.subTest(step_field=field):
                payload = step()
                payload[field] = value
                self.assert_invalid(payload)
        for field, value in (("position_m", [12, -0.8, -4]), ("y_m", -0.8),
                             ("height_m", 0), ("altitude_m", 0),
                             ("wave_height_m", 0), ("ocean_state", {}),
                             ("asset_path", "/tmp/foreign.usd"), ("id", "Porpoise_001"),
                             ("state", "shallow_swim"), ("unexpected", None)):
            with self.subTest(agent_field=field):
                payload = step()
                payload["agents"][0][field] = value
                self.assert_invalid(payload)

    def test_only_one_porpoise_is_supported(self):
        for agents in ([], [step()["agents"][0]] * 2, {}, None, "agents", ()):
            with self.subTest(agents=agents):
                payload = step()
                payload["agents"] = agents
                self.assert_invalid(payload)
        for species in ("bottlenose_dolphin", "Harbour_Porpoise", "", 1, None, []):
            payload = step()
            payload["agents"][0]["species"] = species
            self.assert_invalid(payload)

    def test_identifiers_are_safe_and_length_limited(self):
        for field, owner in (("run_id", "step"), ("agent_id", "agent")):
            for value in ("Run_0", "_fixture", "a" * 128):
                with self.subTest(field=field, valid=value[:20]):
                    payload = step()
                    target = payload if owner == "step" else payload["agents"][0]
                    target[field] = value
                    exchange.validate_step(payload)
            for value in ("", "a" * 129, "1run", "two words", "a/b", "../World",
                          "a-b", "a.b", "a\n", "caf\u00e9", 1, True, None, []):
                with self.subTest(field=field, invalid=value):
                    payload = step()
                    target = payload if owner == "step" else payload["agents"][0]
                    target[field] = value
                    self.assert_invalid(payload)

    def test_state_enum_is_transport_vocabulary(self):
        self.assertEqual(set(exchange.STATES), STATES)
        for state in STATES:
            payload = step()
            # Zero depth and speed are not restricted by an invented state profile.
            payload["agents"][0].update(behavioural_state=state, depth_m=0, speed_mps=0)
            exchange.validate_step(payload)
        for state in ("dive", "submerged", "flying", "Surface", "", None, []):
            payload = step()
            payload["agents"][0]["behavioural_state"] = state
            self.assert_invalid(payload)

    def test_vertical_reference_has_one_mean_level_interpretation(self):
        for value in ("wave_surface", "instantaneous_wave_surface", "absolute_y",
                      "mean_sea_plane", "", 0, None, []):
            with self.subTest(reference=value):
                payload = step()
                payload["agents"][0]["vertical_reference"] = value
                self.assert_invalid(payload)

    def test_seed_and_step_index_are_strict_safe_integers(self):
        for field in ("seed", "step_index"):
            for value in (0, MAX_SAFE_INTEGER):
                with self.subTest(field=field, valid=value):
                    payload = step()
                    payload[field] = value
                    if field == "step_index":
                        payload["simulation_time_s"] = value * payload["simulation_step_s"]
                    exchange.validate_step(payload)
            for value in (-1, MAX_SAFE_INTEGER + 1, 10**1000, 1.0, True, False,
                          "1", float("nan"), float("inf"), None):
                with self.subTest(field=field, invalid=repr(value)[:30]):
                    payload = step()
                    payload[field] = value
                    self.assert_invalid(payload)

    def test_all_scalar_numbers_reject_nonfinite_bool_and_string_values(self):
        invalid = (True, False, "1", None, [], float("nan"), float("inf"),
                   -float("inf"), 10**1000)
        for field in ("simulation_time_s", "simulation_step_s", "heading_deg", "speed_mps", "depth_m"):
            for value in invalid:
                with self.subTest(field=field, value=repr(value)[:30]):
                    payload = step()
                    target = payload if field.startswith("simulation_") else payload["agents"][0]
                    target[field] = value
                    self.assert_invalid(payload)

    def test_numeric_bounds_and_horizontal_vector_shape(self):
        for field, values in (("simulation_time_s", (-1,)), ("simulation_step_s", (0, -1)),
                              ("heading_deg", (-0.01, 360, 720)),
                              ("speed_mps", (-0.01,)), ("depth_m", (-0.01,))):
            for value in values:
                payload = step()
                target = payload if field.startswith("simulation_") else payload["agents"][0]
                target[field] = value
                self.assert_invalid(payload)
        for value in ([], [1], [1, 2, 3], (1, 2), "1,2", {"x": 1, "z": 2}, None):
            payload = step()
            payload["agents"][0]["horizontal_position_m"] = value
            self.assert_invalid(payload)
        for axis in (0, 1):
            for value in (True, "1", None, float("nan"), float("inf"), 10**1000):
                with self.subTest(axis=axis, value=repr(value)[:30]):
                    payload = step()
                    payload["agents"][0]["horizontal_position_m"][axis] = value
                    self.assert_invalid(payload)
        payload = step(0)
        payload["agents"][0].update(horizontal_position_m=[-1e300, 1e300],
                                    heading_deg=359.999999, speed_mps=1e300, depth_m=1e300)
        exchange.validate_step(payload)  # Finite transport values have no biological maximum.

    def test_time_is_index_times_step_with_absolute_tolerance_only(self):
        payload = step(3, 0.1)
        payload["simulation_time_s"] = 0.3
        exchange.validate_step(payload)  # Ordinary binary floating-point roundoff.
        for offset in (-0.5e-9, 0.5e-9):
            payload = step()
            payload["simulation_time_s"] += offset
            exchange.validate_step(payload)
        for index, dt, offset in ((4, 0.25, -2e-9), (4, 0.25, 2e-9),
                                   (10**9, 1, 0.001), (0, 0.25, 0.1)):
            with self.subTest(index=index, dt=dt, offset=offset):
                payload = step(index, dt)
                payload["simulation_time_s"] += offset
                self.assert_invalid(payload)
        payload = step()
        payload.update(step_index=MAX_SAFE_INTEGER, simulation_step_s=1e308,
                       simulation_time_s=1e308)
        self.assert_invalid(payload)  # Finite inputs whose expected time overflows.

    def test_schema_required_fields_constants_and_cardinality_match_runtime(self):
        schema = json.loads((ROOT / "integrations/gama/step_v2.schema.json").read_text())
        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["required"]), STEP_FIELDS)
        self.assertEqual(set(schema["properties"]), STEP_FIELDS)
        self.assertEqual(schema["properties"]["schema_version"]["const"], "2.0")
        agents = schema["properties"]["agents"]
        self.assertEqual(agents["minItems"], 1)
        self.assertEqual(agents["maxItems"], 1)
        agent = schema["$defs"]["agent"]
        self.assertEqual(agent["type"], "object")
        self.assertFalse(agent["additionalProperties"])
        self.assertEqual(set(agent["required"]), AGENT_FIELDS)
        self.assertEqual(set(agent["properties"]), AGENT_FIELDS)
        self.assertEqual(agent["properties"]["species"]["const"], "harbour_porpoise")
        self.assertEqual(agent["properties"]["vertical_reference"]["const"], "mean_sea_level")
        self.assertEqual(set(agent["properties"]["behavioural_state"]["enum"]), STATES)


class BufferTests(unittest.TestCase):
    def test_arbitrary_start_gaps_and_latest_retry(self):
        buffer = exchange.StepBuffer()
        self.assertIsNone(buffer.latest)
        self.assertEqual(buffer.accepted_steps, 0)
        for count, index in enumerate((7, 8, 23), 1):
            payload = step(index)
            result = buffer.accept(payload)
            self.assertTrue(result["accepted"])
            self.assertFalse(result["duplicate"])
            self.assertFalse(result["rendered"])
            self.assertEqual(buffer.latest, payload)
            self.assertEqual(buffer.accepted_steps, count)
            self.assertTrue(buffer.accept(deepcopy(payload))["duplicate"])
            self.assertEqual(buffer.accepted_steps, count)

    def test_out_of_order_and_changed_latest_steps_are_atomic(self):
        buffer = exchange.StepBuffer()
        buffer.accept(step(7))
        buffer.accept(step(10))
        before = buffer.latest
        changed = step(10)
        changed["agents"][0]["speed_mps"] = 0.7
        for payload in (step(7), step(9), changed, {}):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    buffer.accept(payload)
                self.assertEqual(buffer.latest, before)
                self.assertEqual(buffer.accepted_steps, 2)
        self.assertFalse(buffer.accept(step(11))["duplicate"])
        self.assertEqual(buffer.accepted_steps, 3)

    def test_advancing_index_requires_strictly_advancing_represented_time(self):
        # Absolute clock tolerance permits equality to index*dt after rounding;
        # it does not permit replay to advance without represented clock progress.
        cases = [
            (step(0, 1e-10), step(1, 1e-10), 0),
            (step(4, 1e-10), step(5, 1e-10), 4e-10),
            (step(4, 1e-10), step(5, 1e-10), 3e-10),
            (step(9007199254740989, 0.1), step(9007199254740990, 0.1), None),
        ]
        for initial, later, reported_time in cases:
            with self.subTest(dt=initial["simulation_step_s"],
                              index=later["step_index"], reported_time=reported_time):
                if reported_time is not None:
                    later["simulation_time_s"] = reported_time
                self.assertGreater(later["step_index"], initial["step_index"])
                self.assertLessEqual(later["simulation_time_s"], initial["simulation_time_s"])
                exchange.validate_step(later)  # Structurally valid and within clock tolerance.
                buffer = exchange.StepBuffer()
                buffer.accept(initial)
                with self.assertRaises(ValueError):
                    buffer.accept(later)
                self.assertEqual(buffer.latest, initial)
                self.assertEqual(buffer.accepted_steps, 1)
                advancing = step(later["step_index"] + 1, later["simulation_step_s"])
                self.assertGreater(advancing["simulation_time_s"], initial["simulation_time_s"])
                self.assertFalse(buffer.accept(advancing)["duplicate"])
                self.assertEqual(buffer.accepted_steps, 2)

    def test_run_seed_timestep_and_agent_identity_are_fixed_until_reset(self):
        for field in ("run_id", "seed", "simulation_step_s", "agent_id"):
            with self.subTest(field=field):
                buffer = exchange.StepBuffer()
                original = step(7)
                buffer.accept(original)
                changed = step(8)
                if field == "agent_id":
                    changed["agents"][0][field] = "Porpoise_002"
                elif field == "run_id":
                    changed[field] = "Other_run"
                elif field == "seed":
                    changed[field] += 1
                else:
                    changed[field] = 0.5
                    changed["simulation_time_s"] = changed["step_index"] * changed[field]
                with self.assertRaises(ValueError):
                    buffer.accept(changed)
                self.assertEqual(buffer.latest, original)
                self.assertEqual(buffer.accepted_steps, 1)
                buffer.reset()
                self.assertIsNone(buffer.latest)
                self.assertEqual(buffer.accepted_steps, 0)
                self.assertFalse(buffer.accept(changed)["duplicate"])
                self.assertEqual(buffer.latest, changed)

    def test_input_and_latest_access_cannot_mutate_accepted_state(self):
        buffer = exchange.StepBuffer()
        original = step()
        expected = deepcopy(original)
        buffer.accept(original)
        original["agents"][0]["horizontal_position_m"][0] = 999
        original["run_id"] = "Mutated_input"
        view = buffer.latest
        view["agents"].clear()
        view["seed"] = 0
        self.assertEqual(buffer.latest, expected)
        self.assertTrue(buffer.accept(expected)["duplicate"])
        self.assertEqual(buffer.accepted_steps, 1)

    def test_valid_behaviour_and_pose_fields_can_evolve(self):
        buffer = exchange.StepBuffer()
        buffer.accept(step(0))
        changed = step(1)
        changed["agents"][0].update(behavioural_state="descent", horizontal_position_m=[13, -5],
                                    heading_deg=180, speed_mps=0.8, depth_m=1.5)
        self.assertFalse(buffer.accept(changed)["duplicate"])
        self.assertEqual(buffer.latest, changed)


class TransformTests(unittest.TestCase):
    def test_units_depth_and_all_cardinal_headings(self):
        for units in (1, 0.01):
            for heading, forward in ((0, (0, 0, 1)), (90, (1, 0, 0)),
                                     (180, (0, 0, -1)), (270, (-1, 0, 0))):
                with self.subTest(units=units, heading=heading):
                    payload = step()
                    payload["agents"][0]["heading_deg"] = heading
                    before = deepcopy(payload)
                    transforms = exchange.preview_transforms(payload, units)
                    self.assertEqual(payload, before)
                    self.assertEqual(len(transforms), 1)
                    result = transforms[0]
                    self.assertEqual(result["id"], "Porpoise_001")
                    self.assertEqual(result["position_m"], [12, -0.8, -4])
                    self.assertEqual(result["vertical_reference"], "mean_sea_level")
                    self.assertEqual(result["heading_deg"], heading)
                    for actual, expected in zip(result["forward_y_up"], forward):
                        self.assertAlmostEqual(actual, expected)
                    for actual, expected in zip(result["position_scene_units"], (12 / units, -0.8 / units, -4 / units)):
                        self.assertAlmostEqual(actual, expected)
                    self.assertAlmostEqual(result["speed_scene_units_per_s"], 0.6 / units)

    def test_zero_depth_resolves_to_mean_plane_for_every_state(self):
        for state in STATES:
            payload = step()
            payload["agents"][0].update(behavioural_state=state, depth_m=0)
            self.assertEqual(exchange.preview_transforms(payload, 1)[0]["position_m"][1], 0)

    def test_invalid_stage_units_and_payload_are_rejected(self):
        for units in (0, -1, True, False, "0.01", None, float("nan"),
                      float("inf"), 10**1000):
            with self.subTest(units=repr(units)[:30]):
                with self.assertRaises(ValueError):
                    exchange.preview_transforms(step(), units)
        payload = step()
        payload["agents"][0]["position_m"] = [12, -0.8, -4]
        with self.assertRaises(ValueError):
            exchange.preview_transforms(payload, 0.01)

    def test_conversion_overflow_is_rejected_without_changing_input(self):
        for field in ("horizontal_position_m", "depth_m", "speed_mps"):
            with self.subTest(field=field):
                payload = step()
                payload["agents"][0][field] = [1e308, 0] if field == "horizontal_position_m" else 1e308
                before = deepcopy(payload)
                with self.assertRaises(ValueError):
                    exchange.preview_transforms(payload, 1e-300)
                self.assertEqual(payload, before)


if __name__ == "__main__":
    unittest.main()
