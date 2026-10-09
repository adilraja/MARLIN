"""Pure pending-selection and aggregate-copy tests; no HTTP, Kit or USD.

Selection fixtures are copies of the actual failed M7 attempt and its immutable
declaration. Small filesystem fixtures exercise copying only; they are never
claimed to be experiment states or accepted rendered groups.
"""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import capture_gama_dataset_pending_v2 as pending
import aggregate_gama_dataset_v2 as aggregate


class PendingSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.campaign = pending.DEFAULT_SOURCE
        cls.declaration = json.loads((cls.campaign / "declaration.json").read_text())
        cls.report = json.loads((cls.campaign / "results.json").read_text())
        cls.before = {name: pending.capture.pin(cls.campaign / name)
                      for name in ("declaration.json", "results.json")}

    @classmethod
    def tearDownClass(cls):
        after = {name: pending.capture.pin(cls.campaign / name) for name in cls.before}
        if after != cls.before:
            raise AssertionError("Actual declaration or failed campaign evidence changed")

    def reject(self, change):
        declaration, report = deepcopy(self.declaration), deepcopy(self.report)
        change(declaration, report)
        with self.assertRaises(ValueError):
            pending.select_pending(declaration, report)

    def test_actual_failed_attempt_selects_only_three_declared_missing_test_states(self):
        selection = pending.select_pending(self.declaration, self.report)
        expected = [(pending.PENDING_RUN, step) for step in (8, 16, 32)]
        self.assertEqual(selection["pending_keys"], expected)
        self.assertEqual(len(selection["accepted_keys"]), 12)
        self.assertEqual(len(set(selection["accepted_keys"])), 12)
        self.assertTrue(all(run != pending.PENDING_RUN for run, _ in selection["accepted_keys"]))
        self.assertIs(self.report["passed"], False)
        self.assertIs(self.report["runs"][-1]["passed"], False)
        for run, step in expected:
            state = next(state for row in self.declaration["runs"] if row["run_id"] == run
                         for state in row["selected_states"] if state["step_index"] == step)
            self.assertEqual(state["seed"], 2147483647)
            self.assertEqual(state["step_index"], step)

    def test_rejects_success_reclassification_or_preflight_or_approval_claim(self):
        for field, value in (("passed", True), ("preflight_only", True),
                             ("biological_approval", True), ("declaration_unchanged", False),
                             ("runtime_code_unchanged", False)):
            with self.subTest(field=field):
                self.reject(lambda _, r: r.update({field: value}))

    def test_rejects_changed_protocol_source_or_failed_preservation(self):
        self.reject(lambda _, r: r["runtime_code_after"][0].update(sha256="0" * 64))
        self.reject(lambda _, r: r["preservation_after"][0].update(passed=False))
        self.reject(lambda _, r: r.update(preservation_before=[]))

    def test_rejects_wrong_or_reordered_actual_run_identities(self):
        self.reject(lambda _, r: r["runs"].reverse())
        self.reject(lambda _, r: r["runs"][0].update(seed=42))
        self.reject(lambda _, r: r["runs"][0].update(split="test"))
        self.reject(lambda _, r: r["runs"][0].update(encounter_group_id="replacement"))

    def test_rejects_missing_or_duplicate_declared_snapshots(self):
        self.reject(lambda d, _: d["runs"][0]["selected_states"].pop())
        self.reject(lambda d, _: d["runs"][0]["selected_states"].append(
            deepcopy(d["runs"][0]["selected_states"][0])))

    def test_rejects_duplicate_or_undeclared_accepted_group(self):
        self.reject(lambda _, r: r["runs"][0]["groups"].append(
            deepcopy(r["runs"][0]["groups"][0])))
        self.reject(lambda _, r: r["runs"][0]["groups"][0].update(step_index=31))
        self.reject(lambda _, r: r["runs"][0]["groups"][0].update(run_id=pending.PENDING_RUN))

    def test_rejects_substituted_source_state_or_group_split(self):
        self.reject(lambda _, r: r["runs"][0]["groups"][0]["source_state"]["agents"][0].update(depth_m=.6))
        self.reject(lambda _, r: r["runs"][0]["groups"][0].update(split="test"))

    def test_rejects_accepted_group_without_held_pose_or_coexistence(self):
        self.reject(lambda _, r: r["runs"][0]["groups"][0].update(held_state=False))
        self.reject(lambda _, r: r["runs"][0]["groups"][0].update(retained_group=None))
        self.reject(lambda _, r: r["runs"][0]["groups"][0].update(coexistence_checks={"layers_restored": False}))

    def test_rejects_source_cleanup_failure_or_status_reclassification(self):
        self.reject(lambda _, r: r["runs"][0].update(cleanup_error="failed release"))
        self.reject(lambda _, r: r["runs"][-1]["cleanup_checks"].update(actor_released=False))
        self.reject(lambda _, r: r["runs"][-1].update(passed=True))

    def test_rejects_failed_capture_with_rendered_evidence_or_nonheadroom_error(self):
        self.reject(lambda _, r: r["runs"][-1]["groups"][0].update(retained_group={"directory": "fixture"}))
        self.reject(lambda _, r: r["runs"][-1]["groups"][0]["capture_attempts"][0].update(
            response={"ok": False, "error": "Renderer failed after starting"}))
        self.reject(lambda _, r: r["runs"][-1]["groups"][0]["capture_attempts"][0]["response"].update(
            directory="partial-rendered-evidence"))

    def test_rejects_incomplete_retries_or_unbound_final_failure_response(self):
        self.reject(lambda _, r: r["runs"][-1]["groups"][0]["capture_attempts"].pop())
        self.reject(lambda _, r: r["runs"][-1]["groups"][0]["capture_attempts"][-1].update(retry_exhausted=False))
        self.reject(lambda _, r: r["runs"][-1]["groups"][0].update(capture_response={"ok": False, "error": "different"}))

    def test_rejects_missing_or_duplicate_partial_image_ids(self):
        self.reject(lambda _, r: r["traceable_images"].pop())
        self.reject(lambda _, r: r["traceable_images"].__setitem__(0, deepcopy(r["traceable_images"][1])))


class EvidenceTreeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="unit_pending_", dir=pending.capture.SPRINT / "qa")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_regular_files_are_pinned_deterministically_with_byte_identity(self):
        (self.root / "nested").mkdir()
        (self.root / "root.json").write_bytes(b"test-only copy fixture\n")
        (self.root / "nested" / "labels.txt").write_bytes(b"")
        rows = pending.tree_pins(self.root)
        self.assertEqual(rows, sorted(rows, key=lambda row: row["path"]))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows, [pending.capture.pin(pending.ROOT / row["path"]) for row in rows])
        before = deepcopy(rows)
        (self.root / "root.json").write_bytes(b"changed test-only copy fixture\n")
        self.assertNotEqual(before, pending.tree_pins(self.root))

    def test_symlink_file_and_directory_are_rejected_without_following(self):
        (self.root / "target.txt").write_text("test-only fixture")
        for directory in (False, True):
            link = self.root / ("directory_link" if directory else "file_link")
            link.symlink_to(self.root if directory else self.root / "target.txt", target_is_directory=directory)
            with self.assertRaises(ValueError):
                pending.tree_pins(self.root)
            link.unlink()

    def test_generated_directory_or_bytecode_names_rejected_before_file_access(self):
        for directories, names in ((["__pycache__"], []), ([], ["forbidden.pyc"])):
            with self.subTest(directories=directories, names=names):
                with patch.object(pending.os, "walk", return_value=[(str(self.root), directories, names)]):
                    with patch.object(pending.capture, "pin", side_effect=AssertionError("generated file read")):
                        with self.assertRaises(ValueError):
                            pending.tree_pins(self.root)


