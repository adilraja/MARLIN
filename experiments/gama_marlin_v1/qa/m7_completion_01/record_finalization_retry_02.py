"""Record the second finalization attempt with unchanged earlier receipts.

Only the fixed new finalizer command is supported. Its binary stdout/stderr
and execution receipt remain outside the seal until the later independent
retry seal check binds them. This helper performs no Kit or rendering call.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BLOCKED = {"_build", "extscache", "__pycache__", ".cache"}


def safe(path):
    path = Path(path)
    if BLOCKED.intersection(path.parts) or path.suffix == ".pyc":
        raise ValueError("Generated paths are prohibited")
    resolved = path.resolve()
    if not resolved.is_relative_to(ROOT) or BLOCKED.intersection(resolved.parts) or resolved.suffix == ".pyc":
        raise ValueError("Evidence must remain inside the repository outside generated directories")
    return resolved


def digest(path):
    value = hashlib.sha256()
    with safe(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def command():
    return ["/usr/bin/python3", "-B", str(HERE / "finalize_acceptance.py"),
            "--acceptance", str(HERE / "acceptance_retry_02.json"),
            "--final-live-check", str(HERE / "final_live_demo/results.json"),
            "--runtime-log-snapshots", str(HERE / "runtime_log_snapshots"),
            "--execution-record", str(HERE / "acceptance_retry_02_execution.json"),
            "--execution-record", str(HERE / "final_live_execution_binding.json"),
            "--active-log", str(HERE / "finalize_retry_02_command.log")]


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    actual_command = command()
    program, runner = safe(actual_command[2]), safe(Path(__file__))
    log, receipt = HERE / "finalize_retry_02_command.log", HERE / "finalize_retry_02_execution.json"
    if log.exists() or receipt.exists():
        raise ValueError("Existing retry command logs/receipts cannot be overwritten")
    started, clock = now(), time.monotonic()
    before_program, before_runner = digest(program), digest(runner)
    completed, error, timed_out = None, None, False
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    with log.open("xb") as stream:
        try:
            completed = subprocess.run(actual_command, cwd=ROOT, env=environment,
                                       stdout=stream, stderr=subprocess.STDOUT,
                                       timeout=900, check=False)
        except subprocess.TimeoutExpired as failure:
            error, timed_out = f"{type(failure).__name__}: {failure}", True
        except Exception as failure:
            error = f"{type(failure).__name__}: {failure}"
    after_program, after_runner = digest(program), digest(runner)
    code = None if completed is None else completed.returncode
    execution = {"kind": "m7_actual_finalization_command_execution", "operation": "finalize", "retry_index": 2,
                 "command": actual_command, "runner_command": [sys.executable, "-B", *sys.argv],
                 "cwd": str(ROOT), "started_at_utc": started, "finished_at_utc": now(),
                 "elapsed_seconds": time.monotonic() - clock, "return_code": code,
                 "log": str(log), "log_sha256": digest(log), "log_bytes": log.stat().st_size,
                 "actual_stdout_stderr_retained_as_binary": True,
                 "source_sha256_before": before_program, "source_sha256_after": after_program,
                 "runner_sha256_before": before_runner, "runner_sha256_after": after_runner,
                 "live_calls_made": False, "new_renders_requested": 0,
                 "timeout_seconds": 900, "terminated_by_timeout": timed_out,
                 "post_seal_finalizer_receipt": True,
                 "finalizer_receipts_require_later_independent_seal_binding": True,
                 "original_failed_finalizer_execution": str(HERE / "finalize_execution.json"),
                 "original_failed_finalizer_log": str(HERE / "finalize_command.log"),
                 "original_receipts_rewritten": False}
    if error:
        execution["error"] = error
    execution["passed"] = (code == 0 and not error and before_program == after_program and before_runner == after_runner)
    with receipt.open("x") as stream:
        json.dump(execution, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(log.read_bytes().decode("utf-8", errors="replace"), end="", flush=True)
    print(json.dumps({"operation": "finalize", "retry_index": 2, "passed": execution["passed"], "execution": str(receipt)}), flush=True)
    if not execution["passed"]:
        raise SystemExit(code if code not in (None, 0) else 1)


if __name__ == "__main__":
    main()
