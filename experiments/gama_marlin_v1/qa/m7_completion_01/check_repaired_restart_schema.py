"""Bounded retained restart-proof checks; never call the finalization main."""
import ast
import copy
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import finalize_acceptance as finalizer


def run():
    ast.parse((HERE / "finalize_acceptance.py").read_text())
    pins = finalizer.validation.Pins()
    records, exclusions = finalizer.restart_proofs(pins, HERE / "runtime_log_snapshots")
    before, after = pins.finish()
    assert len(records) == len(exclusions) == 3 and sum(len(r["phases"]) for r in records) == 6
    assert before == after
    stop_dir = finalizer.QA / "kit_restart_01"
    stop = json.loads((stop_dir / "stop_launch_execution.json").read_text())
    restore = json.loads((stop_dir / "restore_execution.json").read_text())
    stop_log = (stop_dir / "stop_launch_command.log").read_bytes()
    restore_log = (stop_dir / "restore_command.log").read_bytes()
    cases = []
    def rejected(name, execution, phase, log):
        try:
            finalizer.restart_execution_output(execution, phase, log)
        except ValueError as exc:
            cases.append({"name": name, "passed": True, "rejection": str(exc)})
        else:
            raise AssertionError("Malformed actual-record copy accepted: " + name)
    def changed(name, edit):
        value = copy.deepcopy(stop)
        edit(value)
        rejected(name, value, "stop_launch", stop_log)
    changed("missing_actual_exit_code", lambda value: value["result"].pop("exit_code"))
    changed("actual_failed_exit", lambda value: value["result"].update(exit_code=1))
    changed("boolean_actual_exit_is_not_code_zero", lambda value: value["result"].update(exit_code=False))
    changed("string_actual_exit_rejected", lambda value: value["result"].update(exit_code="0"))
    changed("missing_actual_result", lambda value: value.pop("result"))
    changed("contradictory_top_code", lambda value: value.update(return_code=1))
    changed("boolean_top_code_rejected", lambda value: value.update(return_code=False))
    changed("empty_actual_final_chunk", lambda value: value["result"].update(output=""))
    changed("altered_actual_final_chunk", lambda value: value["result"].update(output=value["result"]["output"] + "changed\n"))
    changed("missing_python_bytecode_guard", lambda value: value["command"].remove("-B"))
    rejected("missing_stop_launch_prefix", copy.deepcopy(stop), "stop_launch", stop["result"]["output"].encode())
    rejected("changed_stop_launch_prefix", copy.deepcopy(stop), "stop_launch", b"Changed prefix\n" + stop["result"]["output"].encode())
    rejected("extra_earlier_stdout", copy.deepcopy(stop), "stop_launch", b"extra\n" + stop_log)
    rejected("restore_whole_log_must_match", copy.deepcopy(restore), "restore", b"extra\n" + restore_log)
    positive = copy.deepcopy(stop)
    positive["return_code"] = 0
    positive_top = finalizer.restart_execution_output(positive, "stop_launch", stop_log)
    assert positive_top["actual_nested_exit_code"] == 0
    result = {"kind": "m7_repaired_finalizer_actual_restart_schema_check", "passed": True,
              "ast_passed": True, "actual_restart_groups": 3, "actual_restart_phases": 6,
              "actual_nested_exit_codes": [phase["actual_tool_output_binding"]["actual_nested_exit_code"] for record in records for phase in record["phases"]],
              "checks_passed": len(cases), "rejection_checks": cases,
              "missing_top_level_code_accepted_only_with_actual_nested_code_zero": True,
              "matching_optional_top_level_zero_accepted": True,
              "actual_restart_records": records, "mutable_original_stream_exclusions": exclusions,
              "input_pins_before": before, "input_pins_after": after, "all_inputs_unchanged": before == after,
              "scope": "Actual nested output is the final yielded chunk. Stop/launch combines the exact frozen helper print prefix with that chunk; this checks the original combined log format and is not a new independent observation of its earlier yield.",
              "finalizer_sha256": finalizer.digest(HERE / "finalize_acceptance.py"),
              "full_finalizer_main_executed": False, "source_or_evidence_mutation_attempted": False,
              "live_calls_made": False, "render_calls_made": 0}
    print(json.dumps(result, sort_keys=True))

if __name__ == "__main__":
    run()
