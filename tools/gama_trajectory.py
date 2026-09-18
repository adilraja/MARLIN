"""Convert/compare GAMA fixture outputs, optionally replay into one owned actor.

Only --replay acquires and changes a MARLIN actor. It releases it in finally.
"""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import time
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("exchange", ROOT / "source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge/exchange.py")
exchange = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exchange)


def read_trajectory(path):
    steps = []
    buffer = exchange.StepBuffer()
    for entry in ET.parse(path).getroot().findall("Step"):
        values = {v.attrib["name"]: float(v.text) for v in entry.findall("Variable")}
        x, y, z = (values[k] for k in ("x_m", "y_m", "z_m"))
        snapshot = exchange.validate_step({"schema_version": "1.0", "time_s": values["time_s"],
            "seed": 184729, "agents": [{"id": "Gama_Bottlenose_001", "species": "bottlenose_dolphin",
                "state": "shallow_swim", "position_m": [x, y, z],
                "heading_deg": values["heading_deg"], "speed_mps": values["speed_mps"],
                "depth_m": max(0, -y)}]})
        # Independent engineering checks, not biological acceptance criteria.
        if not math.isclose(math.hypot(x, z), 12, abs_tol=1e-8):
            raise ValueError("GAMA fixture left its 12 m test circle")
        tangent = math.degrees(math.atan2(z, -x)) % 360
        error = (values["heading_deg"] - tangent + 180) % 360 - 180
        if abs(error) > 1e-8:
            raise ValueError("GAMA heading is not tangent in MARLIN's convention")
        if not math.isclose(values["speed_mps"], 12 * math.radians(3), abs_tol=1e-10):
            raise ValueError("Unexpected GAMA fixture speed")
        buffer.accept(snapshot)
        steps.append(snapshot)
    if len(steps) != 20 or [s["time_s"] for s in steps] != list(range(20)):
        raise ValueError("Expected all 20 GAMA steps at times 0..19 seconds")
    return steps


def call(base, path, payload=None):
    request = Request(base.rstrip("/") + path,
                      data=json.dumps(payload).encode() if payload is not None else None,
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=180) as response:
        result = json.load(response)
    if not result.get("ok"):
        raise RuntimeError(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--url", default="http://localhost:8011")
    args = parser.parse_args()
    first, second = read_trajectory(args.first), read_trajectory(args.second)
    if first != second:
        raise ValueError("Repeated GAMA outputs differ")
    encoded = json.dumps(first, sort_keys=True, separators=(",", ":"))
    report = {"deterministic": True, "steps": len(first), "seed": 184729,
              "trajectory_sha256": hashlib.sha256(encoded.encode()).hexdigest(),
              "source_files": [str(args.first.resolve()), str(args.second.resolve())],
              "biological_validation": False, "replayed": False, "snapshots": first}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise ValueError("Output already exists; choose a new report path")
    if args.replay:
        before = call(args.url, "/debug/scene/inspection")
        acquired = call(args.url, "/integration/gama/actor/acquire", {})
        token = acquired["ownership_token"]
        report["replay_results"] = []
        try:
            for step in first:
                result = call(args.url, "/integration/gama/actor/step", {"ownership_token": token, "step": step})
                status = call(args.url, "/integration/gama/actor/status")
                expected = exchange.preview_transforms(step, acquired["meters_per_scene_unit"])[0]
                for key in ("position_scene_units", "forward_y_up"):
                    if any(abs(a-b) > 1e-5 for a, b in zip(status["world_pose"][key], expected[key])):
                        raise ValueError("Authored USD world pose differs from GAMA state")
                result["world_pose_verified"] = True
                report["replay_results"].append(result)
                time.sleep(1)  # Display pacing only; authoritative time remains GAMA's.
            held = call(args.url, "/integration/gama/actor/status")["world_pose"]
            time.sleep(2)
            report["holds_without_updates"] = held == call(args.url, "/integration/gama/actor/status")["world_pose"]
            if not report["holds_without_updates"]:
                raise ValueError("Actor moved without an external step")
            report["replayed"] = True
        finally:
            report["release"] = call(args.url, "/integration/gama/actor/release", {"ownership_token": token})
        report["scene_inspection_unchanged_after_release"] = before == call(args.url, "/debug/scene/inspection")
        if not report["scene_inspection_unchanged_after_release"]:
            raise ValueError("Scene inspection differs after release")
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("snapshots", "replay_results")}, indent=2))


if __name__ == "__main__":
    main()