class SupplementMetadataTests(unittest.TestCase):
    """Report-shape fixtures use actual declared states; they contain no renders."""
    def setUp(self):
        declaration = json.loads((pending.DEFAULT_SOURCE / "declaration.json").read_text())
        original = json.loads((pending.DEFAULT_SOURCE / "results.json").read_text())
        run = deepcopy(declaration["runs"][-1])
        self.plan = {"declaration": original["declaration"], "pending_groups": [
            {"run_id": run["run_id"], "step_index": state["step_index"], "split": "test", "source_state": state}
            for state in run["selected_states"]]}
        groups = [{**selected, "passed": True, "held_state": True,
                   "encounter_group_id": run["encounter_group_id"],
                   "retained_group": {"unit_test_metadata_only": True},
                   "coexistence_checks": {"unit_test_metadata_only": True}}
                  for selected in deepcopy(self.plan["pending_groups"])]
        images = [{"image_id": f"{run['run_id']}__step_{state['step_index']:03d}__{variant}__gsd_{gsd:g}"}
                  for state in run["selected_states"] for variant in ("present", "absent") for gsd in pending.capture.GSDS]
        self.report = {"kind": "m7_pending_only_capture_attempt", "preflight_only": False,
                       "biological_approval": False, "passed": True, "runtime_code_unchanged": True,
                       "declaration_unchanged": True, "source_campaign_unchanged": True,
                       "pending_plan_unchanged": True, "capture_counts": {"target_present": 15, "target_absent": 15, "groups": 3},
                       "declaration": original["declaration"], "runtime_code_before": original["runtime_code_before"],
                       "runtime_code_after": original["runtime_code_before"],
                       "preservation_before": [{"passed": True}, {"passed": True}],
                       "preservation_after": [{"passed": True}, {"passed": True}],
                       "runs": [{key: run[key] for key in ("run_id", "seed", "split", "encounter_group_id")}],
                       "traceable_images": images}
        self.report["runs"][0].update(passed=True, groups=groups, cleanup_checks={"unit_test_metadata_only": True})

    def reject(self, change):
        report = deepcopy(self.report)
        change(report)
        with self.assertRaises(ValueError):
            aggregate.validate_supplement(report, self.plan)

    def test_exact_pending_workload_report_shape_accepts_same_actual_source_states(self):
        groups = aggregate.validate_supplement(self.report, self.plan)
        self.assertEqual([row["step_index"] for row in groups], [8, 16, 32])
        self.assertEqual([row["source_state"] for row in groups], [row["source_state"] for row in self.plan["pending_groups"]])

    def test_rejects_preflight_success_or_changed_source_or_saved_plan(self):
        for field, value in (("preflight_only", True), ("source_campaign_unchanged", False),
                             ("pending_plan_unchanged", False), ("biological_approval", True)):
            with self.subTest(field=field):
                self.reject(lambda r: r.update({field: value}))
        self.reject(lambda r: r.update(declaration={"sha256": "0" * 64}))

    def test_rejects_missing_duplicate_reordered_or_substituted_supplemental_groups(self):
        self.reject(lambda r: r["runs"][0]["groups"].pop())
        self.reject(lambda r: r["runs"][0]["groups"].__setitem__(2, deepcopy(r["runs"][0]["groups"][1])))
        self.reject(lambda r: r["runs"][0]["groups"].reverse())
        self.reject(lambda r: r["runs"][0]["groups"][0]["source_state"]["agents"][0].update(depth_m=.6))

    def test_rejects_changed_split_cleanup_or_rendered_group_status(self):
        self.reject(lambda r: r["runs"][0].update(split="train"))
        self.reject(lambda r: r["runs"][0].update(cleanup_verification_error="failed"))
        self.reject(lambda r: r["runs"][0]["groups"][0].update(held_state=False))
        self.reject(lambda r: r["runs"][0]["groups"][0].update(passed=False))

    def test_rejects_missing_or_duplicate_image_metadata(self):
        self.reject(lambda r: r["traceable_images"].pop())
        self.reject(lambda r: r["traceable_images"].__setitem__(0, deepcopy(r["traceable_images"][1])))


