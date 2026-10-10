"""Retain a fresh read-only historical preservation invocation for M8.

This wrapper keeps the existing M7 preservation checker and all milestone seals
unchanged. Its raw output still names that checker's historical scope; this
execution record identifies why it was invoked during M8. It is not a final M8
acceptance or a seal of the sprint report under construction.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time

QA = Path(__file__).resolve().parent
ROOT = QA.parents[2]
CHECKER = QA / "check_m7_preservation.py"
HELPER = QA / "run_m4_checks.py"


def sha(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def pin(path):
    return {"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": sha(path)}


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stem", default="m8_preservation_initial_01")
    parser.add_argument("--phase", choices=("initial", "final"), default="initial")
    args = parser.parse_args()
    if (not args.stem.startswith("m8_preservation_") or not args.stem
            or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for character in args.stem)):
        raise ValueError("Use a safe exclusive m8_preservation_ output stem")
    result, log, execution = [QA / (args.stem + suffix) for suffix in (".json", ".log", "_execution.json")]
    if any(path.exists() for path in (result, log, execution)):
        raise ValueError("Existing preservation evidence cannot be overwritten")
    sources = [CHECKER, HELPER, Path(__file__).resolve()]
    before = [pin(path) for path in sources]
    command = ["/usr/bin/python3", "-B", str(CHECKER), "--output", str(result)]
    started, monotonic = now(), time.monotonic()
    with log.open("xb") as stream:
        completed = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=False)
    finished, duration = now(), time.monotonic() - monotonic
    after = [pin(path) for path in sources]
    raw = json.loads(result.read_text()) if result.is_file() else None
    record = {"kind": "m8_historical_preservation_execution", "milestone": 8, "phase": args.phase,
              "final_m8_acceptance_claimed": False,
              "scope": "Historical protected inventories and exact historical source anchors; no new final-report seal",
              "command": command, "cwd": str(ROOT), "return_code": completed.returncode,
              "started_at_utc": started, "finished_at_utc": finished, "duration_seconds": duration,
              "checker_report_milestone": None if raw is None else raw.get("milestone"),
              "checker_report_scope": None if raw is None else raw.get("scope"),
              "source_pins_before": before, "source_pins_after": after, "sources_unchanged": before == after,
              "result": pin(result) if result.is_file() else None, "actual_stdout_stderr": pin(log),
              "live_calls_made": False, "tests_rerun": False, "biological_approval": False,
              "passed": completed.returncode == 0 and raw is not None and raw.get("passed") is True and before == after}
    with execution.open("x") as stream:
        stream.write(json.dumps(record, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": record["passed"], "phase": args.phase, "execution": str(execution),
                      "duration_seconds": duration, "result": str(result)}, indent=2))
    if not record["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
