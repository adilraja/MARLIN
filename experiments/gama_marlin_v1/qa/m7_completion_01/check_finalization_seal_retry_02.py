"""Independently verify the second M7 finalization and its retained receipts.

This checker reads retained repository evidence only. It never opens generated
runtime directories, contacts Kit, renders, rewrites the seal or grants biology.
Its own exclusive result is outside the seal inventory, avoiding a self cycle.
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
SPRINT = ROOT / "experiments/gama_marlin_v1"
QA = SPRINT / "qa"
MANIFEST = QA / "milestone_7_manifest.json"
BLOCKED = {"_build", "extscache", "__pycache__", ".cache"}
HISTORICAL_SHAS = {
    SPRINT / "m7_capture_declaration.json": "4955284fe067ce9e69b5d47d8381e6a5f82f3e00e3453d2459858189e431e557",
    QA / "m7_progress_manifest.json": "a480bd2ac0624ab6cc8ff2d6873bb68c355f6a73f9adcb3ad66ec53e242635d9",
    QA / "milestone_8_manifest.json": "16a51dbd84bbe4ca31f0ad26dcbce318722072dd0cb12f6adc2fc872d244adfa",
    QA / "milestone_5_manifest.json": "fdc934b556f006118e8c720a3cbba4302a8a154ae6005da5c4477b0286fc10c3",
    QA / "milestone_6_manifest.json": "97cee0f2401d13b0f5e58473ca0d6278c4c9d17ae9298997aae9622ea17845fd",
}
CAPTURE_SHA = "b634b127dc7f607deb63a749d3cc64727d6b88efcf120f25e83941e968415fd3"
FINALIZER_SHA = "43f0c92d2b06e8f2dfc77a39839fd697ffdad12fc2eed38b4a5dd8c92a67fbeb"
FAILED_FINALIZER_SHA = "a1ca0304fda838b6e3d2f3e607d1384ac333f6300793bfc2c5d68449ed4f68ff"
FAILED_VALIDATOR_SHA = "35ccb30eaa71912e42040d2d5d7d78878c5764c1abf5e2ea71734c53dc6ab0d3"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe(path):
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    require(not BLOCKED.intersection(path.parts) and path.suffix != ".pyc" and ".." not in path.parts,
            "Generated/traversal path prohibited before I/O")
    require(path.is_relative_to(ROOT), "Evidence path leaves the repository")
    parent = path
    while parent != ROOT:
        require(not parent.is_symlink(), "Evidence symlinks are prohibited")
        parent = parent.parent
    resolved = path.resolve()
    require(resolved.is_relative_to(ROOT) and not BLOCKED.intersection(resolved.parts), "Resolved evidence path is prohibited")
    return resolved


def digest(path):
    value = hashlib.sha256()
    with safe(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def pin(path):
    path = safe(path)
    require(path.is_file(), "Retained file missing: " + str(path))
    return {"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": digest(path)}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key: " + key)
        result[key] = value
    return result


def finite(value):
    if isinstance(value, float):
        require(math.isfinite(value), "Nonfinite JSON number")
    elif isinstance(value, dict):
        for item in value.values():
            finite(item)
    elif isinstance(value, list):
        for item in value:
            finite(item)


def read(path, inputs):
    row = pin(path)
    require(row["path"] not in inputs or inputs[row["path"]] == row, "Evidence changed during checking")
    inputs[row["path"]] = row
    value = json.loads(safe(path).read_text(), object_pairs_hook=unique_object)
    finite(value)
    require(pin(path) == row, "JSON evidence changed while reading")
    return value


def utc(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.tzinfo is not None, "Command timestamp has no timezone")
    return parsed.astimezone(timezone.utc)


def expected_command(operation):
    python = ["/usr/bin/python3", "-B"]
    if operation == "acceptance-retry":
        return python + [str(HERE / "validate_completion.py"),
                         "--campaign", str(QA / "m7_capture_set"),
                         "--scene-verifications", str(QA / "m7_scene_validation_set"),
                         "--review", str(QA / "m7_review"),
                         "--dataset", str(SPRINT / "datasets/m7_engineering_v1"),
                         "--execution-record", str(HERE / "aggregate_execution.json"),
                         "--execution-record", str(HERE / "export_execution.json"),
                         "--preservation", str(HERE / "original_preservation.json"),
                         "--history-preservation", str(HERE / "historical_progress_preservation.json"),
                         "--output", str(HERE / "acceptance_retry_02.json")]
    if operation == "snapshots":
        return python + [str(HERE / "snapshot_runtime_logs.py"), "--output", str(HERE / "runtime_log_snapshots")]
    require(operation == "finalize", "Unsupported receipt operation")
    return python + [str(HERE / "finalize_acceptance.py"),
                     "--acceptance", str(HERE / "acceptance_retry_02.json"),
                     "--final-live-check", str(HERE / "final_live_demo/results.json"),
                     "--runtime-log-snapshots", str(HERE / "runtime_log_snapshots"),
                     "--execution-record", str(HERE / "acceptance_retry_02_execution.json"),
                     "--execution-record", str(HERE / "final_live_execution_binding.json"),
                     "--active-log", str(HERE / "finalize_retry_02_command.log")]


def verify_live_binding(sealed, inputs):
    """Bind the schema adapter to its original actual command and tool report."""
    raw_path = HERE / "final_live_execution.json"
    binding_path = HERE / "final_live_execution_binding.json"
    result_path = HERE / "final_live_demo/results.json"
    raw, binding, report = (read(path, inputs) for path in (raw_path, binding_path, result_path))
    for path in (raw_path, binding_path, result_path):
        row = pin(path)
        require(sealed.get(row["path"]) == row, "Actual live proof/adapter was not preserved in the seal")
    require(raw.get("kind") == "m7_actual_final_read_only_live_command_execution"
            and raw.get("passed") is True and type(raw.get("return_code")) is int and raw["return_code"] == 0
            and raw.get("stdout_stderr_retained_exactly") is True
            and raw.get("outer_source_before_after_independently_measured") is False,
            "Original actual live command scope/status was changed")
    require(binding.get("kind") == "m7_final_live_execution_schema_binding"
            and binding.get("schema_binding_only") is True and binding.get("new_command_executed") is False
            and safe(binding["original_execution"]) == raw_path and safe(binding["actual_result"]) == result_path,
            "Live schema adapter implies a new execution or another original proof")
    for key in ("command", "cwd", "return_code", "passed", "log", "log_sha256", "tool_report_started_at_utc",
                "tool_report_finished_at_utc", "live_calls_made", "new_renders_requested", "scene_mutation_attempted", "kit_restart_requested"):
        require(binding.get(key) == raw.get(key), "Live adapter differs from actual original field " + key)
    command = raw["command"]
    require(command == ["/usr/bin/python3", "-B", "tools/verify_gama_m8_demo.py", "--output",
                        "experiments/gama_marlin_v1/qa/m7_completion_01/final_live_demo"], "Original live command differs")
    require(report.get("kind") == "m8_read_only_live_demo_check" and report.get("passed") is True
            and report["started_at_utc"] == raw["tool_report_started_at_utc"]
            and report["finished_at_utc"] == raw["tool_report_finished_at_utc"]
            and report["source_pins_before"] == raw["source_pins_before"]
            and report["source_pins_after"] == raw["source_pins_after"]
            and len(report["checks"]) == 14 and all(value is True for value in report["checks"].values())
            and len(report["route_presence_checks"]) == 4 and all(value is True for value in report["route_presence_checks"].values()),
            "Raw live execution was not bound to the actual passed fourteen-check tool report")
    expected_paths = {"tools/verify_gama_m8_demo.py", "tools/verify_gama_paired_live.py", "tools/gama_porpoise.py",
                      "source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge/marine_check.py"}
    for phase in ("source_pins_before", "source_pins_after"):
        rows = raw[phase]
        require(len(rows) == 4 and len({row["path"] for row in rows}) == 4
                and all(set(row) == {"path", "sha256"} for row in rows), "Raw live pins gained unmeasured fields")
        hashes = {row["path"]: row["sha256"] for row in rows}
        require(set(hashes) == expected_paths and binding[phase] == hashes, "Live schema adapter did not preserve exact SHA-only evidence")
        for path, expected in hashes.items():
            row = pin(ROOT / path)
            require(row["sha256"] == expected and sealed.get(row["path"]) == row, "Actual live source SHA differs from sealed bytes")
    require(raw["source_pins_before"] == raw["source_pins_after"], "Actual live source pins changed")
    log = pin(safe(raw["log"]))
    require(log["sha256"] == raw["log_sha256"] and sealed.get(log["path"]) == log, "Original live stdout/stderr bytes differ")
    inputs[log["path"]] = log
    return {"original_actual_execution": pin(raw_path), "schema_binding": pin(binding_path),
            "actual_tool_report": pin(result_path), "actual_stdout_stderr": log,
            "schema_binding_only": True, "new_command_executed": False,
            "original_sha_only_evidence_preserved_without_invented_measurements": True}


def verify_receipt(operation, sealed, inputs, seal_pin, report_pin):
    prefix = "acceptance_retry_02" if operation == "acceptance-retry" else ("finalize_retry_02" if operation == "finalize" else operation)
    path = HERE / (prefix + "_execution.json")
    record = read(path, inputs)
    command = expected_command(operation)
    require(record.get("kind") == "m7_actual_finalization_command_execution" and record.get("operation") == operation
            and record.get("passed") is True and type(record.get("return_code")) is int and record["return_code"] == 0
            and record.get("command") == command and record.get("cwd") == str(ROOT)
            and record.get("live_calls_made") is False and record.get("new_renders_requested") == 0
            and record.get("terminated_by_timeout") is False and not record.get("error"), "Actual finalization receipt failed or differs")
    runner = record.get("runner_command", [])
    recorder_path = HERE / ("record_finalization_retry_02.py" if operation == "finalize" else "record_finalization_command.py")
    if operation == "finalize":
        require(len(runner) == 3 and runner[1] == "-B" and safe(runner[2]) == recorder_path
                and record.get("retry_index") == 2 and record.get("original_receipts_rewritten") is False,
                "Actual finalization retry recorder command differs")
    else:
        require(len(runner) == 4 and runner[1] == "-B" and safe(runner[2]) == recorder_path
                and runner[3] == operation, "Actual original command recorder differs")
    program, recorder = pin(command[2]), pin(recorder_path)
    require(program == sealed[program["path"]] and recorder == sealed[recorder["path"]], "Actual command program/recorder differs from sealed bytes")
    require(record.get("source_sha256_before") == record.get("source_sha256_after") == program["sha256"]
            and record.get("runner_sha256_before") == record.get("runner_sha256_after") == recorder["sha256"], "Actual source/runner before-after pins differ")
    log = HERE / (prefix + "_command.log")
    row = pin(log)
    require(safe(record["log"]) == log and record.get("log_sha256") == row["sha256"]
            and record.get("log_bytes") == row["bytes"] and row["bytes"] > 0
            and record.get("actual_stdout_stderr_retained_as_binary") is True, "Actual combined stdout/stderr log binding failed")
    inputs[row["path"]] = row
    output = json.loads(log.read_text(), object_pairs_hook=unique_object)
    finite(output)
    require(output.get("passed") is True, "Program stdout did not report actual success")
    started, finished = utc(record["started_at_utc"]), utc(record["finished_at_utc"])
    require(started <= finished and math.isfinite(record["elapsed_seconds"]) and record["elapsed_seconds"] >= 0,
            "Actual command timing differs")
    if operation == "finalize":
        require(record.get("post_seal_finalizer_receipt") is True
                and record.get("finalizer_receipts_require_later_independent_seal_binding") is True,
                "Finalizer receipt did not retain its post-seal scope")
        require(path.relative_to(ROOT).as_posix() not in sealed and row["path"] not in sealed,
                "Post-seal finalizer receipts created a seal self cycle")
        require(output.get("manifest") == seal_pin and output.get("report") == report_pin
                and output.get("capture_counts") == {"images": 150, "target_present": 75, "target_absent": 75, "camera_condition_pairs": 75, "groups": 15}
                and output.get("unique_output_paths") == len(sealed)
                and output.get("separate_later_seal_check_still_required") is True
                and output.get("biological_approval") is False, "Finalizer stdout does not bind this actual seal/report")
    elif operation == "snapshots":
        require(pin(path) == sealed[str(path.relative_to(ROOT))] and row == sealed[row["path"]], "Snapshot receipt/log differs from sealed evidence")
        require(output.get("snapshots") == 3 and safe(output["output"]) == HERE / "runtime_log_snapshots", "Snapshot stdout names another log set")
    else:
        require(operation == "acceptance-retry" and pin(path) == sealed[str(path.relative_to(ROOT))]
                and row == sealed[row["path"]] and safe(output["output"]) == HERE / "acceptance_retry_02.json"
                and output.get("capture_counts") == {"images": 150, "target_present": 75, "target_absent": 75, "camera_condition_pairs": 75, "groups": 15},
                "Actual acceptance retry receipt/log/output differs")
    return {"execution": pin(path), "log": row, "command": command,
            "program": program, "runner": recorder, "started_at_utc": record["started_at_utc"], "finished_at_utc": record["finished_at_utc"]}


def check(output, inputs):
    manifest = read(MANIFEST, inputs)
    seal_pin = pin(MANIFEST)
    require(manifest.get("kind") == "m7_engineering_completion_manifest" and manifest.get("milestone") == 7
            and manifest.get("status") == "complete" and manifest.get("passed") is True and manifest.get("milestone_complete") is True,
            "Require the completed bounded M7 engineering seal")
    require(manifest.get("capture_counts") == {"images": 150, "target_present": 75, "target_absent": 75, "camera_condition_pairs": 75, "groups": 15}
            and manifest.get("split_image_counts") == {"train": 90, "validation": 30, "test": 30}
            and manifest.get("actual_gama_trajectories") == 5 and manifest.get("snapshot_steps") == [8, 16, 32]
            and manifest.get("seeds") == [1, 42, 184729, 20261008, 2147483647]
            and manifest.get("gsd_conditions_cm_px") == [.5, 1, 2, 3, 4] and manifest.get("resolution_px") == [1024, 768], "Declared capture/split contract differs")
    for key in ("biological_approval", "human_approval_inferred", "detector_training_or_inference_run", "automatic_biological_expansion_approval",
                "sprint_acceptance_complete", "uninterrupted_successful_capture_claimed", "all_executed_commands_passed",
                "accepted_groups_recaptured_or_substituted", "background_rgb_equivalence_claimed", "restart_proved_permanent_gpu_memory_fix", "controller_animation_phase_preserved"):
        require(manifest.get(key) is False, "Seal promoted unsupported scope: " + key)
    require(manifest.get("annotation_semantics") == "amodal_direct_evaluated_mesh_projection"
            and manifest.get("rendered_visibility") == "unknown" and manifest.get("pose_mapping") == "static_pose_proxy_v1"
            and manifest.get("failed_attempts_preserved") is True and manifest.get("all_input_pins_current_and_unchanged") is True
            and manifest.get("source_attempt_statuses") == [False, False, True, True], "Acceptance/provenance semantics differ")
    require([row["passed"] for row in manifest["source_attempts"]] == [False, False, True, True]
            and manifest["excluded_earlier_failed_attempt"]["passed"] is False
            and manifest["excluded_earlier_failed_attempt"]["images"] == 20
            and manifest["excluded_earlier_failed_attempt"]["groups"] == 2
            and manifest["excluded_earlier_failed_attempt"]["selected_for_accepted_set"] is False, "Failed attempt history was changed")
    rows = manifest["outputs"]
    require(isinstance(rows, list) and rows and len(rows) == manifest["unique_output_paths"], "Seal inventory count differs")
    sealed = {}
    for row in rows:
        require(set(row) == {"path", "bytes", "sha256"} and isinstance(row["path"], str)
                and not Path(row["path"]).is_absolute() and Path(row["path"]).as_posix() == row["path"]
                and type(row["bytes"]) is int and row["bytes"] >= 0 and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]), "Invalid sealed file row")
        require(row["path"] not in sealed, "Duplicate sealed output path")
        actual = pin(ROOT / row["path"])
        require(actual == row, "Sealed file bytes changed: " + row["path"])
        sealed[row["path"]] = row
        inputs[row["path"]] = row
    require(str(MANIFEST.relative_to(ROOT)) not in sealed and str(output.relative_to(ROOT)) not in sealed
            and manifest.get("seal_self_hash_deferred") is True, "Manifest/check result self-hash cycle")
    for path, expected in HISTORICAL_SHAS.items():
        row = pin(path)
        require(row["sha256"] == expected and sealed.get(row["path"]) == row, "Historical declaration/seal hash changed")
    for name, expected in (("capture_one_pending_snapshot.py", CAPTURE_SHA), ("finalize_acceptance.py", FINALIZER_SHA)):
        row = pin(HERE / name)
        require(row["sha256"] == expected and sealed.get(row["path"]) == row, "Frozen capture/finalizer helper changed")
    require(manifest["frozen_single_state_client"] == pin(HERE / "capture_one_pending_snapshot.py")
            and manifest.get("capture_protocol_pins_per_isolated_attempt") == 32, "Frozen continuation capture pins differ")
    require(manifest.get("historical_m8_status_retained") == "complete_review_with_blocked_milestone_7"
            and manifest["historical_preservation"]["sealed_incomplete_m7_outputs"] == 1355
            and manifest["historical_preservation"]["sealed_m8_outputs"] == 119
            and manifest["historical_preservation"]["historical_records_unchanged"] is True, "Historical disposition was promoted")
    for exclusion in manifest["mutable_runtime_stream_exclusions"]:
        require(exclusion["path"] not in sealed, "Mutable original Kit stream was sealed as immutable")
    require(len(manifest["mutable_runtime_stream_exclusions"]) == 3, "Incomplete mutable stream exclusions")
    report_pin = pin(SPRINT / "M7_COMPLETION_REPORT.md")
    require(manifest["report"] == report_pin and sealed[report_pin["path"]] == report_pin, "Completion report pin differs")
    for path in (HERE / "record_finalization_command.py", HERE / "record_finalization_retry_02.py", Path(__file__).resolve()):
        row = pin(path)
        require(sealed.get(row["path"]) == row, "Final command recorder/checker source was not sealed")
    snapshots = verify_receipt("snapshots", sealed, inputs, seal_pin, report_pin)
    finalized = verify_receipt("finalize", sealed, inputs, seal_pin, report_pin)
    acceptance_retry = verify_receipt("acceptance-retry", sealed, inputs, seal_pin, report_pin)
    acceptance_pin = pin(HERE / "acceptance_retry_02.json")
    require(manifest["acceptance_result"] == acceptance_pin and sealed[acceptance_pin["path"]] == acceptance_pin,
            "Final seal accepted another validation result")
    failed_acceptance = read(HERE / "acceptance.json", inputs)
    failed_execution = read(HERE / "acceptance_execution.json", inputs)
    failed_source = pin(HERE / "validate_completion_failed_v1.py")
    require(failed_acceptance.get("passed") is False and failed_execution.get("passed") is False
            and failed_execution.get("return_code") == 1
            and failed_execution.get("source_sha256_before") == failed_execution.get("source_sha256_after") == failed_source["sha256"] == FAILED_VALIDATOR_SHA
            and sealed.get(failed_source["path"]) == failed_source, "Original failed validator/acceptance status or exact source bytes changed")
    failed_finalizer = read(HERE / "finalize_execution.json", inputs)
    failed_finalizer_source = pin(HERE / "finalize_acceptance_failed_v1.py")
    failed_finalizer_log = pin(HERE / "finalize_command.log")
    old_command = expected_command("finalize")
    old_command[-1] = str(HERE / "finalize_command.log")
    original_recorder = pin(HERE / "record_finalization_command.py")
    require(failed_finalizer.get("passed") is False and failed_finalizer.get("return_code") == 1
            and failed_finalizer.get("command") == old_command
            and failed_finalizer.get("source_sha256_before") == failed_finalizer.get("source_sha256_after")
                == failed_finalizer_source["sha256"] == FAILED_FINALIZER_SHA
            and failed_finalizer.get("runner_sha256_before") == failed_finalizer.get("runner_sha256_after") == original_recorder["sha256"]
            and safe(failed_finalizer["log"]) == HERE / "finalize_command.log"
            and failed_finalizer.get("log_sha256") == failed_finalizer_log["sha256"]
            and failed_finalizer.get("log_bytes") == failed_finalizer_log["bytes"]
            and sealed.get(failed_finalizer_source["path"]) == failed_finalizer_source
            and sealed.get(failed_finalizer_log["path"]) == failed_finalizer_log,
            "Original failed finalization receipt/log/exact source history changed")
    inputs[failed_finalizer_log["path"]] = failed_finalizer_log
    live_binding = verify_live_binding(sealed, inputs)
    require(utc(finalized["started_at_utc"]) <= utc(manifest["completed_at_utc"]) <= utc(finalized["finished_at_utc"]), "Seal time is outside actual finalization execution")
    require(manifest["deferred_finalizer_stdout_log"] == finalized["log"]["path"], "Deferred stdout names another finalizer log")
    require(pin(MANIFEST) == seal_pin, "Seal bytes changed during checking")
    return {"manifest": seal_pin, "report": report_pin, "unique_sealed_outputs_verified": len(sealed),
            "capture_counts": manifest["capture_counts"], "split_image_counts": manifest["split_image_counts"],
            "historical_hashes_verified": {str(path.relative_to(ROOT)): value for path, value in HISTORICAL_SHAS.items()},
            "snapshot_execution": snapshots, "post_seal_finalizer_execution": finalized,
            "successful_acceptance_retry_execution": acceptance_retry,
            "original_failed_acceptance_and_exact_validator_preserved": True,
            "original_failed_finalization_and_exact_sealer_preserved": True,
            "final_live_actual_execution_and_schema_binding": live_binding,
            "manifest_own_sha256_and_completed_finalizer_receipts_verified": True,
            "all_original_mutable_runtime_streams_excluded": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "seal_check_retry_02.json")
    args = parser.parse_args()
    output = safe(args.output)
    require(output.parent == HERE and output.suffix == ".json" and not output.exists(), "Use an exclusive new completion01 result")
    inputs = {}
    helper = pin(Path(__file__).resolve())
    result = {"kind": "m7_independent_completion_seal_and_receipt_check", "passed": False,
              "started_at_utc": datetime.now(timezone.utc).isoformat(), "command": [sys.executable, "-B", *sys.argv],
              "helper_before": helper, "live_calls_made": False, "captures_requested": 0,
              "seal_modified": False, "runtime_generated_bytes_opened": False, "biological_approval": False}
    try:
        result.update(check(output, inputs))
        before = sorted(inputs.values(), key=lambda row: row["path"])
        after = [pin(ROOT / row["path"]) for row in before]
        require(before == after and pin(Path(__file__).resolve()) == helper, "Evidence/helper bytes changed during seal check")
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
                      "unique_sealed_outputs_verified": result.get("unique_sealed_outputs_verified"),
                      "result": str(output), "error": result.get("error")}, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
