"""Save a verified visual checkpoint and controller records; never restart Kit."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tools"))
import verify_gama_paired_live as live

OUTPUT = Path(__file__).resolve().parent


def request(path, payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request("http://localhost:8011" + path, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as response:
        value = json.load(response)
    if value.get("ok") is not True:
        raise ValueError("MARLIN refused the fixed checkpoint/audit operation: " + path)
    return value


def sha(path):
    h = hashlib.sha256()
    with live.safe_path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    result_path = OUTPUT / "checkpoint_result.json"
    if result_path.exists():
        raise ValueError("Existing checkpoint evidence cannot be overwritten")
    report = {"kind": "memory_cleanup_recovery_preparation", "passed": False,
              "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "kit_restarted": False, "desktop_restarted": False,
              "render_requested": False, "live_stage_replaced": False,
              "controller_phase_serialized": False}
    try:
        report["before"] = request("/integration/gama/marine/audit")
        live.require_demo(report["before"])
        report["actor_status"] = request("/integration/gama/v2/actor/status")
        if report["actor_status"]["owned"] or report["actor_status"]["root_present_on_active_stage"]:
            raise ValueError("An actor owner or private root is present")
        checkpoint = report["checkpoint_response"] = request("/debug/scene/checkpoint", {})
        source = live.safe_path(checkpoint["directory"])
        if not source.is_relative_to(ROOT / "artifacts"):
            raise ValueError("Unexpected checkpoint source location")
        target = OUTPUT / "checkpoint_snapshot"
        target.mkdir(exist_ok=False)
        copies = []
        for filename in ("scene.usdc", "metadata.json"):
            original = live.safe_path(source / filename)
            expected = sha(original)
            shutil.copyfile(original, target / filename)
            actual = sha(target / filename)
            if actual != expected or sha(original) != expected:
                raise ValueError("Checkpoint source or byte-identical copy changed")
            copies.append({"source": str(original), "copy": str(target / filename),
                           "sha256": actual, "bytes": (target / filename).stat().st_size})
        if sha(target / "scene.usdc") != checkpoint["scene_sha256"]:
            raise ValueError("Checkpoint scene hash differs from the live API record")
        report["verified_copies"] = copies
        report["limitations"] = checkpoint["limitations"]
        time.sleep(2)
        report["after"] = request("/integration/gama/marine/audit")
        report["checks"] = live.coexistence(report["before"], report["after"])
        report["checks"]["layers_unchanged"] = report["before"]["inspection"]["layers"] == report["after"]["inspection"]["layers"]
        report["passed"] = all(report["checks"].values())
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    finally:
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        with result_path.open("x") as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write("\n")
    print(json.dumps({"passed": report["passed"], "result": str(result_path),
                      "checkpoint_id": report.get("checkpoint_response", {}).get("checkpoint_id"),
                      "limitations": report.get("limitations"), "error": report.get("error")}))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
