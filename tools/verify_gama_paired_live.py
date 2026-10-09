"""M6 live acceptance using one declared, sealed actual GAMA snapshot.

Run only against an already running eleven-animal MARLIN demonstration. The
client does not launch Kit, prepare a scene, change source assets or generate
substitute states. Each output directory is exclusive; failed evidence remains.
--preflight-only performs two marine audits and one actor-status read without
acquiring an actor, making a checkpoint or capturing an image.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import time
from urllib.parse import urlparse
import urllib.request

import gama_porpoise as recorder

ROOT = Path(__file__).resolve().parents[1]
SPRINT = ROOT / "experiments/gama_marlin_v1"
M5_MANIFEST = SPRINT / "qa/milestone_5_manifest.json"
TRAJECTORY = SPRINT / "trajectories/m5_positive_seed_184729_a/trajectory.json"
BASE = "/integration/gama/v2/actor"
SELECTED_STEP = 8
ORDERS = [[0.5, 1.0, 2.0, 3.0, 4.0], [4.0, 3.0, 2.0, 1.0, 0.5]]
DELAY_S = 2.0
POSITION_TOLERANCE_M = 1e-5
HEADING_TOLERANCE_DEG = 1e-4
FORBIDDEN_PARTS = frozenset(("_build", "extscache", "__pycache__", ".cache"))
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def safe_path(path):
    """Refuse generated inputs before accessing their contents."""
    path = Path(path)
    if FORBIDDEN_PARTS.intersection(path.parts) or path.suffix == ".pyc":
        raise ValueError("Generated-directory inputs are prohibited")
    resolved = path.resolve()
    if FORBIDDEN_PARTS.intersection(resolved.parts) or resolved.suffix == ".pyc":
        raise ValueError("A path resolves into a prohibited generated directory")
    return resolved


def write_json(path, value):
    with path.open("x") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


def redact(value, token=None):
    """Ownership credentials belong only in memory and outgoing requests."""
    if isinstance(value, dict):
        return {key: redact(item, token) for key, item in value.items()
                if key.lower() not in ("ownership_token", "token")}
    if isinstance(value, (list, tuple)):
        return [redact(item, token) for item in value]
    if isinstance(value, str) and token:
        return value.replace(token, "[ownership credential redacted]")
    return value


def load_m5_seal():
    seal = json.loads(M5_MANIFEST.read_text())
    if seal.get("status") != "complete" or not seal.get("passed") or not seal.get("human_review_completed"):
        raise ValueError("The completed M5 manifest and human review are required")
    rows = seal.get("outputs")
    if not isinstance(rows, list) or not rows:
        raise ValueError("The M5 manifest has no protected outputs")
    return {"manifest_sha256": digest(M5_MANIFEST), "outputs": rows}


def verify_m5_seal(seal):
    changes = []
    for row in seal["outputs"]:
        path = safe_path(ROOT / row["path"])
        if not path.is_relative_to(ROOT):
            raise ValueError("A protected M5 output is outside the repository")
        if not path.is_file():
            changes.append({"path": row["path"], "error": "missing file"})
        elif path.stat().st_size != row["bytes"] or digest(path) != row["sha256"]:
            changes.append({"path": row["path"], "error": "size or SHA-256 changed"})
    if digest(M5_MANIFEST) != seal["manifest_sha256"]:
        changes.append({"path": str(M5_MANIFEST.relative_to(ROOT)), "error": "manifest changed"})
    return {"passed": not changes, "protected_outputs_checked": len(seal["outputs"]),
            "manifest": str(M5_MANIFEST.relative_to(ROOT)),
            "manifest_sha256": seal["manifest_sha256"], "changes": changes}


def verified_trajectory():
    """Reparse retained raw GAMA output; never repair or manufacture a state."""
    directory = TRAJECTORY.parent
    execution = json.loads((directory / "execution.json").read_text())
    retained_config = json.loads((directory / "configuration.json").read_text())
    config = retained_config["configuration"]
    if execution.get("status") != "passed" or execution.get("actual_seed") != 184729:
        raise ValueError("Expected the accepted actual M5 seed-184729 execution")
    raw = directory / "raw/simulation-outputs0.xml"
    states, validation = recorder.read_trajectory(raw, config, execution["run_id"], 184729)
    if states != json.loads(TRAJECTORY.read_text()):
        raise ValueError("Retained trajectory differs from reparsed actual GAMA output")
    canonical = hashlib.sha256(recorder.canonical_states(states)).hexdigest()
    if canonical != execution["canonical_state_sha256"] or digest(raw) != execution["raw_xml_sha256"]:
        raise ValueError("Actual GAMA output hashes differ from the retained execution")
    selected = states[SELECTED_STEP]
    if (selected["step_index"] != SELECTED_STEP or selected["simulation_time_s"] != 4.0
            or selected["agents"][0]["behavioural_state"] != "shallow_swim"):
        raise ValueError("The predeclared step-8/t=4 shallow-swim snapshot changed")
    return states, {"path": str(TRAJECTORY.relative_to(ROOT)),
                    "sha256": digest(TRAJECTORY), "raw_xml_sha256": digest(raw),
                    "execution_sha256": digest(directory / "execution.json"),
                    "model_sha256": digest(directory / "model.gaml"),
                    "configuration_sha256": digest(directory / "configuration.json"),
                    "canonical_state_sha256": canonical,
                    "raw_gama_reparse_passed": validation["passed"],
                    "samples": len(states), "selected_state": selected}


def settings_equal(left, right):
    """Use MARLIN's declared float32 restoration tolerance; types stay strict."""
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(settings_equal(left[k], right[k]) for k in left)
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        return len(left) == len(right) and all(settings_equal(a, b) for a, b in zip(left, right))
    if type(left) in (int, float) and type(right) in (int, float):
        return math.isclose(left, right, rel_tol=1e-7, abs_tol=1e-9)
    return type(left) is type(right) and left == right


