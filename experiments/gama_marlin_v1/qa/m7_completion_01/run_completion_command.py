"""Retain real command/log/execution records for fixed M7 completion steps."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

OUTPUT = Path(__file__).resolve().parent
QA = OUTPUT.parent
ROOT = OUTPUT.parents[3]
CAMPAIGN = QA / "m7_capture_set"
PROOFS = QA / "m7_scene_validation_set"
REVIEW = QA / "m7_review"
DATASET = ROOT / "experiments/gama_marlin_v1/datasets/m7_engineering_v1"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("aggregate", "review", "export", "preservation", "history", "acceptance", "finalize"))
    args = parser.parse_args()
    python = ["/usr/bin/python3", "-B"]
    commands = {
        "aggregate": python + [str(OUTPUT / "aggregate_capture_set.py"), "--output", str(CAMPAIGN)],
        "review": python + [str(OUTPUT / "finalize_review.py")],
        "export": python + [str(ROOT / "tools/export_gama_dataset_v2.py"), "--campaign", str(CAMPAIGN),
                            "--scene-verifications", str(PROOFS), "--visual-review", str(REVIEW / "visual_inspection.json"),
                            "--output", str(DATASET)],
        "preservation": python + [str(QA / "check_m7_preservation.py"), "--output", str(OUTPUT / "original_preservation.json")],
        "history": python + [str(QA / "check_m8_m7_progress_preservation.py"), "--output", str(OUTPUT / "historical_progress_preservation.json")],
        "acceptance": python + [str(OUTPUT / "validate_completion.py"), "--campaign", str(CAMPAIGN),
                                "--scene-verifications", str(PROOFS), "--review", str(REVIEW), "--dataset", str(DATASET),
                                "--execution-record", str(OUTPUT / "aggregate_execution.json"),
                                "--execution-record", str(OUTPUT / "export_execution.json"),
                                "--preservation", str(OUTPUT / "original_preservation.json"),
                                "--history-preservation", str(OUTPUT / "historical_progress_preservation.json"),
                                "--output", str(OUTPUT / "acceptance.json")],
        "finalize": python + [str(OUTPUT / "finalize_acceptance.py"), "--acceptance", str(OUTPUT / "acceptance.json"),
                              "--final-live-check", str(OUTPUT / "final_live_demo/results.json"),
                              "--execution-record", str(OUTPUT / "acceptance_execution.json")],
    }
    command = commands[args.operation]
    log = OUTPUT / f"{args.operation}_command.log"
    record = OUTPUT / f"{args.operation}_execution.json"
    if log.exists() or record.exists():
        raise ValueError("Existing command evidence cannot be overwritten")
    started, clock = now(), time.monotonic()
    helper_before = digest(Path(__file__))
    source = Path(command[2])
    source_before = digest(source)
    completed = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, timeout=600)
    with log.open("x") as stream:
        stream.write(completed.stdout)
    execution = {"kind": "m7_actual_completion_command_execution", "operation": args.operation,
                 "command": command, "runner_command": [sys.executable, "-B", *sys.argv], "cwd": str(ROOT),
                 "started_at_utc": started, "finished_at_utc": now(), "elapsed_seconds": time.monotonic() - clock,
                 "return_code": completed.returncode, "log": str(log), "log_sha256": digest(log),
                 "source_sha256_before": source_before, "source_sha256_after": digest(source),
                 "runner_sha256_before": helper_before, "runner_sha256_after": digest(Path(__file__)),
                 "live_calls_made": False, "new_renders_requested": 0}
    execution["passed"] = (completed.returncode == 0 and execution["source_sha256_before"] == execution["source_sha256_after"]
                           and execution["runner_sha256_before"] == execution["runner_sha256_after"])
    with record.open("x") as stream:
        stream.write(json.dumps(execution, indent=2, allow_nan=False) + "\n")
    print(completed.stdout, end="", flush=True)
    print(json.dumps({"operation": args.operation, "passed": execution["passed"], "execution": str(record)}), flush=True)
    if not execution["passed"]:
        raise SystemExit(completed.returncode or 1)


if __name__ == "__main__":
    main()
