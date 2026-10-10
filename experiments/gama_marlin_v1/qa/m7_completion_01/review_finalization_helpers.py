"""Independent offline failure checks for new finalization/log helpers.

Only explicit synthetic log fixtures under this new QA directory are written.
The actual finalizer and actual Kit-log snapshot mains are never executed.
"""
import ast
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FIXTURES = HERE / "review_finalization_fixture_01"
OUTPUT = HERE / "review_finalization_helpers_result.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(value)
    return value


def main():
    if FIXTURES.exists() or OUTPUT.exists():
        raise ValueError("Use exclusive new review evidence")
    sources = [Path(__file__), HERE / "snapshot_runtime_logs.py", HERE / "finalize_acceptance.py"]
    before = {str(path): sha(path) for path in sources}
    for path in sources:
        ast.parse(path.read_text(), filename=str(path))
    logs = module("_review_log_snapshots", sources[1])
    finalizer = module("_review_final_acceptance", sources[2])
    FIXTURES.mkdir()
    (FIXTURES / "README.txt").write_text("Synthetic offline fixture logs only. These bytes are not actual Kit logs or capture evidence.\n")
    cases = []

    def check(name, condition):
        cases.append({"name": name, "passed": bool(condition)})

    def rejection(name, operation):
        try:
            operation()
        except (ValueError, FileExistsError) as error:
            cases.append({"name": name, "passed": True, "rejection": str(error)})
        else:
            cases.append({"name": name, "passed": False, "error": "Invalid input was accepted"})

    original = FIXTURES / "input.log"
    original.write_bytes(b"synthetic initial fixed prefix\n")
    copied = FIXTURES / "copy.log"
    snapshot = logs.snapshot(original, copied)
    check("exact_nonempty_initial_prefix_copy", copied.read_bytes() == original.read_bytes()
          and snapshot["copy_exact_initial_prefix"] is True
          and snapshot["original_source_log_sealed_as_immutable"] is False)
    original.write_bytes(original.read_bytes() + b"synthetic later append\n")
    check("later_append_does_not_invalidate_fixed_prefix", logs.prefix_sha(original, snapshot["initial_bytes_read"])
          == snapshot["copy_sha256"] and original.stat().st_size > snapshot["copy_bytes"])
    rejection("existing_copy_is_never_overwritten", lambda: logs.snapshot(original, copied))
    rejection("truncated_fixed_prefix_is_rejected", lambda: logs.prefix_sha(copied, copied.stat().st_size + 1))
    rejection("generated_path_is_rejected_before_io", lambda: logs.safe(HERE / ".cache" / "not_opened.log"))
    rejection("outside_qa_path_is_rejected_before_io", lambda: logs.safe(Path("/tmp/not_opened_runtime_review.log")))

    changing = FIXTURES / "changing.log"
    changing.write_bytes(b"synthetic copy prefix\n")
    corrupted = FIXTURES / "corrupted.log"
    original_reader = logs.prefix_sha
    def changed_prefix(path, count):
        if path == changing:
            changing.write_bytes(b"X" + changing.read_bytes()[1:])
        return original_reader(path, count)
    logs.prefix_sha = changed_prefix
    try:
        rejection("changed_source_prefix_during_copy_is_rejected", lambda: logs.snapshot(changing, corrupted))
    finally:
        logs.prefix_sha = original_reader

    future = datetime(2099, 1, 1, tzinfo=timezone.utc)
    actual_old_live = ROOT / "experiments/gama_marlin_v1/qa/m8_live_demo_01/results.json"
    old_live_sha = sha(actual_old_live)
    rejection("live_check_predating_last_capture_is_rejected",
              lambda: finalizer.final_live(finalizer.validation.Pins(), actual_old_live, [], future))
    check("historical_live_proof_bytes_preserved", sha(actual_old_live) == old_live_sha)
    acceptance = HERE / "synthetic_not_created_acceptance.json"
    command = ["/usr/bin/python3", "-B", str(HERE / "validate_completion.py"),
               "--output", str(HERE / "different_not_created_acceptance.json")]
    rejection("acceptance_command_output_substitution_is_rejected",
              lambda: finalizer.command_args(command, acceptance))
    rejection("timezone_free_timestamp_is_rejected", lambda: finalizer.utc("2026-10-09T00:00:00"))
    after = {str(path): sha(path) for path in sources}
    result = {"kind": "m7_finalization_helpers_independent_offline_review", "passed": all(row["passed"] for row in cases) and before == after,
              "cases": cases, "cases_passed": sum(row["passed"] for row in cases),
              "source_pins_before": before, "source_pins_after": after, "sources_unchanged": before == after,
              "fixture_scope": str(FIXTURES), "synthetic_fixture_logs_only": True,
              "actual_kit_log_snapshot_main_executed": False, "final_report_or_seal_writer_executed": False,
              "live_calls_made": False, "captures_created": 0, "biological_approval": False}
    with OUTPUT.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": result["passed"], "cases_passed": result["cases_passed"], "cases": len(cases), "result": str(OUTPUT)}, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
