"""M4 actual Kit acceptance: cardinal fixtures, retained GAMA replay and coexistence."""
import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import shutil
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
TRAJECTORY = ROOT / "experiments/gama_marlin_v1/trajectories/m3_seed_184729_a/trajectory.json"
POSITION_TOLERANCE_M = 1e-5
HEADING_TOLERANCE_DEG = 1e-4
BASE = "/integration/gama/v2/actor"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8011")
    parser.add_argument("--prepare-demo", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    def request(path, payload=None, expect_ok=True):
        data = None if payload is None else json.dumps(payload).encode()
        req = urllib.request.Request(args.url + path, data=data, headers={"Content-Type": "application/json"})
        # Each call opens a fresh HTTP connection; ownership is independent of it.
        with urllib.request.urlopen(req, timeout=180) as response:
            result = json.load(response)
        if expect_ok and not result.get("ok"):
            raise ValueError(f"{path}: {result}")
        return result
    def audit():
        return request("/integration/gama/marine/audit")
    def controller_configuration(record):
        varying = {"z", "direction", "heading", "model_yaw"}
        return {animal["name"]: {k:v for k,v in animal.items() if k not in varying}
                for animal in record["swimming"]["animals"]}
    report = {"milestone": 4, "passed": False,
              "declared_tolerances": {"position_euclidean_m": POSITION_TOLERANCE_M, "heading_circular_deg": HEADING_TOLERANCE_DEG},
              "trajectory": str(TRAJECTORY.relative_to(ROOT)),
              "trajectory_sha256": hashlib.sha256(TRAJECTORY.read_bytes()).hexdigest(),
              "cardinal_fixtures": [], "actual_gama_transforms": [], "failure_checks": {}, "captures": []}
    token = None
    try:
        initial = audit()
        if args.prepare_demo and not initial["swimming"]["running"] and initial["swimming"]["animal_count"] == 0 and not initial["ocean"]["running"]:
            report["demo_setup"] = [request("/scene/demonstration/environment", {}),
                request("/scene/cetaceans/gallery", {"elevation": 0, "activate_viewport_camera": False}),
                request("/scene/cetaceans/gallery/swim/start", {"depth": -150, "speed": 30, "travel_half_extent": 6500, "activate_viewport_camera": True, "deformation_fps": 15})]
        before = report["before"] = audit()
        assert before["swimming"]["running"] and before["swimming"]["animal_count"] == 11 and before["ocean"]["running"], "An animated eleven-animal demo is required"
        assert not request(BASE + "/status")["owned"], "Refusing to take over an existing v2 owner"
        steps = json.loads(TRAJECTORY.read_text())
        acquired = request(BASE + "/acquire", {"agent_id": steps[0]["agents"][0]["agent_id"]})
        token = acquired["ownership_token"]
        report["acquired"] = {k:v for k,v in acquired.items() if k != "ownership_token"}
        units = acquired["meters_per_scene_unit"]
        def status():
            return request(BASE + "/status")
        def apply(step):
            return request(BASE + "/step", {"ownership_token": token, "step": step})
        def compare(step, current):
            animal = step["agents"][0]
            actual = [v * units for v in current["world_pose"]["position_scene_units"]]
            expected = [animal["horizontal_position_m"][0], -animal["depth_m"], animal["horizontal_position_m"][1]]
            position_error = math.dist(actual, expected)
            forward = current["world_pose"]["forward_y_up"]
            heading = math.degrees(math.atan2(forward[0], forward[2])) % 360
            heading_error = abs((heading - animal["heading_deg"] + 180) % 360 - 180)
            assert position_error <= POSITION_TOLERANCE_M and heading_error <= HEADING_TOLERANCE_DEG
            assert current["actor_count"] == 1 and current["autonomous_controller"] is False
            return {"step_index": step["step_index"], "state": animal["behavioural_state"], "expected_position_m": expected,
                    "composed_position_m": actual, "expected_heading_deg": animal["heading_deg"],
                    "composed_heading_deg": heading, "position_error_m": position_error, "heading_error_deg": heading_error}
        for i, heading in enumerate((0, 90, 180, 270)):
            fixture = deepcopy(steps[0])
            fixture.update(run_id="M4_Cardinal_Fixture", step_index=i, simulation_time_s=i*.5)
            fixture["agents"][0].update(horizontal_position_m=[12.345, -6.789], depth_m=1.35, heading_deg=heading)
            apply(fixture)
            report["cardinal_fixtures"].append(compare(fixture, status()))
        duplicate_before = status()
        duplicate = apply(fixture)
        duplicate_after = status()
        assert duplicate["duplicate"] and duplicate_before["world_pose"] == duplicate_after["world_pose"] and duplicate_before["accepted_steps"] == duplicate_after["accepted_steps"] == 4
        report["failure_checks"]["duplicate_no_advance_one_animal"] = duplicate_after["actor_count"] == 1
        cases = {"out_of_order": deepcopy(fixture), "unknown_agent": deepcopy(fixture), "malformed": deepcopy(fixture)}
        cases["out_of_order"].update(step_index=2, simulation_time_s=1)
        cases["unknown_agent"]["agents"][0]["agent_id"] = "Unknown"
        cases["malformed"]["agents"][0]["position_m"] = [0,0,0]
        for name, invalid in cases.items():
            result = request(BASE + "/step", {"ownership_token": token, "step": invalid}, False)
            current = status()
            assert not result["ok"] and current["world_pose"] == duplicate_after["world_pose"] and current["accepted_steps"] == 4
            report["failure_checks"][name + "_atomic_rejection"] = True
        assert not request(BASE + "/step", {"ownership_token": "wrong", "step": fixture}, False)["ok"]
        assert not request(BASE + "/acquire", {"agent_id": "Another"}, False)["ok"]
        report["failure_checks"]["wrong_token_and_double_acquire_rejected"] = True
        request(BASE + "/reset", {"ownership_token": token})
        reset = status()
        assert reset["world_pose"] == duplicate_after["world_pose"] and reset["accepted_steps"] == 0 and reset["transport_state"] == "awaiting_first_update"
        report["failure_checks"]["reset_holds_pose_and_ownership"] = True
        # The original M2 reset remains validation-only, independent of this owner.
        request("/integration/gama/v2/reset", {})
        assert status()["owned"] and status()["world_pose"] == reset["world_pose"]
        report["failure_checks"]["validation_reset_does_not_release_actor"] = True
        for index, step in enumerate(steps):
            apply(step)
            current = status()
            report["actual_gama_transforms"].append(compare(step, current))
            if index == 10:
                held = current
                time.sleep(3)
                frozen = status()
                assert frozen["transport_state"] == "frozen_updates_missing" and frozen["world_pose"] == held["world_pose"] and frozen["accepted_steps"] == held["accepted_steps"]
                retried = apply(step)
                recovered = status()
                assert retried["duplicate"] and recovered["transport_state"] == "holding_last_state" and recovered["accepted_steps"] == held["accepted_steps"] and recovered["world_pose"] == held["world_pose"]
                report["failure_checks"]["interruption_freeze_and_fresh_http_reconnect"] = True
                report["interruption_status"] = frozen
            if index in (0, 8, 16, 24, 32, 40):
                capture = request(BASE + "/capture", {"ownership_token": token})
                assert capture["render_product_camera_verified"]
                assert all(capture[key]["render_product"]["camera"] == "/MarlinGamaPorpoise/DiagnosticCamera"
                           for key in ("projection_before_capture", "projection_after_capture"))
                assert capture["previous_camera_restored"] and capture["owned_layer_restored"] and capture["controller_gate_restored"]
                assert capture["world_pose"] == current["world_pose"] and status()["world_pose"] == current["world_pose"]
                name = f"frame_{index:03d}_{step['agents'][0]['behavioural_state']}.png"
                shutil.copyfile(capture["file_path"], args.output / name)
                capture["retained_frame"] = name
                report["captures"].append(capture)
        assert status()["accepted_steps"] == len(steps) == 41
        report["during"] = audit()
    except Exception as error:
        report["error"] = str(error)
        raise
    finally:
        try:
            if token is not None:
                report["release"] = request(BASE + "/release", {"ownership_token": token})
                time.sleep(2)
                report["after_release"] = audit()
                report["actor_after_release"] = request(BASE + "/status")
            if "before" in report and "after_release" in report and "during" in report:
                before = report["before"]
                checks = {}
                for label in ("during", "after_release"):
                    current = report[label]
                    checks[label] = {
                        "renderer_unchanged": current["renderer_settings"] == before["renderer_settings"],
                        "stable_scene_unchanged": current["stable_scene_attributes"] == before["stable_scene_attributes"],
                        "camera_unchanged": current["inspection"]["camera"] == before["inspection"]["camera"],
                        "eleven_swimmers_retained": current["swimming"]["running"] and current["swimming"]["animal_count"] == 11,
                        "original_controller_configuration_retained": controller_configuration(current) == controller_configuration(before),
                        "all_original_swimmers_moved": all((a["x"],a["z"]) != (b["x"],b["z"]) for a,b in zip(before["swimming"]["animals"], current["swimming"]["animals"])),
                        "no_deformation_errors": all(not a.get("deformation_error") for a in current["swimming"]["animals"]),
                        "ocean_advanced": current["ocean"]["running"] and current["ocean"]["elapsed"] > before["ocean"]["elapsed"],
                        "ocean_config_unchanged": {k:v for k,v in current["ocean"].items() if k != "elapsed"} == {k:v for k,v in before["ocean"].items() if k != "elapsed"}}
                report["coexistence_checks"] = checks
                report["layers_restored"] = report["after_release"]["inspection"]["layers"] == before["inspection"]["layers"]
                rows = report["cardinal_fixtures"] + report["actual_gama_transforms"]
                report["maximum_position_error_m"] = max(r["position_error_m"] for r in rows)
                report["maximum_heading_error_deg"] = max(r["heading_error_deg"] for r in rows)
                report["passed"] = (not report.get("error") and len(report["captures"]) == 6 and len(report["actual_gama_transforms"]) == 41
                    and all(all(c.values()) for c in checks.values()) and all(report["failure_checks"].values())
                    and report["layers_restored"] and not report["actor_after_release"]["owned"]
                    and report["actor_after_release"]["actor_count"] == 0
                    and not report["actor_after_release"]["root_present_on_active_stage"])
        except Exception as cleanup_error:
            report["cleanup_error"] = str(cleanup_error)
            report["passed"] = False
        finally:
            (args.output / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k:report[k] for k in ("passed", "maximum_position_error_m", "maximum_heading_error_deg", "failure_checks", "coexistence_checks", "layers_restored", "error", "cleanup_error") if k in report}, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
