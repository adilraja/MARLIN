"""Read-only function-level check of the corrected M7 review validator."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
QA = HERE.parent
VALIDATOR = HERE / "validate_completion.py"
EXPECTED_SHA = "c033ec1599ab69a6d170c8ef63614ff93a49878c935f2863d05484a3dc0a766e"
RESULT = HERE / "review_schema_check_result.json"
LOG = HERE / "review_schema_check.log"
EXECUTION = HERE / "review_schema_check_execution.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def check():
    if sha(VALIDATOR) != EXPECTED_SHA:
        raise ValueError("Corrected validator source does not match its approved audit pin")
    specification = importlib.util.spec_from_file_location("_bounded_review_schema_audit", VALIDATOR)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    pins = module.Pins()
    pins.add(VALIDATOR, EXPECTED_SHA)
    pins.add(Path(__file__).resolve())
    report = pins.load(QA / "m7_capture_set/results.json")
    if report.get("passed") is not True:
        raise ValueError("Require the actual accepted aggregate")
    provenance = {(row["run_id"], row["step_index"]): row for row in report["group_provenance"]}
    if len(provenance) != len(report["group_provenance"]) or len(provenance) != 15:
        raise ValueError("Require fifteen unique source-copy provenance groups")
    copies = {key: {str(module.safe(row["source_path"])): row for row in group["copied_files"]}
              for key, group in provenance.items()}
    if any(len(copies[key]) != len(group["copied_files"]) for key, group in provenance.items()):
        raise ValueError("Duplicate source copy paths")
    result = module.validate_review(pins, QA / "m7_review", report, provenance, copies)
    before, after = pins.finish()
    receipt = {"kind": "m7_corrected_review_validator_actual_schema_check", "passed": True,
               "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
               "target_function": "validate_completion.validate_review",
               "validator_sha256": EXPECTED_SHA,
               "actual_aggregate": str(QA / "m7_capture_set"),
               "actual_review": str(QA / "m7_review"), "review_checks": result,
               "input_pins_before": before, "input_pins_after": after,
               "all_inputs_unchanged": before == after,
               "input_count": len(before), "full_acceptance_main_executed": False,
               "live_calls_made": False, "renders_requested": 0,
               "captured_evidence_mutated": False, "validator_source_edited": False,
               "biological_approval": False, "rendered_visibility": "unknown"}
    write(RESULT, receipt)
    print(json.dumps({"passed": True, "result": str(RESULT),
                      "validator_sha256": EXPECTED_SHA, "input_count": len(before),
                      "review_checks": result, "all_inputs_unchanged": before == after}, indent=2))


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--check":
        check()
        return
    if len(sys.argv) != 1:
        raise ValueError("Only the fixed bounded review schema audit is supported")
    if any(path.exists() for path in (RESULT, LOG, EXECUTION)):
        raise ValueError("Existing targeted review audit evidence cannot be overwritten")
    command = ["/usr/bin/python3", "-B", str(Path(__file__).resolve()), "--check"]
    source_before = {str(path): sha(path) for path in (VALIDATOR, Path(__file__).resolve())}
    started, clock = datetime.now(timezone.utc).isoformat(), time.monotonic()
    with LOG.open("xb") as stream:
        completed = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                   timeout=120, check=False)
    source_after = {str(path): sha(path) for path in (VALIDATOR, Path(__file__).resolve())}
    receipt = {"kind": "m7_corrected_review_validator_function_execution", "command": command,
               "cwd": str(ROOT), "return_code": completed.returncode,
               "started_at_utc": started, "finished_at_utc": datetime.now(timezone.utc).isoformat(),
               "duration_seconds": time.monotonic() - clock,
               "source_pins_before": source_before, "source_pins_after": source_after,
               "sources_unchanged": source_before == source_after,
               "log": str(LOG), "log_sha256": sha(LOG),
               "result": str(RESULT), "result_sha256": sha(RESULT) if RESULT.is_file() else None,
               "full_acceptance_main_executed": False, "live_calls_made": False,
               "passed": completed.returncode == 0 and source_before == source_after}
    write(EXECUTION, receipt)
    print(LOG.read_text())
    if not receipt["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
