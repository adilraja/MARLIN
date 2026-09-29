"""Regression checks for the M3 sampler; stdlib only, no Kit or live scene."""

import copy
import importlib.util
import json
import math
from pathlib import Path
import random
import shutil
import tempfile
import unittest
from unittest import mock


EXPERIMENT = Path(__file__).resolve().parents[1]
loader = importlib.util.spec_from_file_location("marlin_m3_sampling", EXPERIMENT / "scenes/sampling.py")
sampling = importlib.util.module_from_spec(loader)
loader.loader.exec_module(sampling)


class SamplingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.initial = {species: sampling.sample_scene(species, 0)
                       for species in sampling.SPECIES}

    def scratch_inputs(self):
        temporary = tempfile.TemporaryDirectory(prefix="marlin-m3-test-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / "wildlife").mkdir()
        shutil.copyfile(EXPERIMENT / "specification.json", root / "specification.json")
        for species in sampling.SPECIES:
            shutil.copyfile(EXPERIMENT / f"wildlife/{species}.json", root / f"wildlife/{species}.json")
        return root

    def assert_rejected_even_if_rehashed(self, manifest):
        manifest["manifest_sha256"] = sampling.manifest_hash(manifest)
        with self.assertRaises(ValueError):
            sampling.validate_manifest(manifest)

    def test_repeatable_after_random_order_and_global_rng_changes(self):
        ids = [(species, index) for species in sampling.SPECIES for index in (0, 1, 7, 24)]
        first = {item: sampling.canonical_json(sampling.sample_scene(*item)) for item in ids}
        random.Random(1007).shuffle(ids)
        random.seed(917)  # Neither sampling nor draws may depend on module RNG.
        for item in ids:
            self.assertEqual(first[item], sampling.canonical_json(sampling.sample_scene(*item)))
        self.assertEqual(len(set(first.values())), len(ids))

    def test_named_draws_do_not_consume_shared_random_state(self):
        seed = self.initial[sampling.SPECIES[0]]["random"]["condition_seed"]
        expected = sampling._draw(seed, "x_m", [-0.6, 0.6])
        for index in range(100):
            sampling._draw(seed, f"unrelated_{index}", [0.0, 1.0])
        self.assertEqual(expected, sampling._draw(seed, "x_m", [-0.6, 0.6]))
        self.assertNotEqual(expected, sampling._draw(seed, "z_m", [-0.6, 0.6]))

    def test_mutating_returned_ranges_does_not_change_future_sampling(self):
        first = sampling.sample_scene("harbour_porpoise", 0)
        expected = sampling.canonical_json(first)
        first["sampling"]["ranges"]["x_m"][0] = -99.0
        self.assertEqual(expected, sampling.canonical_json(sampling.sample_scene("harbour_porpoise", 0)))

    def test_live_input_files_and_frozen_calibration_hashes(self):
        for species, manifest in self.initial.items():
            self.assertTrue(sampling.validate_manifest(manifest))
            self.assertEqual(sampling.CALIBRATION_SHA256[species], manifest["calibration"]["sha256"])
            for dependency in manifest["calibration"]["asset_dependencies"]:
                self.assertEqual(dependency["sha256"], sampling._file_sha256(sampling.PROJECT_ROOT / dependency["path"]))
            helper = sampling._load_seed_helper()
            self.assertEqual(helper(20260929, manifest["scene_id"]), manifest["random"]["condition_seed"])

    def test_geometry_ranges_and_shallow_clearance(self):
        for species in sampling.SPECIES:
            for index in (0, 1, 24, 25, 999999999):
                manifest = sampling.sample_scene(species, index)
                animal = manifest["animal"]
                x, y, z = animal["position_m"]
                self.assertTrue(-0.6 <= x < 0.6)
                self.assertTrue(-0.6 <= z < 0.6)
                self.assertTrue(0.0 <= animal["heading_deg"] < 360.0)
                self.assertEqual(animal["pitch_deg"], 0.0)
                self.assertEqual(animal["roll_deg"], 0.0)
                self.assertEqual(animal["pose_time_code"], 1)
                self.assertEqual(animal["state"], sampling.STATES[species])
                if species == "european_storm_petrel":
                    self.assertTrue(0.75 <= y < 1.25)
                    self.assertGreater(animal["world_y_bounds_m"][0], 0.0)
                    self.assertIsNone(animal["clearance_m"])
                else:
                    self.assertTrue(0.02 <= animal["clearance_m"] < 0.08)
                    self.assertAlmostEqual(animal["world_y_bounds_m"][1], -animal["clearance_m"], places=14)
                for draw in manifest["random"]["subdraws"].values():
                    self.assertTrue(0 <= draw["unit_interval_value"] < 1)

    def test_candidate_ids_and_explicit_replacement_role(self):
        first = sampling.sample_scene("harbour_porpoise", 24)
        replacement = sampling.sample_scene("harbour_porpoise", 25)
        self.assertEqual(first["scene_id"], "harbour_porpoise_0024")
        self.assertEqual(first["candidate_role"], "initial")
        self.assertEqual(replacement["scene_id"], "harbour_porpoise_0025")
        self.assertEqual(replacement["candidate_role"], "replacement_requires_retained_rejection_record")
        for key in ("scene_id", "asset_instance_id", "sequence_id", "condition_id"):
            self.assertNotEqual(first[key], replacement[key])

    def test_invalid_identifiers_fail_closed(self):
        for index in (-1, True, False, 0.0, "0", None, 1000000000):
            with self.subTest(index=index), self.assertRaises(ValueError):
                sampling.sample_scene("harbour_porpoise", index)
        for species in ("unknown", "../harbour_porpoise", "HARBOUR_PORPOISE", True, None, []):
            with self.subTest(species=species), self.assertRaises(ValueError):
                sampling.sample_scene(species, 0)

    def test_gsd_is_only_camera_altitude_and_not_random_input(self):
        for manifest in self.initial.values():
            self.assertFalse(manifest["random"]["gsd_used"])
            self.assertFalse(any("gsd" in label for label in manifest["random"]["subdraws"]))
            y = manifest["animal"]["position_m"][1]
            camera = manifest["camera"]
            self.assertEqual(camera["shared"]["image_up_world_axis"], "-Z")
            self.assertEqual(camera["shared"]["image_size_px"], [1024, 768])
            self.assertEqual(len(camera["variants"]), 5)
            for variant, gsd, separation in zip(camera["variants"], sampling.GSD_LEVELS, sampling.SEPARATIONS_M):
                self.assertEqual(set(variant), {"requested_gsd_cm_px", "position_m", "reference_plane_y_m", "separation_m"})
                self.assertEqual(variant["position_m"], [0.0, y + separation, 0.0])
                self.assertEqual(variant["reference_plane_y_m"], y)
                self.assertEqual(variant["requested_gsd_cm_px"], gsd)
                self.assertAlmostEqual(separation * 5.0 / 50.0 * 0.1, gsd)
            corrupted = copy.deepcopy(manifest)
            corrupted["camera"]["variants"][0]["position_m"][0] = 0.1
            self.assert_rejected_even_if_rehashed(corrupted)

    def test_hash_is_order_independent_and_ignores_only_self_hash(self):
        manifest = self.initial[sampling.SPECIES[0]]
        reordered = dict(reversed(list(manifest.items())))
        self.assertEqual(sampling.manifest_hash(manifest), sampling.manifest_hash(reordered))
        reordered["manifest_sha256"] = "unused"
        self.assertEqual(sampling.manifest_hash(manifest), sampling.manifest_hash(reordered))
        reordered["extra"] = None
        self.assertNotEqual(sampling.manifest_hash(manifest), sampling.manifest_hash(reordered))

    def test_missing_extra_corrupted_and_rehashed_fields_rejected(self):
        base = self.initial[sampling.SPECIES[0]]
        corrupted = copy.deepcopy(base)
        corrupted["animal"]["position_m"][0] = 99.0
        with self.assertRaises(ValueError):
            sampling.validate_manifest(corrupted)
        self.assert_rejected_even_if_rehashed(corrupted)
        for operation in ("missing", "extra", "schema", "boolean_index", "scale", "seed"):
            corrupted = copy.deepcopy(base)
            if operation == "missing":
                del corrupted["animal"]["state"]
            elif operation == "extra":
                corrupted["animal"]["hidden_randomisation"] = True
            elif operation == "schema":
                corrupted["schema_version"] = "2.0.0"
            elif operation == "boolean_index":
                corrupted["candidate_index"] = False
            elif operation == "scale":
                corrupted["animal"]["scale"] *= 2
            else:
                corrupted["random"]["condition_seed"] += 1
            with self.subTest(operation=operation):
                self.assert_rejected_even_if_rehashed(corrupted)

    def test_nonfinite_and_non_json_values_rejected(self):
        for value in (math.nan, math.inf, -math.inf, (1, 2), object(), {1: "value"}):
            corrupted = copy.deepcopy(self.initial[sampling.SPECIES[0]])
            corrupted["extra"] = value
            with self.subTest(value=str(value)), self.assertRaises(ValueError):
                sampling.validate_manifest(corrupted)

    def test_calibration_file_change_and_missing_file_rejected(self):
        root = self.scratch_inputs()
        path = root / "wildlife/harbour_porpoise.json"
        path.write_text(path.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "calibration hash changed"):
            sampling.validate_manifest(self.initial["harbour_porpoise"], root)
        path.unlink()
        with self.assertRaises(ValueError):
            sampling.sample_scene("harbour_porpoise", 0, root)

    def test_dependency_hash_changes_rejected_without_touching_assets(self):
        manifest = self.initial["harbour_porpoise"]
        dependency_path = (sampling.PROJECT_ROOT / manifest["calibration"]["asset_dependencies"][-1]["path"]).resolve()
        original = sampling._file_sha256
        def changed_hash(path):
            return "0" * 64 if path.resolve() == dependency_path else original(path)
        with mock.patch.object(sampling, "_file_sha256", side_effect=changed_hash):
            with self.assertRaisesRegex(ValueError, "dependency hash changed"):
                sampling.validate_manifest(manifest)

    def test_changed_specification_contract_rejected(self):
        root = self.scratch_inputs()
        path = root / "specification.json"
        original = json.loads(path.read_text())
        for group, key, value in (("camera", "focal_length_mm", 55.0),
                                  ("scene_generation", "master_seed", True),
                                  ("scene_generation", "gsd_in_biological_seed", True),
                                  ("coordinates", "up_axis", "Z")):
            modified = copy.deepcopy(original)
            modified[group][key] = value
            path.write_text(json.dumps(modified))
            with self.subTest(key=key), self.assertRaises(ValueError):
                sampling.sample_scene("harbour_porpoise", 0, root)
        path.write_text('{"schema_version":"1.2.0","schema_version":"1.1.0"}')
        with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
            sampling.sample_scene("harbour_porpoise", 0, root)

    def test_schema_12_ranges_and_provenance_must_match_frozen_contract(self):
        root = self.scratch_inputs()
        path = root / "specification.json"
        original = json.loads(path.read_text())
        original["schema_version"] = "1.2.0"
        original["targets"]["state_conditioned_sampling_ranges"] = {
            "values": copy.deepcopy(sampling.SAMPLING_RANGES),
            "status": sampling.RANGE_PROVENANCE,
            "pitch_deg": 0, "roll_deg": 0, "pose_time_code": 1}
        path.write_text(json.dumps(original))
        self.assertTrue(sampling.validate_manifest(sampling.sample_scene("harbour_porpoise", 0, root), root))
        for mutation in ("range", "provenance", "pitch", "pose", "missing"):
            modified = copy.deepcopy(original)
            ranges = modified["targets"]["state_conditioned_sampling_ranges"]
            if mutation == "range": ranges["values"]["porpoise_top_clearance_m"][1] = 0.5
            elif mutation == "provenance": ranges["status"] = "biologically_validated"
            elif mutation == "pitch": ranges["pitch_deg"] = True
            elif mutation == "pose": ranges["pose_time_code"] = 2
            else: modified["targets"]["state_conditioned_sampling_ranges"] = None
            path.write_text(json.dumps(modified))
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, "sampling ranges differ"):
                sampling.sample_scene("harbour_porpoise", 0, root)


if __name__ == "__main__":
    unittest.main()
