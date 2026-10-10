"""One authorized, checkpoint-backed Kit restart; never restart the desktop."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[4]
OUTPUT = Path(__file__).resolve().parent
BASE = "http://127.0.0.1:8011"
OLD_PID = 3085814
CHECKPOINT = ROOT / "experiments/gama_marlin_v1/qa/memory_reclaim_01/checkpoint_result.json"
FORBIDDEN = {"_build", "extscache", "__pycache__", ".cache"}
sys.path.insert(0, str(ROOT / "tools"))
import verify_gama_paired_live as live


def now():
    return datetime.now(timezone.utc).isoformat()


def write(name, value):
    with (OUTPUT / name).open("x") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


def request(path, payload=None, timeout=120):
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(BASE + path, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        value = json.load(response)
    if path != "/openapi.json" and value.get("ok") is not True:
        raise RuntimeError("MARLIN refused " + path + ": " + json.dumps(value))
    return value


def gpu():
    command = ["nvidia-smi", "--query-gpu=memory.used,memory.free", "--format=csv,noheader,nounits"]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    record = {"time": now(), "command": command, "returncode": result.returncode,
              "stdout": result.stdout, "stderr": result.stderr}
    if result.returncode == 0:
        used, free = map(int, result.stdout.strip().split(","))
        record.update(used_mib=used, free_mib=free, minimum_capture_free_mib=768)
    return record


def alive(pid):
    try:
        status = Path(f"/proc/{pid}/stat").read_text()
        return status.rsplit(")", 1)[1].split()[0] != "Z"
    except FileNotFoundError:
        return False


def api_ready():
    try:
        value = request("/openapi.json", timeout=2)
        return "/integration/gama/v2/actor/dataset-capture" in value["paths"]
    except Exception:
        return False


def stop_launch(report):
    checkpoint = json.loads(CHECKPOINT.read_text())
    proof = json.loads((CHECKPOINT.parent / "checkpoint_verification_result.json").read_text())
    if not checkpoint["passed"] or not proof["passed"]:
        raise RuntimeError("A verified visual checkpoint is required")
    for row in checkpoint["verified_copies"]:
        for key in ("source", "copy"):
            path = Path(row[key])
            if FORBIDDEN.intersection(path.parts) or not path.is_relative_to(ROOT):
                raise ValueError("Unexpected checkpoint dependency")
            if live.digest(path) != row["sha256"]:
                raise ValueError("Checkpoint bytes changed")
    report["checkpoint_id"] = checkpoint["checkpoint_response"]["checkpoint_id"]
    report["before"] = request("/integration/gama/marine/audit")
    live.require_demo(report["before"])
    report["actor_before"] = request("/integration/gama/v2/actor/status")
    actor = report["actor_before"]
    if actor["owned"] or actor["actor_count"] or actor["root_present_on_active_stage"]:
        raise RuntimeError("An actor is still owned; restart refused")
    proc = Path(f"/proc/{OLD_PID}")
    if proc.stat().st_uid != os.getuid():
        raise RuntimeError("The observed Kit process has a different owner")
    argv = [part.decode() for part in (proc / "cmdline").read_bytes().split(b"\0") if part]
    expected = ["./kit/kit", "./apps/cris.madil.kit", "--enable", "cris.madil.render_service",
                "--ext-folder", str(ROOT / "source/extensions"), "--enable", "cris.madil.gama_bridge"]
    if argv != expected:
        raise RuntimeError("Kit process identity changed; restart refused")
    report["old_process"] = {"pid": OLD_PID, "argv": argv, "uid": os.getuid()}
    # /proc metadata only: never open files in the generated runtime directory.
    cwd = os.readlink(proc / "cwd")
    expected_cwd = str(ROOT / "_build/linux-x86_64/release")
    if cwd != expected_cwd:
        raise RuntimeError("Unexpected Kit working directory")
    selected = {"DISPLAY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS",
                "XAUTHORITY", "PATH", "LD_LIBRARY_PATH", "VK_ICD_FILENAMES",
                "__GLX_VENDOR_LIBRARY_NAME", "QT_QPA_PLATFORM"}
    inherited = {}
    for entry in (proc / "environ").read_bytes().split(b"\0"):
        if b"=" in entry:
            key, value = entry.split(b"=", 1)
            name = key.decode()
            if name in selected:
                inherited[name] = value.decode()
    report["inherited_environment_keys"] = sorted(inherited)
    report["gpu_before_shutdown"] = gpu()
    report["signal"] = {"pid": OLD_PID, "signal": "SIGINT", "sent_at": now()}
    print("Sending SIGINT to the confirmed MARLIN Kit process.", flush=True)
    os.kill(OLD_PID, signal.SIGINT)
    deadline = time.monotonic() + 45
    while alive(OLD_PID) and time.monotonic() < deadline:
        time.sleep(1)
    if alive(OLD_PID):
        raise RuntimeError("Kit did not exit after SIGINT; no force kill or duplicate launch attempted")
    report["old_process_exited_at"] = now()
    if api_ready():
        raise RuntimeError("A MARLIN API is still listening; duplicate launch refused")
    report["gpu_after_shutdown"] = gpu()
    command = ["./cris.madil.kit.sh", "--enable", "cris.madil.render_service",
               "--ext-folder", str(ROOT / "source/extensions"), "--enable", "cris.madil.gama_bridge"]
    environment = dict(os.environ)
    environment.update(inherited)
    with (OUTPUT / "kit_process.log").open("xb") as log:
        process = subprocess.Popen(command, cwd=cwd, env=environment,
                                   stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True, close_fds=True)
    report["launch"] = {"argv": command, "cwd": cwd, "launcher_pid": process.pid, "started_at": now()}
    write("launch_record.json", report["launch"])
    print("Old Kit exited. The replacement Kit is starting.", flush=True)
    deadline = time.monotonic() + 300
    previous_notice = time.monotonic()
    while not api_ready():
        if process.poll() is not None:
            raise RuntimeError(f"Kit launcher exited with {process.returncode}; inspect retained launch log")
        if time.monotonic() >= deadline:
            raise RuntimeError("Kit API not ready after 300 seconds; process left running for diagnosis")
        if time.monotonic() - previous_notice >= 20:
            print("Waiting for Kit services to finish starting.", flush=True)
            previous_notice = time.monotonic()
        time.sleep(2)
    report["api_ready_at"] = now()
    report["gpu_after_launch_empty_stage"] = gpu()
    print("Replacement Kit API is ready.", flush=True)


def restore(report):
    payloads = json.loads((OUTPUT / "recovery_payloads.json").read_text())
    if payloads.get("passed") is not True:
        raise RuntimeError("Verified recovery payloads are required")
    checkpoint = json.loads(CHECKPOINT.read_text())
    saved = checkpoint["before"]
    report["actor_before_restore"] = request("/integration/gama/v2/actor/status")
    if report["actor_before_restore"]["owned"]:
        raise RuntimeError("Actor ownership prevents scene recovery")
    checkpoint_id = checkpoint["checkpoint_response"]["checkpoint_id"]
    report["checkpoint_restore"] = request(f"/debug/scene/checkpoint/{checkpoint_id}/restore", {})
    report["restored_visual_audit"] = request("/integration/gama/marine/audit")
    report["respawn_results"] = []
    for payload in payloads["animals"]:
        report["respawn_results"].append(request("/scene/cetacean/spawn", payload))
    report["ocean_start"] = request("/scene/ocean/animation/start", payloads["ocean"])
    report["gallery_start"] = request("/scene/cetaceans/gallery/swim/start", payloads["gallery"])
    report["after_before_delay"] = request("/integration/gama/marine/audit")
    time.sleep(3)
    report["after"] = request("/integration/gama/marine/audit")
    checks = live.coexistence(report["after_before_delay"], report["after"])
    checks.update(saved_renderer_settings_restored=live.settings_equal(saved["renderer_settings"], report["after"]["renderer_settings"]),
                  saved_stable_scene_attributes_restored=saved["stable_scene_attributes"] == report["after"]["stable_scene_attributes"],
                  saved_camera_restored=saved["inspection"]["camera"] == report["after"]["inspection"]["camera"],
                  saved_controller_configuration_restored=live.controller_configuration(saved) == live.controller_configuration(report["after"]),
                  saved_ocean_configuration_restored={k:v for k,v in saved["ocean"].items() if k != "elapsed"} == {k:v for k,v in report["after"]["ocean"].items() if k != "elapsed"})
    report["actor_after"] = request("/integration/gama/v2/actor/status")
    checks["actor_unowned_and_private_root_absent"] = (not report["actor_after"]["owned"] and report["actor_after"]["actor_count"] == 0 and not report["actor_after"]["root_present_on_active_stage"])
    report["checks"] = checks
    report["gpu_after_scene_recovery"] = gpu()
    if not all(checks.values()):
        raise RuntimeError("Recovered scene checks failed: " + ", ".join(k for k,v in checks.items() if not v))
    print("Scene and all eleven swimming controllers recovered; phases restarted.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("stop-launch", "restore"))
    args = parser.parse_args()
    name = args.phase.replace("-", "_") + "_result.json"
    if (OUTPUT / name).exists():
        raise RuntimeError("Existing restart evidence cannot be overwritten")
    report = {"kind": "authorized_kit_restart", "phase": args.phase, "passed": False,
              "started_at": now(), "desktop_restarted": False, "gpu_guard_changed": False,
              "controller_animation_phase_preserved": False, "capture_requested": False,
              "authorization": "Why don't you do it? (following the Kit-first restart explanation)"}
    try:
        (stop_launch if args.phase == "stop-launch" else restore)(report)
        report["passed"] = True
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    finally:
        report["finished_at"] = now()
        write(name, report)
    print(json.dumps({"passed": report["passed"], "result": str(OUTPUT/name),
                      "error": report.get("error")}), flush=True)
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