def controller_configuration(audit):
    varying = {"z", "direction", "heading", "model_yaw"}
    return {a["name"]: {k: v for k, v in a.items() if k not in varying}
            for a in audit["swimming"]["animals"]}


def coexistence(before, after):
    old = {a["name"]: a for a in before["swimming"]["animals"]}
    new = {a["name"]: a for a in after["swimming"]["animals"]}
    return {
        "eleven_original_swimmers_running": bool(after["swimming"]["running"])
            and after["swimming"]["animal_count"] == len(new) == 11 and old.keys() == new.keys(),
        "all_original_swimmers_advanced": old.keys() == new.keys()
            and all((old[k]["x"], old[k]["z"]) != (new[k]["x"], new[k]["z"]) for k in old),
        "controller_configuration_preserved": controller_configuration(before) == controller_configuration(after),
        "no_deformation_errors": all(not a.get("deformation_error") for a in new.values()),
        "ocean_advanced": bool(after["ocean"]["running"])
            and after["ocean"]["elapsed"] > before["ocean"]["elapsed"],
        "ocean_configuration_preserved": {k: v for k, v in before["ocean"].items() if k != "elapsed"}
            == {k: v for k, v in after["ocean"].items() if k != "elapsed"},
        "renderer_settings_preserved": settings_equal(before["renderer_settings"], after["renderer_settings"]),
        "stable_scene_attributes_preserved": before["stable_scene_attributes"] == after["stable_scene_attributes"],
        "original_camera_preserved": before["inspection"]["camera"] == after["inspection"]["camera"],
    }


def require_demo(audit):
    if (not audit["swimming"]["running"] or audit["swimming"]["animal_count"] != 11
            or len(audit["swimming"]["animals"]) != 11 or not audit["ocean"]["running"]):
        raise ValueError("An already running eleven-animal demonstration and ocean are required")


