"""Bounded read-only checks of the repaired validator against retained review metadata."""
import ast
import copy
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import validate_completion as validator


def run():
    source = HERE / "validate_completion.py"
    ast.parse(source.read_text())
    campaign = validator.QA / "m7_capture_set"
    review = validator.QA / "m7_review"
    report = json.loads((campaign / "results.json").read_text())
    provenance = {(row["run_id"], row["step_index"]): row for row in report["group_provenance"]}
    copies = {key: {str(validator.safe(row["source_path"])): row for row in value["copied_files"]}
              for key, value in provenance.items()}
    cases = [
        ("boolean_true_cannot_replace_verification_count", {"independent_scene_verifications_passed": True}),
        ("partial_verification_count_rejected", {"independent_scene_verifications_passed": 14}),
        ("float_verification_count_rejected", {"independent_scene_verifications_passed": 15.0}),
        ("changed_pinned_inputs_rejected", {"all_pinned_review_inputs_unchanged": False}),
        ("invented_legacy_flag_cannot_replace_actual_contract", {"all_pinned_review_inputs_unchanged": None, "all_retained_source_files_unchanged": True}),
        ("generator_cannot_claim_manual_inspection", {"visual_inspection_completed": True}),
        ("biological_approval_rejected", {"biological_approval": True}),
    ]
    rows = []
    all_pins = {}
    for name, changes in cases:
        class ModifiedMetadata(validator.Pins):
            def load(self, path, expected=None):
                value = super().load(path, expected)
                if validator.safe(path) == review / "visual_index.json":
                    value = copy.deepcopy(value)
                    value.update(changes)
                return value
        pins = ModifiedMetadata()
        try:
            validator.validate_review(pins, review, report, provenance, copies)
        except ValueError as exc:
            validator.require(str(exc) == "Final generated review scope changed", "Unexpected rejection: " + str(exc))
            before, after = pins.finish()
            all_pins.update({row["path"]: row for row in before})
            rows.append({"name": name, "passed": True, "actual_metadata_copy_changes": changes,
                         "rejection": str(exc), "retained_input_files": len(before), "original_bytes_unchanged": before == after})
        else:
            raise AssertionError("Invalid actual-metadata copy was accepted: " + name)
    result = {"kind": "m7_repaired_review_schema_rejection_checks", "passed": True,
              "checks_passed": len(rows), "checks": rows, "ast_passed": True,
              "actual_review_used": str(review / "visual_index.json"),
              "validator_sha256": validator.digest(source), "source_mutation_attempted": False,
              "full_acceptance_main_executed": False, "live_calls_made": False, "render_calls_made": 0,
              "scope": "Only deep-copied actual JSON metadata was perturbed; retained sources and artifacts were never edited.",
              "retained_inputs": sorted(all_pins.values(), key=lambda row: row["path"])}
    print(json.dumps(result, sort_keys=True))

if __name__ == "__main__":
    run()
