"""Record the fixed offline closeout finalizer after its separate review."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PROGRAM = HERE / "finalize_closeout.py"
MANIFEST = HERE / "closeout_manifest.json"
LOG = HERE / "closeout_command.log"
RECEIPT = HERE / "closeout_execution.json"


def pin(path):
    raw = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def main():
    if len(sys.argv) != 1 or any(path.exists() for path in (MANIFEST, LOG, RECEIPT)):
        raise ValueError("Use the fixed recorder with exclusive new closeout outputs")
    source_before, runner_before = pin(PROGRAM), pin(Path(__file__).resolve())
    command = ["/usr/bin/python3", "-B", str(PROGRAM)]
    started, clock = datetime.now(timezone.utc).isoformat(), time.monotonic()
    with LOG.open("xb") as stream:
        process = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=False)
    source_after, runner_after = pin(PROGRAM), pin(Path(__file__).resolve())
    receipt = {"kind": "sprint_closeout_actual_finalization_execution", "command": command, "cwd": str(ROOT),
               "started_at_utc": started, "finished_at_utc": datetime.now(timezone.utc).isoformat(),
               "elapsed_seconds": time.monotonic() - clock, "return_code": process.returncode,
               "source_before": source_before, "source_after": source_after,
               "runner_before": runner_before, "runner_after": runner_after,
               "source_pins_unchanged": source_before == source_after and runner_before == runner_after,
               "log": pin(LOG), "manifest": pin(MANIFEST) if MANIFEST.is_file() else None,
               "post_seal_receipt": True, "requires_later_independent_seal_binding": True,
               "live_calls_made": False, "new_renders": 0, "new_gama_executions": 0,
               "regression_tests_rerun": False, "ml_training_or_inference_performed": False,
               "old_outputs_written": False,
               "passed": process.returncode == 0 and source_before == source_after and runner_before == runner_after}
    with RECEIPT.open("x") as stream:
        json.dump(receipt, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": receipt["passed"], "manifest": receipt["manifest"],
                      "execution": str(RECEIPT), "log": str(LOG)}, indent=2))
    if not receipt["passed"]:
        raise SystemExit(process.returncode or 1)


if __name__ == "__main__":
    main()
