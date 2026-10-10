"""Recheck retained M7 completion and historical M8 evidence without execution.

Only hashing, JSON/log reading and the frozen M7 check() function are used.
No main function from an old helper is invoked, and no old file is written.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SPRINT = ROOT / "experiments/gama_marlin_v1"
QA = SPRINT / "qa"
CHECKER = QA / "m7_completion_01/check_finalization_seal_retry_02.py"
CHECKER_SHA = "074a551cb6ed76e5be23380c1597ca6b92ad3d1655e2b03f6e311744040d63ed"
M7_SHA = "d2e4f7179b6c6cb1e4de8124f796fa96d56466b919a1f30abe6b39af7dbd0715"
M8_SHA = "16a51dbd84bbe4ca31f0ad26dcbce318722072dd0cb12f6adc2fc872d244adfa"
CATEGORIES = {"bridge": 100, "capture": 145, "existing_camera": 30,
              "existing_marlin_service": 77, "existing_pilot": 8}


def load_checker():
    # Validate this fixed source before loading; -B prevents import cache writes.
    import hashlib
    if hashlib.sha256(CHECKER.read_bytes()).hexdigest() != CHECKER_SHA:
        raise ValueError("Frozen M7 checker source changed")
    spec = importlib.util.spec_from_file_location("frozen_m7_closeout_check", CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_m8(checker, inputs):
    require = checker.require

    def data(path):
        return checker.read(path, inputs)

    def checked(row):
        actual = checker.pin(row["path"])
        require(actual["sha256"] == row["sha256"], "Historical evidence hash changed: " + actual["path"])
        require("bytes" not in row or actual["bytes"] == row["bytes"], "Historical evidence size changed")
        require(actual["path"] not in inputs or inputs[actual["path"]] == actual, "Evidence changed during review")
        inputs[actual["path"]] = actual
        return actual

    manifest = data(QA / "milestone_8_manifest.json")
    manifest_pin = checker.pin(QA / "milestone_8_manifest.json")
    require(manifest_pin["sha256"] == M8_SHA, "Historical M8 seal changed")
    require(manifest.get("passed") is True and manifest.get("milestone") == 8
            and manifest.get("status") == "complete_review_with_blocked_milestone_7"
            and manifest.get("milestone_7_complete") is False
            and manifest.get("sprint_acceptance_complete") is False
            and manifest.get("all_executed_commands_passed") is False
            and manifest.get("biological_approval") is False, "Historical M8 disposition changed")
    sealed = {}
    require(len(manifest["outputs"]) == 119, "M8 output count changed")
    for row in manifest["outputs"]:
        require(set(row) == {"path", "bytes", "sha256"} and isinstance(row["path"], str)
                and not Path(row["path"]).is_absolute() and Path(row["path"]).as_posix() == row["path"]
                and row["path"] not in sealed and type(row["bytes"]) is int and row["bytes"] >= 0
                and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]), "Invalid or duplicate M8 seal row")
        require(checked(row) == row, "M8 sealed output changed")
        sealed[row["path"]] = row

    offline = data(QA / "m8_offline_01/results.json")
    inventory = data(QA / "m8_offline_01/job_inventory.json")
    require(len(offline["results"]) == len(inventory) == 26
            and len({r["name"] for r in offline["results"]}) == 26, "Regression execution inventory changed")
    jobs = {r["name"]: r for r in inventory}
    cases = [r for r in offline["results"] if r["tests"] is not None]
    require(len(cases) == 24 and sum(r["tests"] for r in cases) == 360
            and offline.get("total_unittest_cases") == 360, "Retained test count changed")
    categories = Counter()
    for row in offline["results"]:
        require(data(QA / f"m8_offline_01/{row['name']}.execution.json") == row,
                "Test execution differs from retained aggregate: " + row["name"])
        checked(row["stdout"])
        checked(row["stderr"])
        job = jobs[row["name"]]
        require(row["category"] == job["category"]
                and row["command"] == [job["python"], "-B", *job["args"]], "Actual retained command differs")
        if row["tests"] is not None:
            require(type(row["tests"]) is int and row["tests"] == row["expected_tests"] == job["expected_tests"]
                    and row["passed"] is True and type(row["return_code"]) is int and row["return_code"] == 0
                    and row["skipped"] == 0, "Retained unittest execution failed")
            text = checker.safe(row["stdout"]["path"]).read_text() + checker.safe(row["stderr"]["path"]).read_text()
            matches = re.findall(r"^Ran (\d+) tests? in [^\n]+\n\nOK\s*$", text, flags=re.MULTILINE)
            require(matches == [str(row["tests"])], "Retained unittest log does not attest the count")
            categories[row["category"]] += row["tests"]
    require(dict(categories) == CATEGORIES and offline["passed"] is False
            and offline["source_pins_unchanged"] is True and offline["source_pin_count"] == 283
            and offline["additional_passed_contract_checks"] == 1
            and offline["git_diff_check"]["return_code"] == 0, "Regression disposition changed")
    failed = [r for r in offline["results"] if r["passed"] is not True]
    require(len(failed) == 1 and failed[0]["name"] == "pilot_sealed_package"
            and failed[0]["return_code"] == 1, "Historical packaging failure was promoted")
    metric = next(r for r in offline["results"] if r["name"] == "pilot_metric_contract")
    require(metric["passed"] is True and metric["return_code"] == 0
            and checker.safe(metric["stdout"]["path"]).read_text().strip() == "M7 metric contract passed",
            "Retained metric self-check changed")
    sources = data(QA / "m8_offline_01/source_pins_before.json")
    require(sources == data(QA / "m8_offline_01/source_pins_after.json") and len(sources) == 283,
            "Retained regression source pins changed")
    for row in sources:
        checked(row)
    disposition = data(QA / "m8_offline_01/historical_package_disposition.json")
    require(disposition["original_run_passed"] is False and disposition["original_failed_execution"] == failed[0]
            and disposition["no_package_outputs_written"] is True and disposition["original_evidence_preserved"] is True
            and disposition["expected_schema"] == "1.6.0" and disposition["actual_preserved_final_schema"] == "1.7.0"
            and disposition["rerun_performed"] is False, "Historical packaging disposition changed")

    audit = data(QA / "m8_pilot_audit_02.json")
    execution = data(QA / "m8_pilot_audit_02_execution.json")
    require(audit["passed"] is True and audit["source_and_images_unchanged_after"] is True
            and audit["input_images_decoded_hashed_and_pixel_padding_checked"] == 300
            and len(audit["image_pins"]) == 300 and len(audit["source_pins"]) == 41
            and audit["retained_test_metric_summaries_exact"] == 18
            and audit["annotation_boxes_linked_geometry_coco_assignment"] == 250
            and audit["unknown_visible_and_silhouette_areas"] == 250
            and audit["training_or_inference_performed"] is False and audit["live_calls_made"] is False
            and audit["biological_approval"] is False and execution["passed"] is True
            and execution["return_code"] == 0 and execution["old_outputs_written"] is False,
            "Historical Pilot audit contract changed")
    checked(execution["result"])
    checked(execution["actual_combined_stdout_stderr"])
    require(checked({"path": str(QA / "m8_pilot_audit_check.py"), "sha256": execution["checker_sha256"]})
            and len(audit["cpu_transform_checks"]) == 12
            and all(r["normalized_tensor_equal_at_unit_scale"] is True and r["boxes_unchanged"] is True
                    for r in audit["cpu_transform_checks"]), "Retained transform audit differs")
    for row in audit["source_pins"] + audit["image_pins"] + audit["historical_pilot_source_pins_matched"]:
        checked(row)
    for row in audit["installed_source_wheel_record_checks"]:
        require(row["passed"] is True, "Installed-source RECORD check changed")
        checked(row["source"])
        checked(row["distribution_record"])

    review = data(QA / "m8_final_review_validation.json")
    require(review["kind"] == "m8_final_review_validation" and review["passed"] is True
            and review["regression_unittest_cases_passed"] == 360 and review["regression_categories"] == CATEGORIES
            and review["input_pins_unchanged"] is True and review["pilot_audit_passed"] is True
            and review["live_demo_passed"] is True and review["historical_preservation_passed"] is True
            and review["m7_progress_pins_checked"] == 1355 and review["milestone_7_complete"] is False
            and review["sprint_acceptance_complete"] is False and review["biological_approval"] is False
            and review["all_executed_commands_passed"] is False and review["historical_packaging_command_failed"] is True
            and review["retained_offline_batch_passed"] is False and review["finalizer_live_calls_made"] is False
            and review["new_images_rendered"] == 0 and review["new_ml_training"] is False,
            "Historical M8 final review validity changed")
    recipe = review["disposition_recipe_copy_provenance"]
    retained_recipe = checked(recipe["retained_copy"])
    require(recipe["original"]["path"] == "/tmp/m8_historical_package_disposition.py"
            and recipe["original"]["sha256"] == retained_recipe["sha256"]
            and recipe["original"]["bytes"] == retained_recipe["bytes"], "Retained temporary recipe binding differs")
    for row in review["input_pins_before"]:
        if row["path"] == recipe["original"]["path"]:
            require(row == recipe["original"], "Historical temporary recipe pin differs")
        else:
            checked(row)
    final_execution = data(QA / "m8_final_review_execution.json")
    final_log = checked({"path": str(QA / "m8_final_review_command.log"),
                         "sha256": checker.digest(QA / "m8_final_review_command.log")})
    require(final_execution["return_code"] == 0 and final_execution["milestone_8_review_passed"] is True
            and final_execution["manifest_sha256"] == M8_SHA
            and checker.safe(final_log["path"]).read_text() == final_execution["stdout_stderr"],
            "Historical final review receipt/log differs")
    stdout = json.loads(final_execution["stdout_stderr"])
    require(stdout["manifest_sha256"] == M8_SHA and stdout["regression_tests"] == 360
            and stdout["outputs"] == 119 and stdout["milestone_8_review_passed"] is True,
            "Historical final review stdout differs")
    decision = data(QA / "m8_expansion_decision.json")
    require(decision == manifest["expansion_decision"] and decision["review_completed"] is True
            and decision["ready_for_further_bounded_engineering_tests"] is True
            and decision["ready_for_limited_behaviour_conditioned_study"] is False
            and decision["ready_for_larger_biological_expansion"] is False
            and decision["biological_approval"] is False and decision["blocked_milestone"] == 7
            and decision["missing_images"] == 30, "Historical expansion disposition changed")
    documents = [sealed[str((SPRINT / name).relative_to(ROOT))] for name in
                 ("GAMA_MARLIN_SPRINT_REPORT.md", "M8_READ_ONLY_PILOT_AUDIT.md", "M8_REPRODUCTION.md")]
    require(checked(decision["report"]) == documents[0], "Historical decision report pin differs")
    return {"manifest": manifest_pin, "unique_sealed_outputs_verified": 119,
            "regression_unittest_cases_verified_from_retained_commands_and_logs": 360,
            "regression_categories": dict(categories), "regression_source_pins_current": 283,
            "additional_metric_self_check_preserved": True, "historical_failed_package_status_preserved": True,
            "pilot_audit_images_current": 300, "pilot_audit_source_pins_current": 41,
            "historical_pilot_cpu_transform_checks": 12, "historical_pilot_metric_summaries": 18,
            "historical_pilot_geometry_links": 250, "historical_review_input_pins_verified": len(review["input_pins_before"]),
            "temporary_recipe_input_bound_to_sealed_copy": {"original": recipe["original"], "retained_copy": retained_recipe,
                "temporary_original_opened": False, "new_execution_inferred": False},
            "historical_review_receipt_and_log_current": True, "original_reports_and_reproduction": documents,
            "historical_status_retained": manifest["status"], "historical_sprint_acceptance_complete": False,
            "biological_approval": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "existing_evidence_validation.json")
    args = parser.parse_args()
    checker = load_checker()
    output = checker.safe(args.output)
    checker.require(output.parent == HERE and output.suffix == ".json" and not output.exists(),
                    "Use an exclusive new closeout proof result")
    inputs = {}
    helper = checker.pin(Path(__file__).resolve())
    inputs[helper["path"]] = helper
    checker_pin = checker.pin(CHECKER)
    inputs[checker_pin["path"]] = checker_pin
    result = {"kind": "sprint_closeout_retained_acceptance_proof", "passed": False,
              "started_at_utc": datetime.now(timezone.utc).isoformat(), "command": [sys.executable, "-B", *sys.argv],
              "helper_before": helper, "reused_frozen_checker": checker_pin,
              "live_calls_made": False, "captures_requested": 0, "gama_executions": 0,
              "ml_training_or_inference_performed": False, "regression_tests_rerun": False,
              "old_outputs_written": False, "biological_approval": False,
              "new_closeout_documents_validated": False, "sprint_closeout_seal_issued": False}
    try:
        checker.require(checker.pin(QA / "milestone_7_manifest.json")["sha256"] == M7_SHA, "M7 completion seal changed")
        result["m7_completion"] = checker.check(output, inputs)
        checker.require(result["m7_completion"]["unique_sealed_outputs_verified"] == 4827, "M7 inventory count changed")
        result["historical_m8"] = verify_m8(checker, inputs)
        before = sorted(inputs.values(), key=lambda row: row["path"])
        after = [checker.pin(row["path"]) for row in before]
        checker.require(before == after and checker.pin(Path(__file__).resolve()) == helper,
                        "Proof inputs or helper changed while checking")
        result.update(input_pins_before=before, input_pins_after=after, all_inputs_unchanged=True, passed=True)
    except Exception as failure:
        result["error"] = f"{type(failure).__name__}: {failure}"
        result["observed_input_pins"] = sorted(inputs.values(), key=lambda row: row["path"])
    result["helper_after"] = checker.pin(Path(__file__).resolve())
    result["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    with output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": result["passed"], "m7_outputs": result.get("m7_completion", {}).get("unique_sealed_outputs_verified"),
                      "m8_outputs": result.get("historical_m8", {}).get("unique_sealed_outputs_verified"),
                      "retained_unittest_cases": result.get("historical_m8", {}).get("regression_unittest_cases_verified_from_retained_commands_and_logs"),
                      "inputs_verified": len(result.get("input_pins_before", [])), "result": str(output),
                      "error": result.get("error")}, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