def compare_pose(state, status, units):
    agent = state["agents"][0]
    actual = [value * units for value in status["world_pose"]["position_scene_units"]]
    expected = [agent["horizontal_position_m"][0], -agent["depth_m"], agent["horizontal_position_m"][1]]
    forward = status["world_pose"]["forward_y_up"]
    heading = math.degrees(math.atan2(forward[0], forward[2])) % 360
    position_error = math.dist(expected, actual)
    heading_error = abs((heading - agent["heading_deg"] + 180) % 360 - 180)
    if (position_error > POSITION_TOLERANCE_M or heading_error > HEADING_TOLERANCE_DEG
            or status["actor_count"] != 1 or status["autonomous_controller"] is not False):
        raise ValueError("Actual composed porpoise pose or ownership differs from the selected GAMA state")
    return {"passed": True, "composed_position_m": actual, "expected_position_m": expected,
            "composed_heading_deg": heading, "expected_heading_deg": agent["heading_deg"],
            "position_error_m": position_error, "heading_error_deg": heading_error}


def copy_group(source, output):
    """Retain every regular group file; never traverse generated directories."""
    source = safe_path(source)
    if not source.is_dir() or source == ROOT or output.is_relative_to(source):
        raise ValueError("Unexpected capture-group directory")
    target = output / "group"
    target.mkdir(exist_ok=False)
    records = []
    for parent, directories, names in os.walk(source, followlinks=False):
        parent = Path(parent)
        if any(name in FORBIDDEN_PARTS for name in directories):
            raise ValueError("Capture-group directory contains a prohibited generated directory")
        for name in directories:
            if (parent / name).is_symlink():
                raise ValueError("Capture-group directory symlinks are unsupported")
        for name in sorted(names):
            path = parent / name
            if path.is_symlink() or not path.is_file():
                raise ValueError("Capture-group nonregular files are unsupported")
            safe_path(path)
            relative = path.relative_to(source)
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
            if digest(path) != digest(destination):
                raise ValueError("Retained capture-group copy differs from its source")
            records.append({"path": str(Path("group") / relative),
                            "bytes": destination.stat().st_size, "sha256": digest(destination)})
    if not records:
        raise ValueError("Capture group returned no files")
    return {"source_directory": str(source), "retained_directory": "group", "files": records}


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False, ensure_ascii=True).encode()).hexdigest()


def group_file(group, relative, expected_hash):
    """Verify a group-relative regular file without permitting path escapes."""
    relative = Path(relative)
    path = safe_path(group / relative)
    if relative.is_absolute() or not path.is_relative_to(group) or not path.is_file():
        raise ValueError("Invalid capture-group relative file")
    if not isinstance(expected_hash, str) or not SHA256.fullmatch(expected_hash) or digest(path) != expected_hash:
        raise ValueError("A retained capture-group file has a mismatched SHA-256")
    return path


def png_file(group, relative, expected_hash):
    path = group_file(group, relative, expected_hash)
    with path.open("rb") as stream:
        header = stream.read(24)
    if (len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n"
            or struct.unpack(">II", header[16:24]) != (1024, 768)):
        raise ValueError("A retained PNG has unexpected format or dimensions")
    return path


