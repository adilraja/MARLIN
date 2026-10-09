"""Measured-M3 integration and explicitly synthetic mutation/rotation fixtures.

Derived fixtures exercise analysis rejection paths. They are not additional GAMA
executions, stochastic evidence, or biological validation.
"""
from copy import deepcopy
import json
import math
import unittest

import analyze_gama_porpoise as analyzer
import gama_porpoise as runner


class PorpoiseAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(runner.CONFIG.read_text())
        directory = runner.ROOT / "experiments/gama_marlin_v1/trajectories/m3_seed_184729_a"
        cls.actual = json.loads((directory / "trajectory.json").read_text())
        cls.actual_phase = json.loads((directory / "validation.json").read_text())["initial_phase_deg"]

    def fixture(self, seed=7, phase=265, run_id="synthetic_analysis_fixture"):
        """Rotate retained values solely to create a labelled synthetic fixture."""
        states = deepcopy(self.actual)
        angle = math.radians(phase - self.actual_phase)
        for state in states:
            state.update(seed=seed, run_id=run_id)
            agent = state["agents"][0]
            x, z = agent["horizontal_position_m"]
            agent["horizontal_position_m"] = [x * math.cos(angle) + z * math.sin(angle), -x * math.sin(angle) + z * math.cos(angle)]
            agent["heading_deg"] = (agent["heading_deg"] + phase - self.actual_phase) % 360
        return {"states": states, "validation": {"initial_phase_deg": phase}, "fixture_not_gama_execution": True}

    def test_actual_retained_m3_has_declared_constraints_and_no_biological_approval(self):
        result = analyzer.metrics(self.actual, self.config)
        self.assertTrue(result["passed"], result["checks"])
        self.assertFalse(result["biological_approval"])
        self.assertEqual(result["samples"], 41)
        self.assertEqual(result["depth_range_m"], [.2, 3])
        self.assertEqual([row["simulation_time_s"] for row in result["transitions"]], [0, 2, 6, 10, 14, 18])

    def test_interval_durations_do_not_count_final_sample_as_extra_exposure(self):
        result = analyzer.metrics(self.actual, self.config)
        self.assertEqual(result["coverage_s"], {state: 4 for state in ("surface", "shallow_swim", "descent", "submerged_swim", "ascent")})
        self.assertEqual(sum(result["coverage_s"].values()), 20)
        self.assertEqual([e["duration_s"] for e in result["episodes"]], [2, 4, 4, 4, 4, 2])
        self.assertEqual([e["right_censored"] for e in result["episodes"]], [False] * 5 + [True])
        self.assertEqual(len(result["interval_series"]), 40)

    def test_wrapped_headings_preserve_positive_small_turn_rate(self):
        states = self.fixture()["states"]
        headings = [s["agents"][0]["heading_deg"] for s in states]
        self.assertTrue(any(b < a for a, b in zip(headings, headings[1:])))
        result = analyzer.metrics(states, self.config)
        self.assertTrue(result["passed"], result["checks"])
        self.assertAlmostEqual(result["turn_rate_deg_per_s"]["min"], 3.5809862195676, places=10)
        self.assertAlmostEqual(result["turn_rate_deg_per_s"]["max"], 3.5809862195676, places=10)

    def test_chord_speed_is_lower_than_instantaneous_metadata_speed(self):
        result = analyzer.metrics(self.actual, self.config)
        self.assertEqual(result["exported_speed_mps"]["mean"], .5)
        self.assertAlmostEqual(result["horizontal_chord_speed_mps"]["mean"], .49997965519627, places=12)
        self.assertLess(result["horizontal_chord_speed_mps"]["max"], .5)
        self.assertAlmostEqual(result["horizontal_polyline_length_m"], 9.999593103925365, places=11)
        self.assertEqual(result["declared_continuous_horizontal_length_m"], 10)

    def test_depth_secants_are_signed_and_distinct_from_continuous_peaks(self):
        result = analyzer.metrics(self.actual, self.config)
        self.assertAlmostEqual(result["depth_secant_mps"]["min"], -1.028125)
        self.assertAlmostEqual(result["depth_secant_mps"]["max"], .8078125)
        self.assertAlmostEqual(result["continuous_vertical_peak_mps"]["descent"], .825)
        self.assertAlmostEqual(result["continuous_vertical_peak_mps"]["ascent"], -1.05)
        descent = [r for r in result["interval_series"] if r["state"] == "descent"]
        ascent = [r for r in result["interval_series"] if r["state"] == "ascent"]
        self.assertTrue(all(r["depth_secant_mps"] > 0 for r in descent))
        self.assertTrue(all(r["depth_secant_mps"] < 0 for r in ascent))
        self.assertGreater(result["three_dimensional_chord_speed_mps"]["max"], .5)

    def test_altered_valid_depth_state_speed_heading_and_position_fail_constraints(self):
        for name, value, check in (("depth_m", .7, "declared_depth_evolution"),
                                    ("behavioural_state", "ascent", "declared_state_labels"),
                                    ("speed_mps", .7, "exported_horizontal_speed"),
                                    ("heading_deg", 180, "tangent_heading"),
                                    ("horizontal_position_m", [7, 7], "circle_and_phase")):
            with self.subTest(name=name):
                states = deepcopy(self.actual)
                states[7]["agents"][0][name] = value
                result = analyzer.metrics(states, self.config)
                self.assertFalse(result["passed"])
                self.assertFalse(result["checks"][check])

    def test_final_sample_has_zero_exposure_but_its_state_is_still_validated(self):
        states = deepcopy(self.actual)
        states[-1]["agents"][0]["behavioural_state"] = "shallow_swim"
        result = analyzer.metrics(states, self.config)
        self.assertEqual(sum(result["coverage_s"].values()), 20)
        self.assertFalse(result["checks"]["declared_state_labels"])
        self.assertFalse(result["passed"])

    def test_truncation_and_missing_sample_fail_complete_trajectory_checks(self):
        for states in (deepcopy(self.actual[:-1]), deepcopy(self.actual[:7] + self.actual[8:])):
            result = analyzer.metrics(states, self.config)
            self.assertFalse(result["passed"])
            self.assertFalse(result["checks"]["complete_sample_count"])

    def test_contract_rejects_nonfinite_unknown_fields_changed_identity_and_duplicates(self):
        for kind in ("nonfinite", "extra", "identity", "duplicate", "reordered"):
            states = deepcopy(self.actual)
            if kind == "nonfinite":
                states[1]["agents"][0]["depth_m"] = float("nan")
            elif kind == "extra":
                states[1]["agents"][0]["world_y_m"] = -1
            elif kind == "identity":
                states[1]["agents"][0]["agent_id"] = "Other_Animal"
            elif kind == "duplicate":
                states.insert(1, deepcopy(states[0]))
            else:
                states[1], states[2] = states[2], states[1]
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                analyzer.metrics(states, self.config)

    def test_phase_only_synthetic_variation_passes_geometric_checks(self):
        runs = [self.fixture(7, 265), self.fixture(8, 30), self.fixture(9, 120)]
        result = analyzer.compare_seed_variation(runs, self.config)
        self.assertTrue(result["passed"], result["checks"])
        self.assertEqual(result["seeds"], [7, 8, 9])
        self.assertFalse(result["biological_approval"])

    def test_seed_field_change_alone_cannot_prove_variation(self):
        first = self.fixture()
        second = deepcopy(first)
        for state in second["states"]:
            state["seed"] = 99
        result = analyzer.compare_seed_variation([first, second], self.config)
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["distinct_initial_phases"])
        self.assertFalse(result["checks"]["distinct_initial_positions"])

    def test_falsified_phase_claim_does_not_prove_geometric_variation(self):
        first = self.fixture()
        second = deepcopy(first)
        second["validation"]["initial_phase_deg"] += 10
        for state in second["states"]:
            state["seed"] = 99
        result = analyzer.compare_seed_variation([first, second], self.config)
        self.assertFalse(result["checks"]["phase_matches_first_position"])
        self.assertFalse(result["checks"]["phase_only_position_variation"])
        self.assertFalse(result["passed"])

    def test_cross_seed_altered_depth_label_speed_or_turning_fails(self):
        for name, value in (("depth_m", .7), ("behavioural_state", "ascent"),
                            ("speed_mps", .7), ("heading_deg", 180)):
            first, second = self.fixture(7, 265), self.fixture(8, 30)
            second["states"][7]["agents"][0][name] = value
            with self.subTest(name=name):
                result = analyzer.compare_seed_variation([first, second], self.config)
                self.assertFalse(result["passed"])
                self.assertFalse(result["checks"]["all_runs_meet_model_constraints"])

    def test_variation_requires_distinct_primary_seeds_and_finite_exported_phases(self):
        result = analyzer.compare_seed_variation([self.fixture(7, 265), self.fixture(7, 30)], self.config)
        self.assertFalse(result["checks"]["distinct_primary_seeds"])
        for phase in (None, True, -1, 360, float("inf")):
            run = self.fixture()
            run["validation"]["initial_phase_deg"] = phase
            with self.subTest(phase=phase), self.assertRaises(ValueError):
                analyzer.compare_seed_variation([run, self.fixture(8, 30)], self.config)


if __name__ == "__main__":
    unittest.main()
