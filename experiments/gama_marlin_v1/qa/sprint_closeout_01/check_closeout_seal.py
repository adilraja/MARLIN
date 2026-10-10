"""Independently bind the completed engineering closeout and its late receipt.

This reads retained files only. It invokes no prior main, test or live workflow.
The exclusive check result is outside the closeout inventory to avoid a cycle.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
QA = HERE.parent
MANIFEST = HERE / "closeout_manifest.json"
BLOCKED = {"_build", "extscache", "__pycache__", ".cache"}
FINALIZER_SHA = "162f5c982ac7c311e2574d95b235ad34e2bf6e298db375c22ca5b19e9a5a735c"
RECORDER_SHA = "49a8418f728c067dae1d1648084f81c23775ad0ef8fa12c8a7308c272f279066"
EXPECTED_SEAL_SHA = "acc191ca34fe3c032e0db425120991a4d266bf8d88b8faba8aeddbc9aa524f71"
ANCHORS = {"milestone_7": "d2e4f7179b6c6cb1e4de8124f796fa96d56466b919a1f30abe6b39af7dbd0715",
           "milestone_8": "16a51dbd84bbe4ca31f0ad26dcbce318722072dd0cb12f6adc2fc872d244adfa"}
COUNTS = {"images": 150, "target_present": 75, "target_absent": 75, "camera_condition_pairs": 75, "groups": 15}
SPLITS = {"train": 90, "validation": 30, "test": 30}


def require(value, message):
    if not value:
        raise ValueError(message)


def safe(path):
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    require(path.is_relative_to(ROOT) and ".." not in path.parts
            and not BLOCKED.intersection(path.parts) and path.suffix != ".pyc", "Unsafe evidence path")
    parent = path
    while parent != ROOT:
        require(not parent.is_symlink(), "Evidence symlinks are prohibited")
        parent = parent.parent
    return path.resolve()


def pin(path):
    path = safe(path)
    require(path.is_file(), "Retained file missing")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def read(path, inputs):
    row = pin(path)
    require(row["path"] not in inputs or inputs[row["path"]] == row, "Input changed while reading")
    inputs[row["path"]] = row
    value = json.loads(safe(path).read_text(), object_pairs_hook=unique_object,
                       parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))
    require(pin(path) == row, "JSON input changed while reading")
    return value


def bind(row, inputs):
    require(set(row) == {"path", "bytes", "sha256"} and isinstance(row["path"], str)
            and not Path(row["path"]).is_absolute() and Path(row["path"]).as_posix() == row["path"]
            and type(row["bytes"]) is int and row["bytes"] >= 0
            and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]), "Invalid evidence pin")
    require(pin(row["path"]) == row, "Retained bytes changed: " + row["path"])
    require(row["path"] not in inputs or inputs[row["path"]] == row, "Conflicting input pin")
    inputs[row["path"]] = row
    return row


def check(output, inputs):
    manifest = read(MANIFEST, inputs)
    seal = pin(MANIFEST)
    require(seal["sha256"] == EXPECTED_SEAL_SHA, "Completed closeout seal differs from its actual recorded hash")
    require(manifest["kind"] == "gama_marlin_engineering_sprint_closeout_manifest"
            and manifest["status"] == "complete_engineering_scope" and manifest["passed"] is True
            and manifest["sprint_acceptance_complete"] is True and manifest["acceptance_scope"].strip()
            and manifest["capture_counts"] == COUNTS and manifest["split_image_counts"] == SPLITS,
            "Bounded engineering completion contract differs")
    for key in ("biological_approval", "human_approval_inferred", "all_executed_commands_passed", "new_tests_executed",
                "live_calls_made", "ml_training_or_inference_performed", "historical_records_rewritten"):
        require(manifest[key] is False, "Closeout promoted unsupported scope: " + key)
    require(manifest["captures_requested"] == manifest["new_gama_executions"] == 0
            and manifest["retained_regression_unittest_cases"] == 360
            and manifest["historical_failed_packaging_check_preserved"] is True
            and manifest["all_first_proof_inputs_current_and_unchanged"] is True
            and manifest["all_closeout_inputs_unchanged"] is True
            and manifest["original_milestone_seal_sha256"] == ANCHORS, "Retained acceptance or history differs")
    rows = manifest["outputs"]
    require(len(rows) == manifest["unique_output_paths"] and rows, "Closeout inventory count differs")
    sealed = {}
    for row in rows:
        require(row["path"] not in sealed, "Duplicate closeout inventory path")
        sealed[row["path"]] = bind(row, inputs)
    deferred = [MANIFEST, HERE / "closeout_command.log", HERE / "closeout_execution.json", output,
                HERE / "seal_check_command.log", HERE / "seal_check_execution.json"]
    require(all(str(path.relative_to(ROOT)) not in sealed for path in deferred)
            and manifest["manifest_self_hash_deferred"] is True
            and manifest["completed_finalizer_receipt_requires_later_independent_binding"] is True,
            "Manifest or receipt self-hash cycle")
    execution = read(HERE / "closeout_execution.json", inputs)
    log = bind(execution["log"], inputs)
    require(safe(log["path"]) == HERE / "closeout_command.log"
            and manifest["deferred_finalizer_log"] == log["path"]
            and manifest["deferred_finalizer_execution"] == str((HERE / "closeout_execution.json").relative_to(ROOT)),
            "Another late finalizer receipt/log was selected")
    command = ["/usr/bin/python3", "-B", str(HERE / "finalize_closeout.py")]
    require(execution["kind"] == "sprint_closeout_actual_finalization_execution"
            and execution["command"] == command and execution["cwd"] == str(ROOT)
            and execution["passed"] is True and type(execution["return_code"]) is int and execution["return_code"] == 0
            and execution["manifest"] == seal and execution["source_pins_unchanged"] is True
            and execution["post_seal_receipt"] is True and execution["requires_later_independent_seal_binding"] is True,
            "Completed actual finalization receipt differs")
    for key in ("live_calls_made", "regression_tests_rerun", "ml_training_or_inference_performed", "old_outputs_written"):
        require(execution[key] is False, "Finalizer performed an unsupported workflow")
    require(execution["new_renders"] == execution["new_gama_executions"] == 0, "Finalizer claims new executions")
    for prefix, filename, expected in (("source", "finalize_closeout.py", FINALIZER_SHA),
                                       ("runner", "record_closeout.py", RECORDER_SHA)):
        current = bind(execution[prefix + "_before"], inputs)
        require(current == execution[prefix + "_after"] == pin(HERE / filename)
                and current["sha256"] == expected and sealed.get(current["path"]) == current,
                "Finalizer/recorder before-after/current/sealed source differs")
    stdout = read(HERE / "closeout_command.log", inputs)
    require(stdout == {"passed": True, "manifest": seal, "outputs": len(rows), "capture_counts": COUNTS,
                       "first_proof_inputs_rechecked": 4859, "separate_later_seal_check_required": True},
            "Actual completed finalizer stdout differs")
    times = [datetime.fromisoformat(value) for value in
             (execution["started_at_utc"], manifest["completed_at_utc"], execution["finished_at_utc"])]
    require(all(value.tzinfo is not None for value in times) and times == sorted(times)
            and isinstance(execution["elapsed_seconds"], (int, float)) and not isinstance(execution["elapsed_seconds"], bool)
            and math.isfinite(execution["elapsed_seconds"]) and execution["elapsed_seconds"] >= 0,
            "Actual finalizer timing differs")
    proof = read(HERE / "existing_evidence_validation.json", inputs)
    require(manifest["existing_evidence_validation"] == pin(HERE / "existing_evidence_validation.json")
            and manifest["actual_existing_evidence_execution"] == pin(HERE / "existing_evidence_execution.json")
            and proof["passed"] is True and proof["all_inputs_unchanged"] is True
            and proof["input_pins_before"] == proof["input_pins_after"]
            and len(proof["input_pins_before"]) == len({row["path"] for row in proof["input_pins_before"]})
            == manifest["first_proof_input_count"] == 4859, "First-proof binding differs")
    for row in proof["input_pins_before"]:
        bind(row, inputs)
    require(proof["m7_completion"]["unique_sealed_outputs_verified"] == 4827
            and proof["m7_completion"]["capture_counts"] == COUNTS and proof["m7_completion"]["split_image_counts"] == SPLITS
            and proof["historical_m8"]["unique_sealed_outputs_verified"] == 119
            and proof["historical_m8"]["regression_unittest_cases_verified_from_retained_commands_and_logs"] == 360,
            "Retained proof acceptance differs")
    for name, expected in ANCHORS.items():
        path = QA / (name + "_manifest.json")
        row = pin(path)
        require(row["sha256"] == expected and sealed.get(row["path"]) == row, "Original milestone seal changed")
    status = read(HERE / "current_status.json", inputs)
    require(manifest["current_status"] == pin(HERE / "current_status.json") and status["sprint_acceptance_complete"] is True
            and status["milestone_7_complete"] is True and status["milestone_8_complete"] is True
            and status["status"] == "complete_engineering_scope" and status["acceptance_scope"] == manifest["acceptance_scope"]
            and status["milestones"] == manifest["milestones"] and [row["number"] for row in status["milestones"]] == list(range(1, 9)),
            "Current status differs from the bounded seal")
    for key in ("biological_approval", "human_approval_inferred", "ready_for_limited_behaviour_conditioned_study",
                "ready_for_larger_biological_expansion", "historical_records_rewritten", "all_executed_commands_passed"):
        require(status[key] is False, "Current status promotes unsupported approval")
    require(all(all(row[key] is True for key in ("implemented", "executed", "passed"))
                and row["biological_suitability"] in {"not_approved", "provisional", "provisional_engineering_use_only"}
                for row in status["milestones"]), "Milestone scope exceeds engineering acceptance")
    require(len(manifest["document_link_checks"]) == 2, "Current report/reproduction checks missing")
    for document in manifest["document_link_checks"]:
        require(document["reviewed_claims_match_bounded_status"] is True
                and sealed.get(document["document"]["path"]) == document["document"], "Document source not inventoried")
        require(document["linked_evidence"] and all(path in sealed for path in document["linked_evidence"]),
                "Previously verified document links lost their sealed inputs")
    require(pin(MANIFEST) == seal, "Closeout seal changed during its check")
    return {"manifest": seal, "unique_sealed_outputs_verified": len(sealed), "first_proof_inputs_rechecked": 4859,
            "completed_finalizer_execution": pin(HERE / "closeout_execution.json"), "completed_finalizer_log": log,
            "source_and_recorder_current_and_sealed": True, "manifest_own_sha256_and_late_receipts_verified": True,
            "original_milestone_seal_sha256": ANCHORS, "capture_counts": COUNTS, "split_image_counts": SPLITS,
            "sprint_acceptance_complete": True, "status": "complete_engineering_scope", "biological_approval": False,
            "prior_document_link_validation_preserved": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "seal_validation.json")
    args = parser.parse_args()
    output = safe(args.output)
    require(output.parent == HERE and output.suffix == ".json" and not output.exists(), "Use an exclusive new closeout check result")
    inputs = {}
    helper = pin(Path(__file__).resolve())
    runner = pin(HERE / "record_seal_check.py")
    inputs[helper["path"]], inputs[runner["path"]] = helper, runner
    result = {"kind": "independent_engineering_sprint_closeout_seal_check", "passed": False,
              "started_at_utc": datetime.now(timezone.utc).isoformat(), "command": [sys.executable, "-B", *sys.argv],
              "helper_before": helper, "live_calls_made": False, "old_outputs_written": False,
              "new_renders": 0, "new_gama_executions": 0, "regression_tests_rerun": False,
              "ml_training_or_inference_performed": False, "seal_modified": False, "biological_approval": False}
    try:
        result.update(check(output, inputs))
        before = sorted(inputs.values(), key=lambda row: row["path"])
        after = [pin(row["path"]) for row in before]
        require(before == after, "Closeout check inputs changed")
        result.update(input_pins_before=before, input_pins_after=after, all_inputs_unchanged=True, passed=True)
    except Exception as failure:
        result["error"] = f"{type(failure).__name__}: {failure}"
        result["observed_input_pins"] = sorted(inputs.values(), key=lambda row: row["path"])
    result["helper_after"] = pin(Path(__file__).resolve())
    result["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    with output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": result["passed"], "manifest": result.get("manifest"),
                      "outputs_verified": result.get("unique_sealed_outputs_verified"),
                      "first_proof_inputs_rechecked": result.get("first_proof_inputs_rechecked"),
                      "result": str(output), "error": result.get("error")}, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