class PendingPlanTests(unittest.TestCase):
    def test_plan_revalidates_all_twelve_actual_groups_and_pins_the_failed_attempt(self):
        plan = pending.build_pending_plan(pending.DEFAULT_SOURCE)
        self.assertIs(plan["source_campaign_passed"], False)
        self.assertEqual(plan["accepted_source_images"], 120)
        self.assertEqual(plan["pending_images"], 30)
        self.assertEqual(len(plan["accepted_source_groups"]), 12)
        self.assertEqual([(row["run_id"], row["step_index"]) for row in plan["pending_groups"]],
                         [(pending.PENDING_RUN, step) for step in (8, 16, 32)])
        self.assertIs(plan["no_accepted_groups_recaptured"], True)
        self.assertIs(plan["no_source_or_image_substitution"], True)
        self.assertEqual(plan["source_campaign_result"], pending.capture.pin(pending.DEFAULT_SOURCE / "results.json"))
        self.assertEqual(plan["source_tree_pins"], pending.tree_pins(pending.DEFAULT_SOURCE))
        for row in plan["accepted_source_groups"]:
            self.assertEqual(row["group_result"], pending.capture.pin(Path(row["source_step_directory"]) / "group_result.json"))
            self.assertEqual(row["group_manifest"], pending.capture.pin(Path(row["source_group_directory"]) / "manifest.json"))

    def test_changed_current_protocol_pins_refused_before_accepted_groups_are_loaded(self):
        with patch.object(pending.capture, "runtime_code_pins", return_value=[]):
            with patch.object(pending.capture, "validate_group", side_effect=AssertionError("loaded after code mismatch")):
                with self.assertRaisesRegex(ValueError, "protocol code changed"):
                    pending.build_pending_plan(pending.DEFAULT_SOURCE)

    def test_missing_or_divergent_accepted_group_result_refused(self):
        target = pending.DEFAULT_SOURCE / "captures/m5_positive_seed_1_a/step_008/group_result.json"
        original_read = Path.read_text
        actual = json.loads(original_read(target))
        def missing(path, *args, **kwargs):
            if path == target:
                raise FileNotFoundError("test interception: missing accepted result")
            return original_read(path, *args, **kwargs)
        with patch.object(Path, "read_text", missing):
            with self.assertRaises(FileNotFoundError):
                pending.build_pending_plan(pending.DEFAULT_SOURCE)
        actual["held_state"] = False
        def divergent(path, *args, **kwargs):
            return json.dumps(actual) if path == target else original_read(path, *args, **kwargs)
        with patch.object(Path, "read_text", divergent):
            with self.assertRaisesRegex(ValueError, "differs from the original campaign"):
                pending.build_pending_plan(pending.DEFAULT_SOURCE)


class CopyStepTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="unit_pending_copy_", dir=pending.capture.SPRINT / "qa")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source, self.target = self.root / "source", self.root / "new_copy"
        self.source.mkdir()
        (self.source / "group").mkdir()
        (self.source / "group_result.json").write_bytes(b"test-only status fixture\n")
        (self.source / "group" / "labels.txt").write_bytes(b"")
        (self.source / "group" / "rgb_fixture.bin").write_bytes(bytes(range(128)))

    def test_byte_exact_copy_has_complete_explicit_origin_and_target_provenance(self):
        before = pending.tree_pins(self.source)
        rows = aggregate.copy_step(self.source, self.target)
        self.assertEqual(pending.tree_pins(self.source), before)
        self.assertEqual(len(rows), len(before))
        for row in rows:
            source, target = map(Path, (row["source_path"], row["target_path"]))
            self.assertEqual(source.relative_to(self.source), target.relative_to(self.target))
            self.assertEqual(str(source.relative_to(self.source)), row["relative_path"])
            self.assertEqual(source.read_bytes(), target.read_bytes())
            self.assertEqual(row["bytes"], source.stat().st_size)
            self.assertEqual(row["source_sha256"], row["target_sha256"])
            self.assertIs(row["byte_identical"], True)

    def test_existing_destination_is_preserved_and_source_destination_overlap_rejected(self):
        self.target.mkdir()
        retained = self.target / "original_evidence.txt"
        retained.write_text("preserve")
        with self.assertRaises(ValueError):
            aggregate.copy_step(self.source, self.target)
        self.assertEqual(retained.read_text(), "preserve")
        for target in (self.source, self.source / "nested_destination", self.root):
            with self.subTest(target=target):
                with self.assertRaises(ValueError):
                    aggregate.copy_step(self.source, target)

    def test_missing_or_empty_source_refused_before_destination_creation(self):
        empty = self.root / "empty"
        empty.mkdir()
        for source in (self.root / "missing", empty):
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    aggregate.copy_step(source, self.target)
                self.assertFalse(self.target.exists())

    def test_directory_symlinks_or_nested_file_symlinks_are_refused(self):
        source_link = self.root / "source_link"
        source_link.symlink_to(self.source, target_is_directory=True)
        with self.assertRaises(ValueError):
            aggregate.copy_step(source_link, self.target)
        self.target.symlink_to(self.root / "uncreated_destination", target_is_directory=True)
        with self.assertRaises(ValueError):
            aggregate.copy_step(self.source, self.target)
        self.target.unlink()
        (self.source / "nested_link").symlink_to(self.source / "group_result.json")
        with self.assertRaises(ValueError):
            aggregate.copy_step(self.source, self.target)
        self.assertFalse(self.target.exists())

    def test_incorrect_copied_bytes_rejected_and_failed_evidence_retained(self):
        def incorrect(original, copied):
            copied.write_bytes(original.read_bytes() + b"changed")
        with self.assertRaises(ValueError):
            aggregate.copy_step(self.source, self.target, copier=incorrect)
        self.assertTrue(self.target.exists())
        self.assertTrue(any(path.is_file() for path in self.target.rglob("*")))

    def test_source_mutation_during_copy_rejected_without_overwriting_prior_evidence(self):
        before = pending.tree_pins(self.source)
        def mutate(original, copied):
            aggregate.shutil.copyfile(original, copied)
            original.write_bytes(original.read_bytes() + b"changed by unit fixture")
        with self.assertRaises(ValueError):
            aggregate.copy_step(self.source, self.target, copier=mutate)
        self.assertNotEqual(before, pending.tree_pins(self.source))
        self.assertTrue(self.target.exists())

    def test_source_mutation_before_later_file_copy_rejected(self):
        count = 0
        def mutate_later(original, copied):
            nonlocal count
            aggregate.shutil.copyfile(original, copied)
            count += 1
            if count == 1:
                (self.source / "group_result.json").write_text("changed later source file")
        with self.assertRaisesRegex(ValueError, "before its byte copy"):
            aggregate.copy_step(self.source, self.target, copier=mutate_later)
        self.assertEqual(count, 2)
        self.assertFalse((self.target / "group_result.json").exists())

    def test_source_tree_addition_during_copy_rejected_after_byte_copies(self):
        def add_file(original, copied):
            aggregate.shutil.copyfile(original, copied)
            (self.source / "unexpected_new_file.txt").write_text("fixture added during copy")
        with self.assertRaisesRegex(ValueError, "Source tree changed"):
            aggregate.copy_step(self.source, self.target, copier=add_file)
        self.assertTrue(self.target.exists())
        self.assertFalse((self.target / "unexpected_new_file.txt").exists())


if __name__ == "__main__":
    unittest.main()
