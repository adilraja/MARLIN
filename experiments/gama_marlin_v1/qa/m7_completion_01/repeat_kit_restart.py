"""Reuse the verified Kit-only restart procedure between pending snapshots."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[4]
QA = ROOT / "experiments/gama_marlin_v1/qa"
BASE = QA / "kit_restart_01/restart_kit.py"
spec = importlib.util.spec_from_file_location("verified_kit_restart", BASE)
restart = importlib.util.module_from_spec(spec)
spec.loader.exec_module(restart)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("stop-launch", "restore"))
    parser.add_argument("--old-pid", type=int)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = restart.live.safe_path(args.output)
    if output.parent != QA or not output.name.startswith("kit_restart_"):
        raise ValueError("Use a new Kit restart evidence directory directly under sprint QA")
    if args.phase == "stop-launch":
        if args.old_pid is None or args.old_pid <= 1:
            raise ValueError("Supply the observed Kit PID; the base procedure checks owner/argv/cwd")
        output.mkdir(exist_ok=False)
        original = QA / "kit_restart_01/recovery_payloads.json"
        target = output / "recovery_payloads.json"
        shutil.copyfile(original, target)
        if restart.live.digest(original) != restart.live.digest(target):
            raise ValueError("Verified recovery payload copy changed")
        restart.OLD_PID = args.old_pid
    elif not output.is_dir() or not json.loads((output / "stop_launch_result.json").read_text())["passed"]:
        raise ValueError("A passed restart is required before recovery")
    restart.OUTPUT = output
    name = args.phase.replace("-", "_") + "_result.json"
    if (output / name).exists():
        raise ValueError("Existing restart evidence cannot be overwritten")
    report = {"kind": "authorized_kit_restart_between_pending_snapshots", "phase": args.phase,
              "passed": False, "started_at": restart.now(), "desktop_restarted": False,
              "gpu_guard_changed": False, "controller_animation_phase_preserved": False,
              "capture_requested": False, "command": [sys.executable, "-B", *sys.argv],
              "authorization": "Kit-only restart authorized by 'Why don't you do it?'; remaining captures authorized by 'So let's do the remaining 30 captures then.'",
              "base_restart_helper": {"path": str(BASE), "sha256": restart.live.digest(BASE)},
              "source_helper_sha256_before": restart.live.digest(Path(__file__))}
    try:
        (restart.stop_launch if args.phase == "stop-launch" else restart.restore)(report)
        report["passed"] = True
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    finally:
        report["source_helper_sha256_after"] = restart.live.digest(Path(__file__))
        report["base_helper_unchanged"] = restart.live.digest(BASE) == report["base_restart_helper"]["sha256"]
        report["passed"] = report["passed"] and report["base_helper_unchanged"] and report["source_helper_sha256_before"] == report["source_helper_sha256_after"]
        report["finished_at"] = restart.now()
        restart.write(name, report)
    print(json.dumps({"passed": report["passed"], "result": str(output/name), "error": report.get("error")}), flush=True)
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
