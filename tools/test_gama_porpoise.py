"""Synthetic XML parser/acceptance tests; these fixtures are NOT GAMA evidence."""
from copy import deepcopy
import json
import math
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

import gama_porpoise as runner


class PorpoiseExportTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(runner.CONFIG.read_text())
        self.run_id = "unit_fixture_not_gama"
        self.seed = 184729
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "synthetic.xml"

    def fixture(self):
        """Construct a labelled test fixture solely to exercise rejection paths."""
        p = self.config["parameters"]
        root = ET.Element("Simulation", id="0")
        for index in range(runner.validate_config(self.config)):
            t = index*p["step"]
            state, depth = runner.expected_vertical(t, p)
            angle = 30 + math.degrees(p["horizontal_speed_mps"]*t/p["path_radius_m"])
            values = {"schema_version": "2.0", "run_id": self.run_id,
                      "agent_id": "Porpoise_001", "species": "harbour_porpoise",
                      "vertical_reference": "mean_sea_level", "agent_count": 1,
                      "step_index": index, "simulation_time_s": t,
                      "simulation_step_s": p["step"], "actual_seed": self.seed,
                      "initial_phase_deg": 30.0, "behavioural_state": state,
                      "x_m": p["path_radius_m"]*math.sin(math.radians(angle)),
                      "z_m": p["path_radius_m"]*math.cos(math.radians(angle)),
                      "heading_deg": (angle+90)%360,
                      "speed_mps": p["horizontal_speed_mps"], "depth_m": depth,
                      **{n: p[n] for n in runner.PARAMETERS if n not in ("step", "horizontal_speed_mps")}}
            entry = ET.SubElement(root, "Step", id=str(index))
            for name in runner.OUTPUTS:
                ET.SubElement(entry, "Variable", name=name).text = str(values[name])
        return root

    def parse(self, root):
        ET.ElementTree(root).write(self.path, encoding="utf-8", xml_declaration=True)
        return runner.read_trajectory(self.path, self.config, self.run_id, self.seed)

    def change(self, root, name, value, index=0):
        variable = next(v for v in root[index].findall("Variable") if v.attrib["name"] == name)
        variable.text = str(value)

    def test_complete_fixture_preserves_exported_values_and_transitions(self):
        states, result = self.parse(self.fixture())
        self.assertEqual(len(states), 41)
        self.assertEqual([r["simulation_time_s"] for r in result["transitions"]], [0, 2, 6, 10, 14, 18])
        self.assertEqual(states[0]["agents"][0]["horizontal_position_m"], [8*math.sin(math.radians(30)), 8*math.cos(math.radians(30))])
        self.assertEqual(result["depth_range_m"], [.2, 3.0])
        self.assertFalse(result["biological_approval"])

    def test_truncated_reordered_duplicate_steps_rejected(self):
        for kind in ("truncated", "reordered", "duplicate"):
            with self.subTest(kind=kind):
                root = self.fixture()
                if kind == "truncated":
                    root.remove(root[-1])
                elif kind == "reordered":
                    root[0], root[1] = root[1], root[0]
                else:
                    root[1].set("id", "0")
                with self.assertRaises(ValueError):
                    self.parse(root)

    def test_missing_unknown_and_duplicate_variables_rejected(self):
        for kind in ("missing", "unknown", "duplicate"):
            root = self.fixture()
            if kind == "missing":
                root[0].remove(root[0][0])
            else:
                ET.SubElement(root[0], "Variable", name="foreign" if kind == "unknown" else "x_m").text = "0"
            with self.assertRaises(ValueError):
                self.parse(root)

    def test_wrong_actual_seed_run_identity_or_agent_count_rejected(self):
        for name, value in (("actual_seed", 42), ("actual_seed", 184729.5),
                            ("run_id", "another_run"), ("agent_count", 2)):
            root = self.fixture()
            self.change(root, name, value)
            with self.assertRaises(ValueError):
                self.parse(root)

    def test_mislabelled_state_depth_and_lost_motion_rejected(self):
        for name, value, index in (("behavioural_state", "surface", 12),
                                   ("depth_m", .8, 20), ("x_m", 100, 4),
                                   ("heading_deg", 0, 1), ("simulation_time_s", 4, 1)):
            root = self.fixture()
            self.change(root, name, value, index)
            with self.assertRaises(ValueError):
                self.parse(root)

    def test_effective_configuration_and_phase_must_remain_fixed(self):
        for name, value in (("path_radius_m", 9), ("speed_mps", .6),
                            ("initial_surface_s", 3), ("simulation_step_s", 1),
                            ("initial_phase_deg", 31)):
            root = self.fixture()
            self.change(root, name, value, index=1)
            with self.assertRaises(ValueError):
                self.parse(root)

    def test_nonfinite_raw_values_rejected(self):
        for name in ("actual_seed", "x_m", "depth_m", "heading_deg", "simulation_time_s"):
            for value in ("nan", "inf", "-inf"):
                root = self.fixture()
                self.change(root, name, value)
                with self.assertRaises(ValueError):
                    self.parse(root)

    def test_v2_unknown_species_datum_and_version_rejected(self):
        for name, value in (("schema_version", "1.0"), ("species", "bottlenose_dolphin"),
                            ("vertical_reference", "wave_surface"), ("agent_id", "../World")):
            root = self.fixture()
            self.change(root, name, value)
            with self.assertRaises(ValueError):
                self.parse(root)

    def test_config_rejects_zero_steps_misaligned_duration_and_biological_claim(self):
        for field, value in (("step", 0), ("descent_s", 4.1), ("surface_depth_m", 4),
                             ("path_radius_m", float("nan"))):
            config = deepcopy(self.config)
            config["parameters"][field] = value
            with self.assertRaises(ValueError):
                runner.validate_config(config)
        config = deepcopy(self.config)
        config["biological_approval"] = True
        with self.assertRaises(ValueError):
            runner.validate_config(config)

    def test_canonical_comparison_excludes_only_run_identity(self):
        states, _ = self.parse(self.fixture())
        other = deepcopy(states)
        for state in other:
            state["run_id"] = "another_execution"
        self.assertEqual(runner.canonical_states(states), runner.canonical_states(other))
        other[0]["agents"][0]["depth_m"] += .1
        self.assertNotEqual(runner.canonical_states(states), runner.canonical_states(other))

    def test_existing_output_is_refused_before_execution(self):
        with self.assertRaisesRegex(ValueError, "already exists"):
            runner.execute(self.run_id, self.seed, Path(self.directory.name))


if __name__ == "__main__":
    unittest.main()
