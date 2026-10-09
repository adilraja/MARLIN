"""Declare and execute M5's fresh-process workload using the unchanged M3 recorder."""
import argparse
from datetime import datetime, timezone
import json
import os
import re
from pathlib import Path
import subprocess
import sys

import gama_porpoise as recorder

ROOT = recorder.ROOT
QA = ROOT / "experiments/gama_marlin_v1/qa"
SEEDS = (1, 2, 42, 1729, 184729, 20261008, 314159, 8675309, 123456789, 2147483647)
REPEATED_SEEDS = (1, 184729, 2147483647)
PIN_FIELDS = ("runtime", "launcher", "launcher_sha256", "runtime_configuration_sha256",
              "model_sha256", "configuration_sha256", "asset_calibration_sha256", "asset_sha256")


def declared_plan(campaign):
    previous = json.loads((ROOT / "experiments/gama_marlin_v1/trajectories/m3_seed_184729_a/execution.json").read_text())
    return {"milestone": 5, "campaign": campaign, "orchestrator_sha256": recorder.sha(Path(__file__)),
            "declared_at_utc": datetime.now(timezone.utc).isoformat(),
            "model_version": "engineering_porpoise_v1", "seeds": list(SEEDS),
            "seed_zero_edge_case": "Retained rejected run m5_retry_seed_0_a; requested 0, actual exported 0.0180602312789524. Positive-seed acceptance scope only; no seed remapping or model change.",
            "repeat_seeds": list(REPEATED_SEEDS), "fresh_process_executions": 13,
            "launch_policy": "sequential; one new recorder and GAMA launcher/JVM invocation per run; distinct workspace and output",
            "pins": {key: previous[key] for key in PIN_FIELDS},
            "canonical_excluded_fields": ["run_id"], "same_seed_comparison": "exact canonical bytes",
            "cross_seed_variation": "initial phase and horizontal pose only; seed values alone do not demonstrate variation",
            "metric_tolerances": {"position_m": 1e-8, "heading_deg": 1e-8, "depth_m": 1e-8,
                                  "speed_mps": 1e-10, "clock_s": 1e-9, "turn_rate_deg_per_s": 1e-7},
            "runs": [{"run_id": f"{campaign}_seed_{seed}_{suffix}", "seed": seed, "repeat": suffix == "b"}
                     for suffix, seeds in (("a", SEEDS), ("b", REPEATED_SEEDS)) for seed in seeds],
            "reviewer": "MAR", "human_review_completed": False, "biological_approval": False}


def verify_current_pins(plan):
    pins = plan["pins"]
    config = json.loads(recorder.CONFIG.read_text())
    recorder.validate_config(config)
    calibration_path = ROOT / config["asset_calibration_record"]
    calibration = json.loads(calibration_path.read_text())
    paths = {"model_sha256": recorder.MODEL, "configuration_sha256": recorder.CONFIG,
             "asset_calibration_sha256": calibration_path, "asset_sha256": ROOT / calibration["asset"]["path"],
             "launcher_sha256": Path(pins["launcher"]),
             "runtime_configuration_sha256": Path("/opt/gama-platform/configuration/config.ini")}
    for key, path in paths.items():
        if recorder.sha(path) != pins[key]:
            raise ValueError(f"Pinned input changed: {key}")
    if plan["seeds"] != list(SEEDS) or plan["repeat_seeds"] != list(REPEATED_SEEDS):
        raise ValueError("Declared seed workload changed")
    if len(plan["runs"]) != 13 or len({r["run_id"] for r in plan["runs"]}) != 13:
        raise ValueError("Expected thirteen distinct run IDs")
    if plan["runs"] != declared_plan(plan["campaign"])["runs"]:
        raise ValueError("Declared run identities changed")
    if recorder.sha(Path(__file__)) != plan["orchestrator_sha256"]:
        raise ValueError("Orchestrator changed after declaration")


def execute(plan, plan_path):
    verify_current_pins(plan)
    report_path = QA / (plan["campaign"] + "_execution.json")
    logs = QA / (plan["campaign"] + "_recorder_logs")
    if report_path.exists() or logs.exists():
        raise ValueError("Preserve existing M5 campaign evidence")
    for item in plan["runs"]:
        for path in (ROOT / "experiments/gama_marlin_v1/trajectories" / item["run_id"],
                     ROOT / "artifacts/gama_marlin_v1/workspaces" / item["run_id"]):
            if path.exists():
                raise ValueError(f"Refusing an existing run/workspace: {item['run_id']}")
    logs.mkdir()
    report = {"milestone": 5, "passed": False, "plan_sha256": recorder.sha(plan_path),
              "started_at_utc": datetime.now(timezone.utc).isoformat(), "runs": [],
              "marlin_http_used": False, "scene_actor_acquired": False, "biological_approval": False}
    try:
        for number, item in enumerate(plan["runs"], 1):
            command = [sys.executable, "-B", "tools/gama_porpoise.py", "--run-id", item["run_id"], "--seed", str(item["seed"])]
            log_path = logs / (item["run_id"] + ".log")
            with log_path.open("x") as log:
                process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
                try:
                    code = process.wait(timeout=220)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    raise RuntimeError(f"Recorder timed out: {item['run_id']}")
            directory = ROOT / "experiments/gama_marlin_v1/trajectories" / item["run_id"]
            execution = json.loads((directory / "execution.json").read_text()) if (directory / "execution.json").exists() else {}
            row = {**item, "recorder_process_id": process.pid, "return_code": code,
                   "command": command, "recorder_log": str(log_path.relative_to(ROOT)),
                   "recorder_log_sha256": recorder.sha(log_path), "directory": str(directory.relative_to(ROOT)),
                   "execution_sha256": recorder.sha(directory / "execution.json") if execution else None,
                   "status": execution.get("status", "missing_execution_record")}
            report["runs"].append(row)
            if code != 0 or execution.get("status") != "passed":
                raise RuntimeError(f"Run failed; evidence retained: {item['run_id']}")
            for key in PIN_FIELDS:
                if execution.get(key) != plan["pins"][key]:
                    raise ValueError(f"Run pin mismatch: {item['run_id']} {key}")
            if execution["actual_seed"] != item["seed"]:
                raise ValueError("Actual seed mismatch")
            print(json.dumps({"completed": number, "total": 13, "run_id": item["run_id"],
                              "seed": item["seed"], "samples": execution["samples"], "status": "passed"}), flush=True)
        verify_current_pins(plan)
        report["passed"] = True
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        recorder.write_json(report_path, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--declare-only", action="store_true")
    parser.add_argument("--campaign", default="m5", help="Fresh safe prefix for a retained retry campaign")
    args = parser.parse_args()
    if not re.fullmatch(r"m5(?:_[A-Za-z0-9_]+)?", args.campaign):
        raise ValueError("Campaign must be m5 or m5_<safe_suffix>")
    plan_path = ROOT / "experiments/gama_marlin_v1" / (args.campaign + "_execution_plan.json")
    if args.declare_only:
        plan = declared_plan(args.campaign)
        verify_current_pins(plan)
        recorder.write_json(plan_path, plan)
        print(json.dumps({"plan": str(plan_path), "seeds": plan["seeds"], "repeat_seeds": plan["repeat_seeds"], "executions": 13}))
    else:
        plan = json.loads(plan_path.read_text())
        execute(plan, plan_path)


if __name__ == "__main__":
    main()
