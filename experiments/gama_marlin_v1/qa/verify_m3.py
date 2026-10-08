"""Revalidate retained real GAMA outputs, tests and baseline; no runtime mutation."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
import gama_porpoise as runner

QA = Path(__file__).resolve().parent
RUNS = ("m3_seed_184729_a", "m3_seed_184729_b")


def read(path):
    return json.loads(path.read_text())


def main():
    output = QA / "m3_validation.json"
    log_path = QA / "m3_export_tests.log"
    if output.exists() or log_path.exists():
        raise SystemExit("M3 verification evidence already exists; preserve it")
    config = read(runner.CONFIG)
    rows = []
    canonical = []
    for run_id in RUNS:
        directory = ROOT / "experiments/gama_marlin_v1/trajectories" / run_id
        report = read(directory / "execution.json")
        assert report["status"] == "passed" and report["return_code"] == 0
        assert report["runtime"]["gama.version"] == "2025.6.4"
        assert report["actual_seed"] == report["requested_seed"] == 184729
        assert not report["marlin_http_used"] and not report["scene_actor_acquired"]
        assert runner.sha(runner.MODEL) == runner.sha(directory / "model.gaml") == report["model_sha256"]
        assert runner.sha(runner.CONFIG) == report["configuration_sha256"]
        assert runner.sha(directory / "experiment.xml") == report["experiment_plan_sha256"]
        assert runner.sha(directory / "raw/simulation-outputs0.xml") == report["raw_xml_sha256"]
        assert runner.sha(directory / "trajectory.json") == report["trajectory_sha256"]
        copied_config = read(directory / "configuration.json")
        assert copied_config == {"configuration": config, "run_id": run_id, "requested_seed": 184729}
        states, validation = runner.read_trajectory(directory / "raw/simulation-outputs0.xml", config, run_id, 184729)
        assert states == read(directory / "trajectory.json")
        assert validation == read(directory / "validation.json")
        encoded = runner.canonical_states(states)
        assert hashlib.sha256(encoded).hexdigest() == report["canonical_state_sha256"]
        canonical.append(encoded)
        rows.append({"run_id": run_id, "execution": str((directory / "execution.json").relative_to(ROOT)),
                     "samples": len(states), "transitions": validation["transitions"],
                     "maximum_errors": validation["maximum_errors"],
                     "raw_xml_sha256": report["raw_xml_sha256"],
                     "canonical_state_sha256": report["canonical_state_sha256"]})
    assert canonical[0] == canonical[1], "Fresh same-seed GAMA state sequences differ"
    baseline = read(QA / "preserved_output_manifest.json")
    protected = [r for r in baseline["files"] if r["path"] != "source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge/extension.py"]
    changed = [r["path"] for r in protected if runner.sha(ROOT / r["path"]) != r["sha256"]]
    assert not changed, changed
    m2 = read(QA / "milestone_2_manifest.json")
    assert all(runner.sha(ROOT / r["path"]) == r["sha256"] for r in m2["outputs"])
    checkpoint = baseline["checkpoint"]
    assert all(runner.sha(ROOT / checkpoint[key]) == checkpoint["sha256"] for key in ("original", "backup"))
    command = [sys.executable, "-B", "tools/test_gama_porpoise.py", "-v"]
    result = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, timeout=60, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    with log_path.open("x") as log:
        log.write(result.stdout)
    assert result.returncode == 0, result.stdout
    tests = int(re.search(r"Ran (\d+) tests", result.stdout)[1])
    for path in (ROOT / "tools/gama_porpoise.py", ROOT / "tools/test_gama_porpoise.py", Path(__file__)):
        ast.parse(path.read_text())
    value = {"milestone": 3, "passed": True, "actual_gama_runs": 2, "distinct_seeds": 1,
             "same_seed_fresh_process_sequences_equal": True,
             "canonical_comparison_excluded_fields": ["run_id"],
             "runs": rows, "tests": {"command": command, "return_code": result.returncode,
                                     "count": tests, "log": str(log_path.relative_to(ROOT)),
                                     "log_sha256": runner.sha(log_path)},
             "protected_m1_files_unchanged": len(protected), "sealed_m2_outputs_unchanged": len(m2["outputs"]),
             "checkpoint_original_and_backup_hashes_match": True,
             "m5_ten_seed_workload_completed": False, "marlin_scene_application_verified": False,
             "biological_approval": False}
    runner.write_json(output, value)
    print(json.dumps(value, indent=2))


if __name__ == "__main__":
    main()
