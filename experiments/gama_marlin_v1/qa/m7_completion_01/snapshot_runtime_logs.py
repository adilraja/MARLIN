"""Retain fixed-prefix snapshots of the three authorized Kit restart logs.

This reads QA log files only. It never opens generated/runtime directories,
controls Kit, requests a capture or treats a still-appended log as immutable.
The source's initially observed byte count fixes the snapshot prefix; later
appended bytes are outside that snapshot and remain explicitly unsealed.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
QA = ROOT / "experiments/gama_marlin_v1/qa"
HERE = Path(__file__).resolve().parent
FORBIDDEN = {"_build", "extscache", "__pycache__", ".cache"}
LOG_NAMES = ("kit_restart_01", "kit_restart_02", "kit_restart_03")


def safe(path):
    path = Path(path)
    if path.is_symlink() or FORBIDDEN.intersection(path.parts) or path.suffix == ".pyc":
        raise ValueError("Generated or symlink input prohibited")
    resolved = path.resolve()
    if not resolved.is_relative_to(QA) or FORBIDDEN.intersection(resolved.parts) or resolved.suffix == ".pyc":
        raise ValueError("Log evidence must resolve into scoped QA")
    return resolved


def now():
    return datetime.now(timezone.utc).isoformat()


def prefix_sha(path, count):
    value = hashlib.sha256()
    remaining = count
    with safe(path).open("rb") as stream:
        while remaining:
            chunk = stream.read(min(1024 * 1024, remaining))
            if not chunk:
                raise ValueError("Source log truncated before its fixed prefix was read")
            value.update(chunk)
            remaining -= len(chunk)
    return value.hexdigest()


def snapshot(source, destination):
    source = safe(source)
    before = source.stat()
    if not source.is_file() or before.st_size <= 0:
        raise ValueError("An actual nonempty retained log is required")
    value = hashlib.sha256()
    remaining = before.st_size
    with source.open("rb") as original, destination.open("xb") as copied:
        while remaining:
            chunk = original.read(min(1024 * 1024, remaining))
            if not chunk:
                raise ValueError("Source log truncated during snapshot; partial evidence remains retained")
            copied.write(chunk)
            value.update(chunk)
            remaining -= len(chunk)
    after = source.stat()
    if (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino) or after.st_size < before.st_size:
        raise ValueError("Log source was replaced/truncated while snapshotting")
    expected = value.hexdigest()
    if destination.stat().st_size != before.st_size or prefix_sha(destination, before.st_size) != expected:
        raise ValueError("Snapshot bytes differ from the exact initial source prefix")
    rechecked = prefix_sha(source, before.st_size)
    if rechecked != expected:
        raise ValueError("Initial source log prefix changed during its snapshot")
    return {"source_log": str(source.relative_to(ROOT)), "initial_source_size_bytes": before.st_size,
            "initial_bytes_read": before.st_size, "source_size_after_copy_bytes": after.st_size,
            "source_prefix_bytes_rechecked": before.st_size, "source_initial_prefix_sha256": expected,
            "source_rechecked_prefix_sha256": rechecked, "copy": str(destination.relative_to(ROOT)),
            "copy_bytes": destination.stat().st_size, "copy_sha256": expected,
            "source_inode_unchanged": True, "copy_exact_initial_prefix": True,
            "source_size_unchanged_during_copy": before.st_size == after.st_size,
            "source_stream_may_append": True, "post_prefix_source_bytes_included": False,
            "original_source_log_sealed_as_immutable": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = safe(args.output)
    if output.parent != HERE or output.exists():
        raise ValueError("Use a new exclusive log-snapshot directory directly in completion01")
    output.mkdir()
    source = Path(__file__).resolve()
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    report = {"kind": "m7_fixed_prefix_runtime_log_snapshots", "passed": False, "started_at_utc": now(),
              "command": [sys.executable, "-B", *sys.argv], "helper_sha256_before": source_sha,
              "live_calls_made": False, "captures_requested": False, "kit_control_requested": False,
              "original_logs_modified": False, "source_streams_can_append_after_snapshot": True,
              "limitation": "Only each initially observed fixed prefix is copied and hashed; subsequent appended source bytes are outside the immutable snapshots.",
              "snapshots": []}
    try:
        for name in LOG_NAMES:
            report["snapshots"].append(snapshot(QA / name / "kit_process.log", output / (name + "_prefix.log")))
        report["helper_sha256_after"] = hashlib.sha256(source.read_bytes()).hexdigest()
        report["passed"] = len(report["snapshots"]) == 3 and report["helper_sha256_after"] == source_sha
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    report["finished_at_utc"] = now()
    with (output / "manifest.json").open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": report["passed"], "snapshots": len(report["snapshots"]), "output": str(output), "error": report.get("error")}, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
