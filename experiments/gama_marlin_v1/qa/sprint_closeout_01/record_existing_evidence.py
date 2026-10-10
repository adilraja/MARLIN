"""Record one fixed offline retained-evidence proof with actual process output."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PROGRAM = HERE / "verify_existing_evidence.py"
RESULT = HERE / "existing_evidence_validation.json"
LOG = HERE / "existing_evidence_command.log"
RECEIPT = HERE / "existing_evidence_execution.json"


def pin(path):
    raw = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def main():
    if len(sys.argv) != 1:
        raise ValueError("This recorder has one fixed command and accepts no arguments")
    if any(path.exists() for path in (RESULT, LOG, RECEIPT)):
        raise ValueError("Retained proof outputs must be exclusive new files")
    source_before = pin(PROGRAM)
    runner_before = pin(Path(__file__).resolve())
    command = ["/usr/bin/python3", "-B", str(PROGRAM), "--output", str(RESULT)]
    started = datetime.now(timezone.utc).isoformat()
    monotonic = time.monotonic()
    with LOG.open("xb") as stream:
        process = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=False)
    finished = datetime.now(timezone.utc).isoformat()
    source_after = pin(PROGRAM)
    runner_after = pin(Path(__file__).resolve())
    unchanged = source_before == source_after and runner_before == runner_after
    receipt = {"kind": "sprint_closeout_retained_acceptance_actual_execution", "command": command,
               "cwd": str(ROOT), "started_at_utc": started, "finished_at_utc": finished,
               "elapsed_seconds": time.monotonic() - monotonic, "return_code": process.returncode,
               "log": pin(LOG), "result": pin(RESULT) if RESULT.exists() else None,
               "source_before": source_before, "source_after": source_after,
               "runner_before": runner_before, "runner_after": runner_after,
               "source_pins_unchanged": unchanged, "live_calls_made": False,
               "regression_tests_rerun": False, "new_renders": 0, "new_gama_executions": 0,
               "ml_training_or_inference_performed": False, "old_outputs_written": False,
               "passed": process.returncode == 0 and unchanged}
    with RECEIPT.open("x") as stream:
        json.dump(receipt, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": receipt["passed"], "return_code": process.returncode,
                      "receipt": str(RECEIPT), "result": str(RESULT), "log": str(LOG)}, indent=2))
    if not receipt["passed"]:
        raise SystemExit(process.returncode or 1)


if __name__ == "__main__":
    main()
