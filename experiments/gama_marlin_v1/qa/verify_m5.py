"""Reparse actual M5 exports, compare fresh runs and retain separate review outcomes."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
QA = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
import gama_porpoise as recorder
import run_gama_porpoise_m5 as campaign
import analyze_gama_porpoise as analyzer
from run_m4_checks import verify_rows, INTENTIONAL_SOURCE_DELTAS


def read(path):
    return json.loads(path.read_text())


def main():
    output = QA / "m5_analysis.json"
    if output.exists():
        raise ValueError("Preserve existing M5 analysis evidence")
    plan_path = ROOT / "experiments/gama_marlin_v1/m5_positive_execution_plan.json"
    execution_path = QA / "m5_positive_execution.json"
    plan, execution = read(plan_path), read(execution_path)
    campaign.verify_current_pins(plan)
    assert execution["passed"] and execution["plan_sha256"] == recorder.sha(plan_path)
    assert len(execution["runs"]) == len(plan["runs"]) == 13
    config = read(recorder.CONFIG)
    runs, primary, by_seed, workspaces, pids = [], [], {}, set(), set()
    for declared, invoked in zip(plan["runs"], execution["runs"]):
        assert all(invoked[k] == declared[k] for k in ("run_id", "seed", "repeat"))
        directory = ROOT / "experiments/gama_marlin_v1/trajectories" / declared["run_id"]
        assert invoked["directory"] == str(directory.relative_to(ROOT))
        record = read(directory / "execution.json")
        assert recorder.sha(directory / "execution.json") == invoked["execution_sha256"]
        assert recorder.sha(ROOT / invoked["recorder_log"]) == invoked["recorder_log_sha256"]
        assert invoked["return_code"] == record["return_code"] == 0 and record["status"] == "passed"
        assert record["requested_seed"] == record["actual_seed"] == declared["seed"]
        assert all(record[k] == plan["pins"][k] for k in campaign.PIN_FIELDS)
        assert not record["marlin_http_used"] and not record["scene_actor_acquired"]
        assert recorder.sha(directory / "model.gaml") == plan["pins"]["model_sha256"]
        assert read(directory / "configuration.json") == {"configuration": config, "run_id": declared["run_id"], "requested_seed": declared["seed"]}
        assert recorder.sha(directory / "experiment.xml") == record["experiment_plan_sha256"]
        assert recorder.sha(directory / "raw/simulation-outputs0.xml") == record["raw_xml_sha256"]
        states, validation = recorder.read_trajectory(directory / "raw/simulation-outputs0.xml", config, declared["run_id"], declared["seed"])
        assert states == read(directory / "trajectory.json") and validation == read(directory / "validation.json")
        assert recorder.sha(directory / "trajectory.json") == record["trajectory_sha256"]
        encoded = recorder.canonical_states(states)
        assert hashlib.sha256(encoded).hexdigest() == record["canonical_state_sha256"]
        assert record["canonical_comparison_excluded_fields"] == ["run_id"]
        measurement = analyzer.metrics(states, config)
        assert measurement["passed"] and not measurement["biological_approval"]
        assert measurement["tolerances"]["turn_rate_deg_per_s"] == plan["metric_tolerances"]["turn_rate_deg_per_s"]
        command = record["command"]
        assert command[:4] == ["/usr/sbin/gama-headless", "-m", "1024m", "-ws"]
        workspace = command[4]
        assert workspace == str(ROOT / "artifacts/gama_marlin_v1/workspaces" / declared["run_id"])
        assert workspace not in workspaces and invoked["recorder_process_id"] not in pids
        workspaces.add(workspace)
        pids.add(invoked["recorder_process_id"])
        data = {"states": states, "validation": validation, "canonical": encoded,
                "run_id": declared["run_id"], "record": record, "invocation": invoked}
        by_seed.setdefault(declared["seed"], []).append(data)
        if not declared["repeat"]:
            primary.append(data)
        runs.append({**declared, "directory": str(directory.relative_to(ROOT)), "samples": len(states),
                     "initial_phase_deg": validation["initial_phase_deg"], "canonical_sha256": record["canonical_state_sha256"],
                     "recorder_process_id": invoked["recorder_process_id"], "metrics": measurement})
    assert len(primary) == 10 and set(by_seed) == set(plan["seeds"])
    repeats = []
    for seed in plan["repeat_seeds"]:
        left, right = by_seed[seed]
        assert left["canonical"] == right["canonical"]
        repeats.append({"seed": seed, "runs": [left["run_id"], right["run_id"]],
                        "canonical_bytes_equal": True,
                        "canonical_sha256": hashlib.sha256(left["canonical"]).hexdigest(),
                        "distinct_recorder_processes": left["invocation"]["recorder_process_id"] != right["invocation"]["recorder_process_id"]})
    variation = analyzer.compare_seed_variation(primary, config)
    assert variation["passed"]
    original = ROOT / "experiments/gama_marlin_v1/trajectories/m3_seed_184729_a/trajectory.json"
    representative = by_seed[184729][0]
    assert representative["canonical"] == recorder.canonical_states(read(original))
    m4_path = QA / "m4_live_03/results.json"
    m4 = read(m4_path)
    assert m4["passed"] and m4["trajectory_sha256"] == recorder.sha(original)
    for capture in m4["captures"]:
        index = capture["gama_state"]["step_index"]
        assert recorder.canonical_states([capture["gama_state"]]) == recorder.canonical_states([representative["states"][index]])
        assert capture["render_product_camera_verified"]
    zero_directory = ROOT / "experiments/gama_marlin_v1/trajectories/m5_retry_seed_0_a"
    zero = read(zero_directory / "execution.json")
    zero_raw = ET.parse(zero_directory / "raw/simulation-outputs0.xml").getroot()
    actual_zero = float(next(v.text for v in zero_raw.find("Step").findall("Variable") if v.attrib["name"] == "actual_seed"))
    assert zero["status"] == "failed" and zero["return_code"] == 0 and zero["requested_seed"] == 0 and actual_zero != 0
    assert "Actual exported GAMA seed differs" in zero["error"] and not (zero_directory / "trajectory.json").exists()
    baseline = read(QA / "preserved_output_manifest.json")
    protected = verify_rows(baseline["files"], INTENTIONAL_SOURCE_DELTAS)
    assert protected["passed"]
    checkpoint = baseline["checkpoint"]
    preservation = {"baseline": protected,
                    "checkpoint_copies": verify_rows([{"path": checkpoint[k], "bytes": checkpoint["bytes"], "sha256": checkpoint["sha256"]} for k in ("original", "backup")]),
                    "archive": verify_rows([baseline["archive"]]),
                    "m3_seal": verify_rows(read(QA / "milestone_3_manifest.json")["outputs"]),
                    "m4_seal": verify_rows(read(QA / "milestone_4_manifest.json")["outputs"])}
    assert all(value["passed"] for value in preservation.values())
    tests = []
    for name in ("test_gama_porpoise_analysis", "test_gama_porpoise"):
        command = [sys.executable, "-B", f"tools/{name}.py", "-v"]
        result = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, timeout=60, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        log = QA / ("m5_" + name + ".log")
        with log.open("x") as stream:
            stream.write(result.stdout)
        assert result.returncode == 0, result.stdout
        count = int(re.search(r"Ran (\d+) tests", result.stdout)[1])
        tests.append({"command": command, "count": count, "passed": True, "log": str(log.relative_to(ROOT)), "log_sha256": recorder.sha(log)})
    paths = [Path(__file__), ROOT / "tools/run_gama_porpoise_m5.py", ROOT / "tools/analyze_gama_porpoise.py", ROOT / "tools/test_gama_porpoise_analysis.py"]
    syntax = []
    for path in paths:
        ast.parse(path.read_text())
        syntax.append({"path": str(path.relative_to(ROOT)), "sha256": recorder.sha(path)})
    report = {"milestone": 5, "engineering_reproducibility": "passed", "engineering_passed": True,
              "biological_suitability": "provisional", "biological_approval": False,
              "human_review": {"reviewer": "MAR", "status": "pending", "decision_record": "m5_human_review.json"},
              "acceptance_scope": "Ten positive declared seeds, with three repeated in fresh processes; installed pinned runtime and unchanged engineering_porpoise_v1",
              "plan": str(plan_path.relative_to(ROOT)), "plan_sha256": recorder.sha(plan_path),
              "execution": str(execution_path.relative_to(ROOT)), "execution_sha256": recorder.sha(execution_path),
              "fresh_process_runs": 13, "distinct_seeds": 10, "samples_per_run": 41, "total_samples": 533,
              "canonical_excluded_fields": ["run_id"], "repeats": repeats, "variation": variation, "runs": runs,
              "representative_pose_source": {"path": str(m4_path.relative_to(ROOT)), "trajectory": str(original.relative_to(ROOT)),
                                              "m5_run_id": representative["run_id"], "canonical_equal_to_m5": True,
                                              "source_results_sha256": recorder.sha(m4_path),
                                              "note": "Reused six actual M4 poses from the identical model/configuration/seed/state sequence; no new M5 Kit capture"},
              "zero_seed_edge_case": {"run_id": "m5_retry_seed_0_a", "requested_seed": 0, "actual_exported_seed": actual_zero,
                                      "rejected_before_trajectory_acceptance": True, "included_in_positive_acceptance_workload": False,
                                      "scope": "Observed counterexample on this installed model/runtime; zero is outside the declared positive-seed acceptance scope"},
              "sandbox_attempt": {"run_id": "m5_seed_0_a", "status": "failed", "reason": "Installed /opt GAMA configuration was not writable inside sandbox", "retained": True},
              "preservation": preservation, "tests": tests, "total_tests": sum(t["count"] for t in tests),
              "python_syntax_checked": syntax, "marlin_scene_mutated": False, "milestone_6_started": False}
    recorder.write_json(output, report)
    print(json.dumps({k:report[k] for k in ("engineering_reproducibility", "biological_suitability", "human_review", "fresh_process_runs", "distinct_seeds", "total_samples", "total_tests", "repeats")}))


if __name__ == "__main__":
    main()
