"""Sequential, read-only selection of completed retained M7 capture groups.

The capture client is independent of this process. A group becomes eligible
only after its final group_result and manifest both report a passed group.
Each invocation and all actual combined output are retained exclusively in a
separate validation directory. No HTTP, Kit or renderer call is made.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time


ROOT = Path(__file__).resolve().parents[3]
PYTHON = "/home/madil/opt/blender-5.0.1-linux-x64/5.0/python/bin/python3.11"
VERIFIER = Path(__file__).with_name("verify_m7_group.py")
SEEDS = (1, 42, 184729, 20261008, 2147483647)
STEPS = (8, 16, 32)
PINNED_SOURCES = (
    VERIFIER, Path(__file__), Path(__file__).with_name("verify_m6_scene.py"),
    ROOT / "source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge/dataset_state_v2.py",
    ROOT / "source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge/paired_state_v2.py",
    ROOT / "source/extensions/cris.madil.render_service/cris/madil/render_service/calibration_geometry.py",
    ROOT / "source/extensions/cris.madil.render_service/cris/madil/render_service/capture_projection.py",
)


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def write(path, value):
    with path.open("x") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


def ready(step_path):
    final_result = step_path / "group_result.json"
    manifest_path = step_path / "group/manifest.json"
    if not final_result.is_file() or not manifest_path.is_file():
        return False
    try:
        result, manifest = (json.loads(path.read_text()) for path in (final_result, manifest_path))
    except json.JSONDecodeError:
        # The capture client writes its final result only after restoration;
        # a partially written final JSON is not an eligible retained group.
        return False
    accepted = (result.get("passed") is True and manifest.get("passed") is True
                and manifest.get("status") == "passed" and manifest.get("milestone") == 7
                and manifest.get("recovery_required") is False
                and manifest.get("restoration_errors") == [])
    if accepted:
        run_id, step = step_path.parent.name, int(step_path.name.removeprefix("step_"))
        source = manifest["source_state"]
        if (result.get("run_id") != run_id or result.get("step_index") != step
                or source.get("run_id") != run_id or source.get("step_index") != step):
            raise ValueError("Accepted group source state differs from its declared trajectory/snapshot path")
    return accepted


def verify_one(campaign, output, run_id, step, pins):
    step_path = campaign / "captures" / run_id / f"step_{step:03d}"
    group = step_path / "group"
    stem = f"{run_id}__step_{step:03d}"
    result_path, log_path = output / (stem + ".json"), output / (stem + ".log")
    execution_path = output / (stem + "_execution.json")
    if any(path.exists() for path in (result_path, log_path, execution_path)):
        raise ValueError("Refusing to replace an existing validation: " + stem)
    if {str(path.relative_to(ROOT)): digest(path) for path in PINNED_SOURCES} != pins:
        raise ValueError("Pinned verifier/helper sources changed before group verification")
    result_before = digest(step_path / "group_result.json")
    manifest_before = digest(group / "manifest.json")
    command = [PYTHON, "-B", str(VERIFIER), "--group", str(group), "--output", str(result_path)]
    started, monotonic_start = now(), time.monotonic()
    with log_path.open("xb") as log:
        completed = subprocess.run(command, cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT, check=False)
    finished, duration = now(), time.monotonic() - monotonic_start
    validation = json.loads(result_path.read_text()) if result_path.is_file() else None
    current_pins = {str(path.relative_to(ROOT)): digest(path) for path in PINNED_SOURCES}
    unchanged = (result_before == digest(step_path / "group_result.json")
                 and manifest_before == digest(group / "manifest.json") and current_pins == pins)
    execution = {"kind": "m7_independent_group_verifier_execution", "run_id": run_id, "step_index": step,
                 "command": command, "cwd": str(ROOT), "return_code": completed.returncode,
                 "started_at_utc": started, "finished_at_utc": finished, "duration_seconds": duration,
                 "source_sha256": pins, "actual_combined_stdout_stderr": str(log_path.relative_to(ROOT)),
                 "log_sha256": digest(log_path), "result_sha256": digest(result_path) if result_path.is_file() else None,
                 "capture_result_sha256": result_before, "capture_manifest_sha256": manifest_before,
                 "source_and_retained_group_markers_unchanged": unchanged,
                 "runtime": validation.get("runtime") if validation else None,
                 "passed": completed.returncode == 0 and validation is not None and validation.get("passed") is True and unchanged}
    write(execution_path, execution)
    print(json.dumps({"event": "independent_group_verified", "run_id": run_id, "step_index": step,
                      "passed": execution["passed"], "captures_verified": len(validation.get("captures", [])) if validation else 0,
                      "result": str(result_path), "error": validation.get("error") if validation else "No retained verifier result"}), flush=True)
    if not execution["passed"]:
        raise ValueError("Independent group verification failed; retained output: " + stem)
    return {"run_id": run_id, "step_index": step, "result": str(result_path.relative_to(output)),
            "result_sha256": digest(result_path), "execution": str(execution_path.relative_to(output)),
            "execution_sha256": digest(execution_path), "passed": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--poll-seconds", type=float, default=5)
    parser.add_argument("--timeout-seconds", type=float, default=3600)
    args = parser.parse_args()
    campaign, output = args.campaign.resolve(), args.output.resolve()
    scoped_qa = Path(__file__).resolve().parent
    if not campaign.is_relative_to(scoped_qa) or not output.is_relative_to(scoped_qa):
        raise ValueError("Campaign and validation output must stay in this scoped sprint QA directory")
    if not campaign.is_dir() or output.exists() or not 0 < args.poll_seconds <= 30 or args.timeout_seconds <= 0:
        raise ValueError("Require an existing campaign, exclusive output and bounded polling")
    output.mkdir()
    pins = {str(path.relative_to(ROOT)): digest(path) for path in PINNED_SOURCES}
    pending = [(f"m5_positive_seed_{seed}_a", step) for seed in SEEDS for step in STEPS]
    report = {"kind": "m7_independent_campaign_group_verification", "passed": False,
              "started_at_utc": now(), "campaign": str(campaign), "expected_groups": len(pending),
              "source_sha256": pins, "groups": []}
    deadline = time.monotonic() + args.timeout_seconds
    try:
        while pending:
            completed = []
            for run_id, step in pending:
                if ready(campaign / "captures" / run_id / f"step_{step:03d}"):
                    report["groups"].append(verify_one(campaign, output, run_id, step, pins))
                    completed.append((run_id, step))
            pending = [item for item in pending if item not in completed]
            if not pending:
                break
            campaign_result = campaign / "results.json"
            if campaign_result.is_file():
                try:
                    json.loads(campaign_result.read_text())
                except json.JSONDecodeError:
                    pass
                else:
                    if all(ready(campaign / "captures" / run_id / f"step_{step:03d}") for run_id, step in pending):
                        continue
                    raise ValueError("Campaign finished without all expected accepted retained groups")
            if time.monotonic() >= deadline:
                raise TimeoutError("Timed out waiting for completed retained groups")
            time.sleep(args.poll_seconds)
        report["passed"] = len(report["groups"]) == report["expected_groups"]
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    report.update(finished_at_utc=now(), pending_groups=[{"run_id": run_id, "step_index": step} for run_id, step in pending])
    write(output / "results.json", report)
    print(json.dumps({"event": "independent_campaign_verification_finished", "passed": report["passed"],
                      "groups_verified": len(report["groups"]), "error": report.get("error")}), flush=True)
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