def validate_group(group, selected_state, response):
    """Audit copied evidence independently of the endpoint's passed flag."""
    from PIL import Image, ImageChops, ImageStat
    manifest = json.loads((group / "manifest.json").read_text())
    resolved = json.loads((group / "resolved_state.json").read_text())
    scene_hash = manifest["resolved_scene_state_hash"]
    if not isinstance(scene_hash, str) or not SHA256.fullmatch(scene_hash):
        raise ValueError("Invalid resolved scene-state identity")
    if (manifest.get("source_state") != selected_state
            or resolved["identity"]["gama_source_state"] != selected_state
            or resolved.get("resolved_scene_state_hash") != scene_hash
            or response.get("resolved_scene_state_hash") != scene_hash
            or canonical_hash(resolved["identity"]) != scene_hash
            or resolved.get("remaining_time_samples") != 0
            or resolved["identity"].get("pose_mapping") != "static_pose_proxy_v1"):
        raise ValueError("Resolved identity does not describe the selected actual frozen GAMA state")
    group_file(group, "source_scene.usdc", manifest["source_scene_sha256"])
    state_checks = manifest.get("state_checks", [])
    if (not state_checks or any(check.get("matches") is not True
            or check.get("resolved_scene_state_hash") != scene_hash for check in state_checks)
            or manifest.get("all_state_hashes_equal") is not True):
        raise ValueError("Resolved biological/environmental identity changed during capture")
    labels = [check.get("label") for check in state_checks]
    if len(labels) != len(set(labels)) or "after_attach" not in labels:
        raise ValueError("Frozen-state checkpoints are missing or duplicated")
    restoration = manifest.get("restoration_checks", {})
    if (response.get("ok") is not True or manifest.get("passed") is not True
            or manifest.get("status") != "passed" or not restoration
            or any(value is not True for value in restoration.values())
            or manifest.get("restoration_errors") != []
            or manifest.get("recovery_required") is not False
            or response.get("recovery_required") is not False):
        raise ValueError("The capture/restoration transaction did not pass")
    captures = manifest.get("captures", [])
    if (manifest.get("orders") != ORDERS or manifest.get("artificial_delay_s") != DELAY_S
            or len(captures) != 10 or response.get("capture_count") != 10):
        raise ValueError("Retained capture order/count differs from the predeclared workload")
    agent = selected_state["agents"][0]
    anchor = [agent["horizontal_position_m"][0], -agent["depth_m"], agent["horizontal_position_m"][1]]
    exposure = json.loads((ROOT / "experiments/gsd_pilot_v1/environment.json").read_text())["camera_exposure_attributes"]
    invariants = None
    repeated = {}
    camera_checks = []
    for index, item in enumerate(captures):
        order_index, condition_index = divmod(index, 5)
        gsd = ORDERS[order_index][condition_index]
        label = f"order_{order_index}_condition_{condition_index}"
        if (item.get("order_index") != order_index or item.get("condition_index") != condition_index
                or item.get("gsd_cm_px") != gsd
                or item.get("artificial_delay_s") != (DELAY_S if order_index else 0)
                or item.get("resolved_scene_state_hash") != scene_hash
                or item.get("render_product_camera_verified") is not True):
            raise ValueError("Capture condition differs from the declared workload")
        wrapped = item["camera_condition"]
        camera = wrapped["camera_condition"]
        condition_hash = wrapped["camera_condition_hash"]
        if canonical_hash(camera) != condition_hash:
            raise ValueError("Camera-condition hash differs from its resolved values")
        unit = camera["meters_per_scene_unit"]
        if (not math.isclose(unit, .01, rel_tol=0, abs_tol=1e-12)
                or camera["camera_path"] != "/MarlinGamaPairCamera"
                or camera["resolution_px"] != [1024, 768]
                or camera["nominal_gsd_cm_px"] != gsd or camera["projection"] != "perspective"
                or camera["reference_plane_y_m"] != anchor[1] or camera["anchor_m"] != anchor
                or not settings_equal(camera["authored_exposure_attributes"], exposure)):
            raise ValueError("Actual camera anchor, resolution, projection or exposure differs")
        expected_matrix = [[1, 0, 0, 0], [0, 0, -1, 0], [0, 1, 0, 0],
                           [anchor[0] / unit, (anchor[1] + 100 * gsd) / unit, anchor[2] / unit, 1]]
        if not all(math.isclose(camera["composed_camera_matrix"][i][j], expected_matrix[i][j],
                                rel_tol=1e-10, abs_tol=1e-8) for i in range(4) for j in range(4)):
            raise ValueError("Actual camera is not the declared fixed-anchor nadir camera")
        for key, expected in (("focal_length", 50 / (100 * unit)),
                              ("horizontal_aperture", 1024 * 5e-5 / unit),
                              ("vertical_aperture", 768 * 5e-5 / unit),
                              ("horizontal_aperture_offset", 0), ("vertical_aperture_offset", 0)):
            if not math.isclose(camera[key], expected, rel_tol=1e-6, abs_tol=1e-8):
                raise ValueError("Actual camera intrinsics differ from Pilot v1 geometry")
        if camera["clipping_range_scene_units"] != [1, 100000] or camera["f_stop"] != 0:
            raise ValueError("Actual camera clipping or depth-of-field optics differ")
        constant = {key: value for key, value in camera.items()
                    if key not in ("nominal_gsd_cm_px", "composed_camera_matrix")}
        if invariants is None:
            invariants = constant
        if constant != invariants:
            raise ValueError("An intrinsic/exposure camera field changed across GSD conditions")
        if gsd in repeated and repeated[gsd] != condition_hash:
            raise ValueError("Repeated GSD camera identities differ across capture orders")
        repeated[gsd] = condition_hash
        before, after = item["projection_before_capture"], item["projection_after_capture"]
        for projection in (before, after):
            product = projection["render_product"]
            if (projection.get("projection_metadata_version") != 2
                    or projection["actual_viewport_resolution"] != [1024, 768]
                    or product["camera"] != camera["camera_path"] or product["resolution"] != [1024, 768]
                    or product["pixel_aspect_ratio"] not in (None, 1)
                    or product["data_window_ndc"] not in (None, [0, 0, 1, 1])):
                raise ValueError("Actual render-product camera/resolution differs from the condition")
        for key in ("capture_view_matrix", "capture_projection_matrix", "render_product"):
            if before[key] != after[key]:
                raise ValueError("Capture-image projection changed during a condition")
        if item["rgb_file"] != label + "/rgb.png":
            raise ValueError("Capture RGB is not in its declared condition directory")
        png_file(group, item["rgb_file"], item["rgb_sha256"])
        probes = item["settling_probes"]
        if not 3 <= len(probes) <= 7 or item["settling_threshold_mean_absolute_rgb"] != 1.0:
            raise ValueError("Capture did not retain the declared settling probes")
        previous = None
        measured_difference = None
        for probe_index, probe in enumerate(probes):
            if probe["file"] != f"{label}/probe_{probe_index + 1:02d}.png":
                raise ValueError("Probe sequence is not in its declared condition directory")
            probe_path = png_file(group, probe["file"], probe["sha256"])
            with Image.open(probe_path) as source:
                current = source.convert("RGB")
            measured_difference = None if previous is None else sum(ImageStat.Stat(ImageChops.difference(previous, current)).mean) / 3
            declared_difference = probe["mean_absolute_rgb_difference_from_previous"]
            if ((measured_difference is None and declared_difference is not None)
                    or (measured_difference is not None and (type(declared_difference) not in (int, float)
                        or not math.isclose(measured_difference, declared_difference, rel_tol=1e-10, abs_tol=1e-9)))):
                raise ValueError("Retained RGB settling metric differs from the actual PNGs")
            previous = current
        if measured_difference >= 1 or item["rgb_sha256"] != probes[-1]["sha256"]:
            raise ValueError("Final RGB differs from the accepted settled probe")
        required_labels = [label + suffix for suffix in ("_before_delay", "_after_delay", "_after_warmup", "_complete")]
        required_labels.extend(label + f"_probe_{attempt}_{suffix}"
                               for attempt in range(1, len(probes) + 1) for suffix in ("before", "after"))
        if not set(required_labels).issubset(labels):
            raise ValueError("A condition lacks state checks around its delay, warmup or PNG probes")
        capture_path = group / f"order_{order_index}_condition_{condition_index}" / "capture.json"
        if json.loads(capture_path.read_text()) != item:
            raise ValueError("Per-condition capture sidecar differs from the group manifest")
        measured_gsd = [100 * (camera["composed_camera_matrix"][3][1] * unit - anchor[1])
                        / (camera["focal_length"] / camera[key] * pixels)
                        for key, pixels in (("horizontal_aperture", 1024), ("vertical_aperture", 768))]
        if any(not math.isclose(value, gsd, rel_tol=1e-6, abs_tol=1e-8) for value in measured_gsd):
            raise ValueError("Measured reference-plane GSD differs from the condition")
        camera_checks.append({"order_index": order_index, "condition_index": condition_index,
                              "gsd_cm_px": gsd, "camera_condition_hash": condition_hash,
                              "measured_reference_gsd_xy_cm_px": measured_gsd,
                              "settling_probes": len(probes), "final_mean_absolute_rgb_difference": measured_difference})
    return {"passed": True, "manifest": "group/manifest.json", "capture_count": len(captures),
            "resolved_scene_state_hash": scene_hash, "state_checks": len(state_checks),
            "retained_png_hashes_and_settling_metrics_verified": True,
            "nominal_reference_plane_camera_geometry_verified": True,
            "camera_checks": camera_checks, "underwater_optical_calibration_claimed": False,
            "rgb_bitwise_repeatability_claimed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8011")
    parser.add_argument("--output", type=Path, required=True, help="New exclusive evidence directory")
    parser.add_argument("--preflight-only", action="store_true", help="Read two audits and actor status; do not mutate the scene")
    args = parser.parse_args()
    parsed = urlparse(args.url)
    if (parsed.scheme not in ("http", "https") or parsed.hostname not in ("localhost", "127.0.0.1", "::1")
            or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
        parser.error("Use a loopback MARLIN base URL without credentials, paths or query parameters")
    output = safe_path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    token = None
    seal = None
    report = {"milestone": 6, "passed": False, "preflight_only": args.preflight_only,
              "scene_mutation_attempted": False, "milestone_7_started": False,
              "biological_approval": False,
              "declared_tolerances": {"position_euclidean_m": POSITION_TOLERANCE_M,
                                      "heading_circular_deg": HEADING_TOLERANCE_DEG,
                                      "renderer_float_relative": 1e-7, "renderer_float_absolute": 1e-9}}

    def request(path, payload=None, expect_ok=True):
        data = None if payload is None else json.dumps(payload, allow_nan=False).encode()
        req = urllib.request.Request(args.url.rstrip("/") + path, data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=1200) as response:
            result = json.load(response)
        if not isinstance(result, dict) or (expect_ok and result.get("ok") is not True):
            raise ValueError(f"{path}: {redact(result, token)}")
        return result

    def audit():
        return request("/integration/gama/marine/audit")

    try:
        seal = load_m5_seal()
        report["m5_before"] = verify_m5_seal(seal)
        if not report["m5_before"]["passed"]:
            raise ValueError("Protected M5 outputs changed before the live workload")
        steps, source = verified_trajectory()
        report["source_gama_record"] = source
        declaration = {"declared_at_utc": datetime.now(timezone.utc).isoformat(),
                       "selection_before_image_inspection": True,
                       "source_trajectory": source["path"], "source_sha256": source["sha256"],
                       "selected_step_index": SELECTED_STEP, "simulation_time_s": 4.0,
                       "behavioural_state": "shallow_swim", "orders": ORDERS,
                       "delay_s": DELAY_S,
                       "delay_policy": "Between captures in the second order; the endpoint does not delay the first order",
                       "no_silent_state_replacement": True}
        write_json(output / "declaration.json", declaration)
        report["declaration"] = declaration
        report["before"] = audit()
        report["actor_before"] = request(BASE + "/status")
        require_demo(report["before"])
        if (report["actor_before"]["owned"] or report["actor_before"]["root_present_on_active_stage"]):
            raise ValueError("Refusing an existing porpoise owner or private root")
        if args.preflight_only:
            time.sleep(2)
            report["second_audit"] = audit()
            report["preflight_checks"] = coexistence(report["before"], report["second_audit"])
            report["preflight_checks"]["layers_unchanged"] = report["before"]["inspection"]["layers"] == report["second_audit"]["inspection"]["layers"]
            report["passed"] = all(report["preflight_checks"].values())
        else:
            report["checkpoint_before_acquire"] = request("/debug/scene/checkpoint", {})
            report["scene_mutation_attempted"] = True
            acquired = request(BASE + "/acquire", {"agent_id": steps[0]["agents"][0]["agent_id"]})
            token = acquired["ownership_token"]
            report["acquired"] = redact(acquired, token)
            for step in steps[:SELECTED_STEP + 1]:
                applied = request(BASE + "/step", {"ownership_token": token, "step": step})
                if not applied.get("applied") or applied.get("duplicate"):
                    raise ValueError("An actual ordered GAMA update was not applied exactly once")
            report["selected_actor_before_capture"] = request(BASE + "/status")
            report["selected_pose_before_capture"] = compare_pose(steps[SELECTED_STEP], report["selected_actor_before_capture"], acquired["meters_per_scene_unit"])
            if report["selected_actor_before_capture"]["accepted_steps"] != SELECTED_STEP + 1:
                raise ValueError("Replay advanced beyond or failed to reach the selected step")
            capture = request(BASE + "/paired-capture", {"ownership_token": token,
                                                         "orders": ORDERS, "delay_s": DELAY_S}, expect_ok=False)
            report["paired_capture_response"] = redact(capture, token)
            if capture.get("directory"):
                report["retained_group"] = copy_group(capture["directory"], output)
            if capture.get("ok") is not True:
                raise ValueError("Paired-capture endpoint failed; returned group evidence was retained")
            if not report.get("retained_group"):
                raise ValueError("Paired-capture endpoint returned no evidence directory")
            report["group_checks"] = validate_group(output / "group", steps[SELECTED_STEP], capture)
            report["during"] = audit()
            report["selected_actor_after_capture"] = request(BASE + "/status")
            report["selected_pose_after_capture"] = compare_pose(steps[SELECTED_STEP], report["selected_actor_after_capture"], acquired["meters_per_scene_unit"])
            report["capture_held_actor"] = (
                report["selected_actor_after_capture"]["accepted_steps"] == SELECTED_STEP + 1
                and report["selected_actor_after_capture"]["world_pose"] == report["selected_actor_before_capture"]["world_pose"]
                and report["selected_actor_after_capture"]["latest"] == report["selected_actor_before_capture"]["latest"])
            if not report["capture_held_actor"]:
                raise ValueError("Paired capture advanced or changed the owned GAMA state")
    except BaseException as error:
        report["error"] = redact(f"{type(error).__name__}: {error}", token)
    finally:
        if token is not None:
            try:
                report["release"] = request(BASE + "/release", {"ownership_token": token})
            except BaseException as error:
                report["cleanup_error"] = redact(f"{type(error).__name__}: {error}", token)
            try:
                time.sleep(2)
                report["after_release"] = audit()
                report["actor_after_release"] = request(BASE + "/status")
                report["cleanup_checks"] = coexistence(report["before"], report["after_release"])
                report["cleanup_checks"].update(
                    layers_restored=report["before"]["inspection"]["layers"] == report["after_release"]["inspection"]["layers"],
                    actor_released=not report["actor_after_release"]["owned"] and report["actor_after_release"]["actor_count"] == 0,
                    private_root_absent=not report["actor_after_release"]["root_present_on_active_stage"])
                if "during" in report:
                    report["during_checks"] = coexistence(report["before"], report["during"])
                report["passed"] = (not report.get("error") and not report.get("cleanup_error")
                    and bool(report.get("capture_held_actor")) and bool(report.get("group_checks", {}).get("passed"))
                    and all(report["cleanup_checks"].values()) and all(report.get("during_checks", {"missing": False}).values()))
            except BaseException as error:
                report["cleanup_verification_error"] = redact(f"{type(error).__name__}: {error}", token)
                report["passed"] = False
        if seal is not None:
            try:
                report["m5_after"] = verify_m5_seal(seal)
                report["passed"] = report["passed"] and report["m5_after"]["passed"]
            except BaseException as error:
                report["m5_preservation_error"] = redact(f"{type(error).__name__}: {error}", token)
                report["passed"] = False
        if report.get("error") or report.get("cleanup_error"):
            report["passed"] = False
        write_json(output / "results.json", redact(report, token))
    print(json.dumps({"passed": report["passed"], "preflight_only": args.preflight_only,
                      "results": str(output / "results.json"), "error": report.get("error"),
                      "cleanup_error": report.get("cleanup_error")}, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
