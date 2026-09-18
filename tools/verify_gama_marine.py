"""Exercise the owned GAMA actor alongside an already-running marine scene."""
import argparse
import json
from pathlib import Path
import time
from gama_trajectory import call, exchange


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8011")
    parser.add_argument("--trajectory", type=Path, default=Path("artifacts/gama/trajectory_validation.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Choose an unused output path")
    steps = json.loads(args.trajectory.read_text())["snapshots"]
    for step in steps:
        exchange.validate_step(step)
    def audit():
        return call(args.url, "/integration/gama/marine/audit")
    before = audit()
    if not before["swimming"]["running"] or before["swimming"]["animal_count"] != 11 or not before["ocean"]["running"]:
        raise ValueError("Start the eleven gallery swimmers and ocean first")
    report = {"before": before, "steps_verified": 0}
    acquired = call(args.url, "/integration/gama/actor/acquire", {})
    token = acquired["ownership_token"]
    try:
        for step in steps:
            call(args.url, "/integration/gama/actor/step", {"ownership_token": token, "step": step})
            status = call(args.url, "/integration/gama/actor/status")
            expected = exchange.preview_transforms(step, acquired["meters_per_scene_unit"])[0]
            for key in ("position_scene_units", "forward_y_up"):
                if any(abs(a-b) > 1e-5 for a,b in zip(expected[key],status["world_pose"][key])):
                    raise ValueError("USD pose mismatch")
            report["steps_verified"] += 1
            time.sleep(.15)
        report["during"] = audit()
        report["capture"] = call(args.url, "/integration/gama/actor/capture", {"ownership_token": token})
        report["after_capture"] = audit()
    finally:
        report["release"] = call(args.url, "/integration/gama/actor/release", {"ownership_token": token})
        time.sleep(2)
        report["after_release"] = audit()
        report["actor_after_release"] = call(args.url, "/integration/gama/actor/status")
        checks = {}
        for label in ("during", "after_capture", "after_release"):
            if label not in report:
                continue
            current = report[label]
            checks[label] = {
                "settings_unchanged": current["renderer_settings"] == before["renderer_settings"],
                "camera_lighting_materials_unchanged": current["stable_scene_attributes"] == before["stable_scene_attributes"],
                "overview_camera_unchanged": current["inspection"]["camera"] == before["inspection"]["camera"],
                "eleven_swimmers_running": current["swimming"]["running"] and current["swimming"]["animal_count"] == 11,
                "swimmers_moved": all((a["x"],a["z"]) != (b["x"],b["z"]) for a,b in zip(before["swimming"]["animals"], current["swimming"]["animals"])),
                "no_deformation_errors": all(not a.get("deformation_error") for a in current["swimming"]["animals"]),
                "ocean_advanced": current["ocean"]["running"] and current["ocean"]["elapsed"] > before["ocean"]["elapsed"],
                "ocean_config_unchanged": {k:v for k,v in current["ocean"].items() if k != "elapsed"} == {k:v for k,v in before["ocean"].items() if k != "elapsed"},
            }
        report["checks"] = checks
        report["layers_restored"] = report["after_release"]["inspection"]["layers"] == before["inspection"]["layers"]
        report["passed"] = (len(checks)==3 and all(all(c.values()) for c in checks.values()) and
                            report["layers_restored"] and not report["actor_after_release"]["owned"])
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k in ("capture", "checks", "layers_restored", "passed", "steps_verified")}, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
