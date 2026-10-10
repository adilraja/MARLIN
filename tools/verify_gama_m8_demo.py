"""Read-only Milestone 8 check of the already running marine demonstration."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlparse
import urllib.request

import verify_gama_paired_live as live


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8011")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    address = urlparse(args.url)
    if (address.scheme != "http" or address.hostname not in ("localhost", "127.0.0.1", "::1")
            or address.username or address.password or address.query or address.fragment
            or address.path not in ("", "/")):
        parser.error("Use an HTTP loopback MARLIN base URL without credentials or paths")
    output = live.safe_path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    sources = [Path(__file__).resolve(), Path(live.__file__).resolve(),
               live.ROOT / "tools/gama_porpoise.py",
               live.ROOT / "source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge/marine_check.py"]
    pins = [{"path": str(path.relative_to(live.ROOT)), "sha256": live.digest(path)} for path in sources]
    report = {"kind": "m8_read_only_live_demo_check", "milestone": 8, "passed": False,
              "started_at_utc": now(), "command": [sys.executable, *sys.argv],
              "http_requests": [], "scene_mutation_attempted": False,
              "captures_requested": 0, "kit_restart_requested": False,
              "biological_approval": False, "source_pins_before": pins}

    def request(path):
        item = {"method": "GET", "path": path, "started_at_utc": now()}
        report["http_requests"].append(item)
        with urllib.request.urlopen(args.url.rstrip("/") + path, timeout=30) as response:
            item["http_status_code"] = response.status
            value = json.load(response)
        item["finished_at_utc"] = now()
        if not isinstance(value, dict) or (path != "/openapi.json" and value.get("ok") is not True):
            raise ValueError("Read-only endpoint did not return a successful object: " + path)
        return value

    try:
        report["before"] = request("/integration/gama/marine/audit")
        report["actor_before"] = request("/integration/gama/v2/actor/status")
        live.require_demo(report["before"])
        time.sleep(2)
        report["after"] = request("/integration/gama/marine/audit")
        report["actor_after"] = request("/integration/gama/v2/actor/status")
        live.require_demo(report["after"])
        checks = live.coexistence(report["before"], report["after"])
        checks["layers_unchanged"] = report["before"]["inspection"]["layers"] == report["after"]["inspection"]["layers"]
        for when in ("before", "after"):
            status = report["actor_" + when]
            checks["no_owned_actor_" + when] = status["owned"] is False and status["actor_count"] == 0
            checks["no_private_root_" + when] = status["root_present_on_active_stage"] is False
        report["checks"] = checks
        report["openapi"] = request("/openapi.json")
        routes = {path: path in report["openapi"]["paths"] for path in (
            "/scene/marine/setup", "/scene/cetaceans/gallery",
            "/integration/gama/v2/actor/paired-capture", "/integration/gama/v2/actor/dataset-capture")}
        report["route_presence_checks"] = routes
        gpu = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.free", "--format=csv,noheader,nounits"],
                             text=True, capture_output=True, timeout=30)
        report["gpu_observation"] = {"recorded_at_utc": now(), "command": gpu.args,
            "return_code": gpu.returncode, "stdout": gpu.stdout, "stderr": gpu.stderr,
            "minimum_free_mib_before_render": 768, "gpu_headroom_is_not_a_read_only_demo_check": True}
        if gpu.returncode == 0:
            values = gpu.stdout.strip().splitlines()
            if len(values) == 1:
                used, free = map(int, values[0].split(","))
                report["gpu_observation"].update(used_mib=used, free_mib=free,
                    below_capture_minimum=free < 768)
        report["passed"] = all(checks.values()) and all(routes.values())
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    finally:
        after = [{"path": str(path.relative_to(live.ROOT)), "sha256": live.digest(path)} for path in sources]
        report["source_pins_after"] = after
        report["source_pins_unchanged"] = pins == after
        report["passed"] = report["passed"] and report["source_pins_unchanged"]
        report["finished_at_utc"] = now()
        live.write_json(output / "results.json", report)
    print(json.dumps({"passed": report["passed"], "results": str(output / "results.json"),
                      "checks": report.get("checks"), "gpu": report.get("gpu_observation"),
                      "error": report.get("error")}), flush=True)
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
