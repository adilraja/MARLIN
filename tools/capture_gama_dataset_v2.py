"""Bounded M7 dataset capture from declared, sealed actual GAMA trajectories.

This client never launches Kit/GAMA, selects new states from image appearance,
or changes source assets. A completed declaration precedes all M7 rendering.
Every output directory is exclusive and failures remain available for review.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import time
from urllib.parse import urlparse
import urllib.request

import verify_gama_paired_live as live

ROOT, SPRINT, BASE = live.ROOT, live.SPRINT, live.BASE
SEEDS = (1, 42, 184729, 20261008, 2147483647)
STEPS = (8, 16, 32)
GSDS = (.5, 1., 2., 3., 4.)
SPLITS = {1: "train", 42: "train", 184729: "train", 20261008: "validation", 2147483647: "test"}
M6_MANIFEST = SPRINT / "qa/milestone_6_manifest.json"
DECLARATION = SPRINT / "m7_capture_declaration.json"
BRIDGE = "source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge"
ALLOWED_M6_DELTAS = frozenset((BRIDGE + "/extension.py", BRIDGE + "/paired_v2.py"))
HEADROOM_ATTEMPTS = 4
HEADROOM_DELAY_S = 20
HEADROOM_REJECTION = re.compile(r"Insufficient GPU headroom before capture: ([0-9]+) MiB free; require at least 768 MiB\. No render attempted\.\Z")


def pin(path):
    path = live.safe_path(path)
    return {"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": live.digest(path)}


def load_seal(path, allowed_changes=()):
    document = json.loads(path.read_text())
    if document.get("status") != "complete" or document.get("passed") is not True:
        raise ValueError("A completed sealed milestone is required")
    if not isinstance(document.get("outputs"), list) or not document["outputs"]:
        raise ValueError("A sealed milestone has no output pins")
    return {"manifest": pin(path), "outputs": document["outputs"], "allowed_changes": sorted(allowed_changes),
            "allowed_current_pins": [pin(ROOT / row["path"]) for row in document["outputs"]
                                     if row["path"] in allowed_changes]}


def verify_seal(seal):
    failures, deltas = [], []
    for row in seal["outputs"]:
        path = live.safe_path(ROOT / row["path"])
        if not path.is_relative_to(ROOT):
            raise ValueError("A sealed output escaped the repository")
        current = pin(path) if path.is_file() else None
        if row["path"] in seal["allowed_changes"]:
            initial = next(item for item in seal["allowed_current_pins"] if item["path"] == row["path"])
            if current != initial:
                failures.append({"path": row["path"], "error": "Declared M7 runtime source changed during execution"})
            deltas.append({"path": row["path"], "sealed_sha256": row["sha256"],
                           "current_sha256": None if current is None else current["sha256"],
                           "intentional_m7_delta": current != row})
        elif current != row:
            failures.append({"path": row["path"], "error": "Protected output changed or disappeared"})
    if pin(ROOT / seal["manifest"]["path"]) != seal["manifest"]:
        failures.append({"path": seal["manifest"]["path"], "error": "Sealed manifest changed"})
    return {"passed": not failures, "manifest": seal["manifest"],
            "outputs_checked": len(seal["outputs"]), "changes": failures,
            "intentional_source_deltas": deltas}


def verified_run(seed, suffix="a"):
    directory = SPRINT / f"trajectories/m5_positive_seed_{seed}_{suffix}"
    execution = json.loads((directory / "execution.json").read_text())
    retained = json.loads((directory / "configuration.json").read_text())
    expected_id = directory.name
    if (execution.get("status") != "passed" or execution.get("return_code") != 0
            or execution.get("requested_seed") != seed or execution.get("actual_seed") != seed
            or execution.get("run_id") != expected_id
            or retained.get("run_id") != expected_id or retained.get("requested_seed") != seed):
        raise ValueError("Expected a distinct accepted actual positive-seed GAMA execution")
    config = retained["configuration"]
    raw = directory / "raw/simulation-outputs0.xml"
    states, validation = live.recorder.read_trajectory(raw, config, expected_id, seed)
    canonical = hashlib.sha256(live.recorder.canonical_states(states)).hexdigest()
    if (validation.get("passed") is not True or states != json.loads((directory / "trajectory.json").read_text())
            or canonical != execution["canonical_state_sha256"]
            or live.digest(raw) != execution["raw_xml_sha256"]
            or live.digest(directory / "trajectory.json") != execution["trajectory_sha256"]
            or live.digest(directory / "model.gaml") != execution["model_sha256"]
            or live.digest(SPRINT / "porpoise_model_config.json") != execution["configuration_sha256"]
            or config != json.loads((SPRINT / "porpoise_model_config.json").read_text())
            or live.digest(directory / "experiment.xml") != execution["experiment_plan_sha256"]):
        raise ValueError("Actual GAMA records differ from sealed execution/source identities")
    files = [pin(directory / name) for name in ("execution.json", "configuration.json", "model.gaml",
                                               "experiment.xml", "trajectory.json", "raw/simulation-outputs0.xml")]
    selected = [states[index] for index in STEPS]
    for state, index, label, depth in zip(selected, STEPS, ("shallow_swim", "descent", "ascent"), (.5, 1.9, 1.6)):
        if (state["step_index"] != index or state["simulation_time_s"] != index * .5
                or state["agents"][0]["behavioural_state"] != label
                or not math.isclose(state["agents"][0]["depth_m"], depth, rel_tol=0, abs_tol=1e-12)):
            raise ValueError("The declared fixed state/time coverage changed")
    return states, {"run_id": expected_id, "seed": seed, "samples": len(states),
                    "split": SPLITS[seed], "encounter_group_id": f"gama_engineering_porpoise_seed_{seed}",
                    "raw_gama_reparse_passed": True, "canonical_state_sha256": canonical,
                    "source_files": files, "selected_states": selected,
                    "model_sha256": execution["model_sha256"],
                    "model_configuration_sha256": execution["configuration_sha256"],
                    "runtime": execution["runtime"], "runtime_configuration_sha256": execution["runtime_configuration_sha256"],
                    "launcher_sha256": execution["launcher_sha256"],
                    "actual_execution": {key: execution[key] for key in ("started_at_utc", "finished_at_utc", "command", "cwd", "return_code", "actual_seed")}}


def build_plan():
    """Read actual records only; caller exclusively saves the approved declaration."""
    runs = []
    for seed in SEEDS:
        _, record = verified_run(seed)
        related = [record["run_id"]]
        repeats = []
        if seed in (1, 184729, 2147483647):
            _, repeat = verified_run(seed, "b")
            if repeat["canonical_state_sha256"] != record["canonical_state_sha256"]:
                raise ValueError("Related repeated encounter did not reproduce its source trajectory")
            related.append(repeat["run_id"])
            repeats.append({key: repeat[key] for key in ("run_id", "split", "encounter_group_id", "source_files", "canonical_state_sha256")})
        record.update(related_run_ids=related, related_runs_not_rendered=repeats)
        runs.append(record)
    if (len({run["run_id"] for run in runs}) != 5
            or len({run["canonical_state_sha256"] for run in runs}) != 5
            or len({run["actual_execution"]["command"][-1] for run in runs}) != 5):
        raise ValueError("The five selected GAMA executions are not distinct")
    return {"schema_version": "1.0", "milestone": 7,
            "selection_declared_before_m7_image_inspection": True,
            "selection_rule": "Fixed step indices 8, 16, 32 from each of five predeclared accepted actual GAMA executions",
            "seeds": list(SEEDS), "snapshot_steps": list(STEPS), "simulation_times_s": [4., 8., 16.],
            "gsd_conditions_cm_px": list(GSDS), "snapshots_per_trajectory": 3,
            "planned_capture_groups": 15, "planned_target_present_captures": 75,
            "planned_target_absent_captures": 75,
            "split_policy": "Whole trajectory/encounter, including all snapshots, five GSDs, negative counterparts and related repeated run IDs",
            "splits": {name: [run["run_id"] for run in runs if run["split"] == name]
                       for name in ("train", "validation", "test")},
            "runs": runs, "no_silent_state_replacement": True,
            "negative_policy": {"operation": "RemovePrim", "prim_path": "/MarlinGamaPorpoise",
                                "scope": "private_frozen_variant", "same_parent_frozen_snapshot": True,
                                "poor_visibility_is_not_target_absence": True},
            "scope": {"engineering_test_set_only": True, "biological_approval": False,
                      "pose_mapping": "static_pose_proxy_v1", "visibility": "unknown until reviewed; no image-based reselection",
                      "annotation_semantics": "amodal_direct_evaluated_mesh_projection",
                      "exact_visible_or_refracted_outline_claimed": False,
                      "seed_variation": "initial angular phase only; separate fresh processes do not establish biological stochastic independence",
                      "coverage": "shallow swimming, descent and ascent at motion-root depths 0.5, 1.9 and 1.6 m; no complete five-state pose validation",
                      "environment": "Frozen current marine presentation environment per snapshot; Pilot-style 1024x768 nominal root-plane optics",
                      "new_gama_executions_required": False,
                      "reused_gama_executions": "Five accepted independent fresh processes retained and sealed in M5"},
            "m7_intentional_existing_source_deltas": sorted(ALLOWED_M6_DELTAS),
            "runtime_code_pin_policy": "Record current bounded client/bridge code hashes before execution and require unchanged hashes after; historical sealed source bytes remain preserved in M6 records"}


def validate_declaration(path):
    declaration = json.loads(path.read_text())
    current = build_plan()
    metadata_fields = {"declared_at_utc", "sealed_m5_manifest", "sealed_m6_manifest",
                       "strict_baseline_verification_before_m7_refactor", "historical_m6_source_pins"}
    if set(declaration) != set(current) | metadata_fields:
        raise ValueError("Declaration has missing or unsupported schema fields")
    for key, expected in current.items():
        if declaration.get(key) != expected:
            raise ValueError("The approved declaration differs from actual sources: " + key)
    if not declaration.get("declared_at_utc"):
        raise ValueError("A prior timestamped declaration is required")
    declared_time = datetime.fromisoformat(declaration["declared_at_utc"])
    if declared_time.tzinfo is None or declared_time > datetime.now(timezone.utc):
        raise ValueError("The declaration must have an actual prior timezone-aware timestamp")
    for key, manifest in (("sealed_m5_manifest", live.M5_MANIFEST), ("sealed_m6_manifest", M6_MANIFEST)):
        if declaration.get(key) != pin(manifest):
            raise ValueError("A declared historical seal changed")
    baseline = declaration["strict_baseline_verification_before_m7_refactor"]
    for key, manifest in (("milestone_5", live.M5_MANIFEST), ("milestone_6", M6_MANIFEST)):
        evidence = baseline[key]
        seal = json.loads(manifest.read_text())
        if (evidence.get("passed") is not True or evidence.get("outputs_checked") != len(seal["outputs"])
                or evidence.get("changes") != [] or evidence.get("manifest_sha256") != live.digest(manifest)):
            raise ValueError("Declared strict pre-refactor seal verification changed")
    historical = json.loads(M6_MANIFEST.read_text())["outputs"]
    if declaration["historical_m6_source_pins"] != [row for row in historical if row["path"].startswith("source/")]:
        raise ValueError("Declared historical M6 source pins changed")
    return declaration


def runtime_code_pins():
    # Only canonical package files are read, including new bounded modules.
    paths = sorted((ROOT / BRIDGE).glob("*.py"))
    paths.extend((Path(__file__).resolve(), Path(live.__file__).resolve(), Path(live.recorder.__file__).resolve()))
    service = ROOT / "source/extensions/cris.madil.render_service/cris/madil/render_service"
    paths.extend(service / name for name in ("hidef_marine.py", "calibration_geometry.py", "capture_projection.py",
                                            "capture_state.py", "calibration_capture.py", "camera.py",
                                            "cetacean_gallery.py", "cetacean.py", "ocean.py", "petrel_api.py"))
    return [pin(path) for path in sorted(set(paths))]


def is_no_render_headroom(response):
    """Only this exact pre-render rejection can be retried without new images."""
    if (not isinstance(response, dict) or set(response) != {"ok", "error"}
            or response.get("ok") is not False or not isinstance(response.get("error"), str)):
        return False
    match = HEADROOM_REJECTION.fullmatch(response["error"])
    return match is not None and int(match.group(1)) < 768


def _assert_held_state(status, state, expected_status, units):
    if (status.get("owned") is not True or status.get("guard_error") is not None
            or status.get("latest") != state or status.get("accepted_steps") != state["step_index"] + 1
            or status.get("accepted_steps") != expected_status["accepted_steps"]
            or status.get("world_pose") != expected_status["world_pose"]
            or status.get("autonomous_controller") is not False or status.get("actor_count") != 1):
        raise ValueError("Headroom wait changed ownership, held GAMA snapshot/count/pose or guard state")
    live.compare_pose(state, status, units)


def capture_with_headroom_retry(capture_once, status_read, state, expected_status, units,
                               attempts, expected_code_pins, wait=time.sleep, utc_now=None,
                               code_read=None):
    """Try one unchanged capture at most four times, only before any rendering.

    ``capture_once`` sends the same fixed ownership-token payload on every call
    and returns (response_dictionary, actual_http_status_code). Injectable reads,
    waits and clocks support pure tests without touching the live service.
    All response/error evidence goes into the caller-owned ``attempts`` list.
    Non-headroom responses return immediately for the normal retention path.
    """
    now = utc_now or (lambda: datetime.now(timezone.utc).isoformat())
    read_code = code_read or runtime_code_pins
    for number in range(1, HEADROOM_ATTEMPTS + 1):
        record = {"attempt_index": number, "started_at_utc": now(),
                  "held_state_before": False, "runtime_code_unchanged": False,
                  "same_source_step_index": state["step_index"], "same_source_run_id": state["run_id"]}
        attempts.append(record)
        current_code = read_code()
        record["runtime_code_pins_sha256"] = live.canonical_hash(current_code)
        record["runtime_code_unchanged"] = current_code == expected_code_pins
        if not record["runtime_code_unchanged"]:
            raise ValueError("Runtime code changed before a bounded headroom capture attempt")
        record["status_before"] = status_read()
        _assert_held_state(record["status_before"], state, expected_status, units)
        record["held_state_before"] = True
        response, http_code = capture_once()
        record.update(response=response, http_status_code=http_code, response_received_at_utc=now(),
                      retryable_no_render_headroom=is_no_render_headroom(response))
        if not record["retryable_no_render_headroom"]:
            # Return the response even if this read detects a changed actor so
            # the caller can retain any returned image group before aborting.
            record["held_state_after_response"] = False
            try:
                record["status_after_response"] = status_read()
                _assert_held_state(record["status_after_response"], state, expected_status, units)
                record["held_state_after_response"] = True
            except BaseException as error:
                record["post_response_status_error"] = f"{type(error).__name__}: {error}"
            return response
        record.update(observed_free_gpu_mib=int(HEADROOM_REJECTION.fullmatch(response["error"]).group(1)),
                      required_free_gpu_mib=768, render_attempted=False, held_state_after_rejection=False)
        record["status_after_headroom_rejection"] = status_read()
        _assert_held_state(record["status_after_headroom_rejection"], state, expected_status, units)
        record["held_state_after_rejection"] = True
        if number == HEADROOM_ATTEMPTS:
            record["retry_exhausted"] = True
            return response
        record["wait_before_next_attempt_s"] = HEADROOM_DELAY_S
        wait(HEADROOM_DELAY_S)
        record["wait_completed_at_utc"] = now()
        record["status_after_wait"] = status_read()
        record["held_state_after_wait"] = False
        _assert_held_state(record["status_after_wait"], state, expected_status, units)
        record["held_state_after_wait"] = True
        record["runtime_code_unchanged_after_wait"] = read_code() == expected_code_pins
        if not record["runtime_code_unchanged_after_wait"]:
            raise ValueError("Runtime code changed during a bounded headroom wait")
    raise AssertionError("Bounded headroom loop exhausted without a response")


def disk_preflight(output):
    source = SPRINT / "qa/m6_live_03/group/source_scene.usdc"
    source_bytes = source.stat().st_size
    # Conservative provisioning includes two USD variants, ten accepted PNGs,
    # up to seven RGBA probes per capture, both runtime and retained copies.
    per_group = 2 * source_bytes + 80 * 1024 * 768 * 4 + 5 * 1024 * 1024
    estimate = 15 * 2 * per_group + 512 * 1024 * 1024
    usage = shutil.disk_usage(output)
    return {"passed": usage.free >= estimate, "available_bytes": usage.free,
            "estimated_required_bytes": estimate, "m6_source_scene_bytes": source_bytes,
            "basis": "Engineering space provision for 15 groups, two USD variants/group, up to 70 probe plus ten accepted 1024x768 RGBA PNGs/group, runtime and retained copies; no exact compression-size guarantee"}


def finite_list(value, size, label):
    if (not isinstance(value, list) or len(value) != size
            or any(type(item) not in (int, float) or not math.isfinite(item) for item in value)):
        raise ValueError(label + " must contain finite numeric coordinates")
    return value


def validate_annotation(group, item, state):
    path = live.group_file(group, item["annotation_file"], item["annotation_sha256"])
    yolo_path = live.group_file(group, item["yolo_file"], item["yolo_sha256"])
    annotation = json.loads(path.read_text())
    if annotation != item["annotation"]:
        raise ValueError("Inline annotation differs from the retained JSON")
    agent = state["agents"][0]
    target = item["target_present"]
    expected = {"schema_version": "gama_marlin_amodal_annotation_v1", "target_present": target,
                "species": agent["species"], "class_id": 0, "run_id": state["run_id"],
                "step_index": state["step_index"], "simulation_time_s": state["simulation_time_s"],
                "original_gama_depth_m": agent["depth_m"], "vertical_reference": agent["vertical_reference"],
                "behavioural_state": agent["behavioural_state"], "resolution_px": [1024, 768],
                "camera_path": item["camera_condition"]["camera_condition"]["camera_path"],
                "annotation_semantics": "amodal_direct_evaluated_mesh_projection",
                "pose_mapping": "static_pose_proxy_v1", "biological_approval": False,
                "pose_scope": "Direct geometry only; body animation, breathing and biological dive pose were not certified",
                "class_scope": "Owned harbour porpoise only; unrelated demonstration animals remain unlabelled background",
                "area_semantics": "Rectangle box area only; neither visible pixels nor silhouette area",
                "rendered_visibility": "unknown", "visible_mask": None, "refraction_calibrated": False,
                "projected_silhouette_area_px": None, "visible_target_area_px": None}
    common_geometry_fields = {"mesh_paths", "vertex_count", "raw_amodal_bbox_xyxy_px", "amodal_bbox_xyxy_px",
                              "amodal_bbox_coco_xywh_px", "intersects_image", "bbox_clipped_to_image", "annotation_status"}
    allowed_fields = set(expected) | common_geometry_fields
    if target:
        allowed_fields.update(("projected_vertices_sha256", "world_bounds_min_m", "world_bounds_max_m", "target_usd_visibility"))
        if annotation.get("intersects_image") is True:
            allowed_fields.add("bbox_rectangle_area_px")
    if set(annotation) != allowed_fields:
        raise ValueError("Annotation has missing or unsupported schema fields")
    if any(annotation.get(key) != value for key, value in expected.items()):
        raise ValueError("Annotation source/presence/visibility/optical semantics differ")
    if (type(annotation["class_id"]) is not int or type(annotation["target_present"]) is not bool
            or annotation["biological_approval"] is not False or annotation["refraction_calibrated"] is not False
            or type(annotation["vertex_count"]) is not int or type(annotation["step_index"]) is not int
            or not isinstance(annotation["resolution_px"], list)
            or any(type(value) is not int for value in annotation["resolution_px"])):
        raise ValueError("Annotation class, presence, approval, geometry count and resolution require strict types")
    if not target:
        if (annotation.get("mesh_paths") != [] or annotation.get("vertex_count") != 0
                or annotation.get("raw_amodal_bbox_xyxy_px") is not None
                or annotation.get("amodal_bbox_xyxy_px") is not None
                or annotation.get("amodal_bbox_coco_xywh_px") is not None
                or annotation.get("intersects_image") is not False
                or annotation.get("bbox_clipped_to_image") is not False
                or annotation.get("annotation_status") != "target_physically_removed"
                or yolo_path.read_text() != ""):
            raise ValueError("A removed-target counterpart has target geometry or a nonempty label")
    else:
        meshes = annotation.get("mesh_paths")
        if (not isinstance(meshes, list) or not meshes or len(meshes) != len(set(meshes))
                or any(not isinstance(path, str) or not path.startswith("/MarlinGamaPorpoise/Porpoise_001/") for path in meshes)
                or type(annotation.get("vertex_count")) is not int or annotation["vertex_count"] <= 0
                or not live.SHA256.fullmatch(annotation.get("projected_vertices_sha256", ""))):
            raise ValueError("Present-target annotation lacks evaluated owned-mesh provenance")
        low = finite_list(annotation["world_bounds_min_m"], 3, "World bounds minimum")
        high = finite_list(annotation["world_bounds_max_m"], 3, "World bounds maximum")
        if any(lo > hi for lo, hi in zip(low, high)) or annotation["target_usd_visibility"] not in ("inherited", "invisible"):
            raise ValueError("Present-target world bounds/USD visibility are invalid")
        raw = finite_list(annotation.get("raw_amodal_bbox_xyxy_px"), 4, "Raw amodal box")
        if raw[0] > raw[2] or raw[1] > raw[3]:
            raise ValueError("Raw amodal box is inverted")
        clipped = [max(0, raw[0]), max(0, raw[1]), min(1024, raw[2]), min(768, raw[3])]
        intersects = clipped[0] < clipped[2] and clipped[1] < clipped[3]
        if (annotation.get("intersects_image") is not intersects
                or annotation.get("bbox_clipped_to_image") is not (intersects and clipped != raw)):
            raise ValueError("Annotation clipping/intersection flags differ from the actual box")
        if intersects:
            x0, y0, x1, y1 = clipped
            coco = [x0, y0, x1 - x0, y1 - y0]
            label = "0 " + " ".join(f"{value:.12f}" for value in (
                (x0 + x1) / (2 * 1024), (y0 + y1) / (2 * 768), (x1 - x0) / 1024, (y1 - y0) / 768)) + "\n"
            if (annotation.get("amodal_bbox_xyxy_px") != clipped
                    or annotation.get("amodal_bbox_coco_xywh_px") != coco
                    or annotation.get("bbox_rectangle_area_px") != (x1 - x0) * (y1 - y0)
                    or annotation.get("annotation_status") != "physically_present_direct_amodal_box"
                    or yolo_path.read_text() != label):
                raise ValueError("Clipped JSON/COCO box or normalized YOLO label is inconsistent")
        elif (annotation.get("amodal_bbox_xyxy_px") is not None
                or annotation.get("amodal_bbox_coco_xywh_px") is not None
                or annotation.get("annotation_status") != "physically_present_outside_image"
                or yolo_path.read_text() != ""):
            raise ValueError("Out-of-frame target must retain physical presence with an empty image label")
    return {"passed": True, "annotation_status": annotation["annotation_status"],
            "target_present": target, "intersects_image": annotation["intersects_image"],
            "bbox_xyxy_px": annotation["amodal_bbox_xyxy_px"], "rendered_visibility": "unknown",
            "independent_usd_vertex_projection_verified": False,
            "limitation": "Client verifies source semantics, arithmetic, labels and hashes; separate retained-USD verification must rebuild evaluated mesh projections"}


def validate_camera_pixels(group, item, state):
    from PIL import Image, ImageChops, ImageStat
    gsd = item["gsd_cm_px"]
    wrapped = item["camera_condition"]
    camera = wrapped["camera_condition"]
    if live.canonical_hash(camera) != wrapped["camera_condition_hash"]:
        raise ValueError("Camera identity hash differs from the resolved condition")
    agent = state["agents"][0]
    anchor = [agent["horizontal_position_m"][0], -agent["depth_m"], agent["horizontal_position_m"][1]]
    unit = camera["meters_per_scene_unit"]
    exposure = json.loads((ROOT / "experiments/gsd_pilot_v1/environment.json").read_text())["camera_exposure_attributes"]
    if (not math.isclose(unit, .01, rel_tol=0, abs_tol=1e-12)
            or camera["camera_path"] != "/MarlinGamaPairCamera" or camera["resolution_px"] != [1024, 768]
            or camera["nominal_gsd_cm_px"] != gsd or camera["projection"] != "perspective"
            or camera["reference_plane_y_m"] != anchor[1] or camera["anchor_m"] != anchor
            or not live.settings_equal(camera["authored_exposure_attributes"], exposure)
            or camera["clipping_range_scene_units"] != [1, 100000] or camera["f_stop"] != 0):
        raise ValueError("Camera geometry/exposure differs from the bounded Pilot-style condition")
    expected_matrix = [[1, 0, 0, 0], [0, 0, -1, 0], [0, 1, 0, 0],
                       [anchor[0] / unit, (anchor[1] + 100 * gsd) / unit, anchor[2] / unit, 1]]
    matrix = camera["composed_camera_matrix"]
    if (not isinstance(matrix, list) or len(matrix) != 4
            or any(not isinstance(row, list) or len(row) != 4 for row in matrix)
            or not all(type(matrix[i][j]) in (int, float) and math.isfinite(matrix[i][j])
                       and math.isclose(matrix[i][j], expected_matrix[i][j], rel_tol=1e-10, abs_tol=1e-8)
                       for i in range(4) for j in range(4))):
        raise ValueError("Actual camera differs from the fixed-anchor nadir pose")
    for key, value in (("focal_length", 50 / (100 * unit)), ("horizontal_aperture", 1024 * 5e-5 / unit),
                       ("vertical_aperture", 768 * 5e-5 / unit), ("horizontal_aperture_offset", 0), ("vertical_aperture_offset", 0)):
        if type(camera[key]) not in (int, float) or not math.isclose(camera[key], value, rel_tol=1e-6, abs_tol=1e-8):
            raise ValueError("Resolved camera intrinsics differ from the requested condition")
    projections = (item["projection_before_capture"], item["projection_after_capture"])
    for projection in projections:
        product = projection["render_product"]
        if (projection.get("projection_metadata_version") != 2
                or projection["actual_viewport_resolution"] != [1024, 768]
                or product["camera"] != camera["camera_path"] or product["resolution"] != [1024, 768]
                or product["pixel_aspect_ratio"] not in (None, 1)
                or product["data_window_ndc"] not in (None, [0, 0, 1, 1])
                or item.get("render_product_camera_verified") is not True):
            raise ValueError("Actual image render product disagrees with camera metadata")
    for key in ("capture_view_matrix", "capture_projection_matrix", "render_product"):
        if projections[0][key] != projections[1][key]:
            raise ValueError("Actual projection changed during capture")
    label = f"{item['variant']}_order_0_condition_{item['condition_index']}"
    if item["rgb_file"] != label + "/rgb.png":
        raise ValueError("RGB file does not belong to its declared condition")
    image = live.png_file(group, item["rgb_file"], item["rgb_sha256"])
    with Image.open(image) as decoded:
        decoded.load()
        if decoded.size != (1024, 768):
            raise ValueError("RGB dimensions differ from annotation/camera resolution")
    probes = item["settling_probes"]
    if not 3 <= len(probes) <= 7 or item["settling_threshold_mean_absolute_rgb"] != 1:
        raise ValueError("RGB probes do not satisfy the existing bounded settling protocol")
    previous, difference = None, None
    for attempt, probe in enumerate(probes, 1):
        if probe["file"] != f"{label}/probe_{attempt:02d}.png":
            raise ValueError("Probe does not belong to its condition/sequence")
        path = live.png_file(group, probe["file"], probe["sha256"])
        with Image.open(path) as decoded:
            current = decoded.convert("RGB")
        difference = None if previous is None else sum(ImageStat.Stat(ImageChops.difference(previous, current)).mean) / 3
        recorded = probe["mean_absolute_rgb_difference_from_previous"]
        if ((difference is None and recorded is not None)
                or (difference is not None and (type(recorded) not in (int, float)
                    or not math.isclose(difference, recorded, rel_tol=1e-10, abs_tol=1e-9)))):
            raise ValueError("Actual retained probe pixels disagree with the settling metadata")
        previous = current
    if difference >= 1 or item["rgb_sha256"] != probes[-1]["sha256"]:
        raise ValueError("Accepted RGB is not its settled final probe")
    return {"passed": True, "camera_condition_hash": wrapped["camera_condition_hash"],
            "settling_probes": len(probes), "final_mean_absolute_rgb_difference_0_to_255": difference,
            "underwater_optical_calibration_claimed": False, "pixel_identical_pairing_claimed": False}


def validate_group(group, state, response):
    manifest = json.loads((group / "manifest.json").read_text())
    if (response.get("ok") is not True or manifest.get("passed") is not True
            or manifest.get("status") != "passed" or manifest.get("milestone") != 7
            or manifest.get("source_state") != state or manifest.get("orders") != [list(GSDS)]
            or manifest.get("artificial_delay_s") != 0 or len(manifest.get("captures", [])) != 10
            or response.get("capture_count") != 10 or response.get("recovery_required") is not False
            or manifest.get("recovery_required") is not False or manifest.get("restoration_errors") != []):
        raise ValueError("The bounded dataset transaction did not pass as declared")
    restoration = manifest.get("restoration_checks", {})
    if not restoration or any(value is not True for value in restoration.values()):
        raise ValueError("The dataset transaction did not restore all saved scene state")
    if (not live.SHA256.fullmatch(manifest.get("original_source_content_hash", ""))
            or manifest["original_source_content_hash"] != manifest.get("restored_source_content_hash")):
        raise ValueError("Original non-camera scene content was not restored exactly")
    parent, background = manifest["parent_scene_hash"], manifest["background_scene_hash"]
    if (not live.SHA256.fullmatch(parent) or not live.SHA256.fullmatch(background)
            or parent != response.get("parent_scene_hash") or background != response.get("background_scene_hash")
            or parent != response.get("resolved_scene_state_hash") or parent != manifest.get("resolved_scene_state_hash")):
        raise ValueError("Parent/background response identities disagree with the retained manifest")
    records = manifest["variant_records"]
    if set(records) != {"present", "absent"}:
        raise ValueError("Exactly one positive and one removed-target variant are required")
    for variant in ("present", "absent"):
        record, identity = records[variant], records[variant]["identity"]
        if (live.canonical_hash(identity) != record["resolved_scene_state_hash"]
                or record.get("remaining_time_samples") != 0 or identity.get("gama_source_state") != state):
            raise ValueError("Variant identity/source state is invalid")
        scene = manifest["variant_scene_files"][variant]
        if scene["file"] != variant + "_scene.usdc":
            raise ValueError("Unexpected frozen variant scene filename")
        live.group_file(group, scene["file"], scene["sha256"])
    positive, negative = records["present"], records["absent"]
    if (positive["resolved_scene_state_hash"] != parent or positive["identity"]["pose_mapping"] != "static_pose_proxy_v1"
            or negative["schema_version"] != "gama_marlin_target_absent_v1"
            or negative.get("target_present") is not False or negative["identity"].get("target_present") is not False
            or negative["identity"].get("target_mesh_count") != 0
            or negative["identity"].get("parent_positive_scene_state_hash") != parent
            or negative["identity"].get("biological_approval") is not False
            or negative["identity"].get("pose_mapping") != "target_removed_counterpart_of_static_pose_proxy_v1"
            or negative.get("background_hash") != background
            or negative["resolved_scene_state_hash"] == parent):
        raise ValueError("The removed-target identity is not an explicit positive-linked counterfactual")
    for key in ("stage_coordinates", "renderer_settings", "dependencies", "environment_clock", "gama_source_state"):
        if positive["identity"][key] != negative["identity"][key]:
            raise ValueError("Negative variant changed a common source context field: " + key)
    checked_dependencies, unresolved_dependencies = [], []
    for dependency in positive["identity"]["dependencies"]:
        if dependency.get("sha256") is None:
            if dependency.get("status") != "runtime_or_unresolved":
                raise ValueError("An unhashed runtime dependency lacks its explicit limitation")
            unresolved_dependencies.append(dependency["path"])
            continue
        # Skip explicitly unresolved runtime paths before resolving/opening them.
        path = live.safe_path(dependency["path"])
        if not path.is_relative_to(ROOT) or live.digest(path) != dependency["sha256"]:
            raise ValueError("A recorded local positive/background dependency changed")
        checked_dependencies.append({"path": dependency["path"], "sha256": dependency["sha256"]})
    removal = manifest["target_removal"]
    required_removal = {"operation": "RemovePrim", "prim_path": "/MarlinGamaPorpoise", "scope": "private_frozen_variant"}
    if (any(removal.get(key) != value for key, value in required_removal.items())
            or negative["identity"].get("removal_operation") != required_removal
            or removal.get("parent_positive_scene_state_hash") != parent
            or removal.get("before_target_present") is not True or removal.get("after_target_present") is not False
            or type(removal.get("before_target_mesh_count")) is not int or removal["before_target_mesh_count"] < 1
            or removal.get("after_target_mesh_count") != 0
            or "/MarlinGamaPorpoise" not in removal["before_root_paths"]
            or removal["after_root_paths"] != [path for path in removal["before_root_paths"] if path != "/MarlinGamaPorpoise"]):
        raise ValueError("Target removal was not the bounded physical subtree operation")
    if json.loads((group / "resolved_state.json").read_text()) != positive or json.loads((group / "absent_resolved_state.json").read_text()) != negative:
        raise ValueError("Variant JSON sidecars differ from the manifest")
    checks = manifest.get("state_checks", [])
    if not checks or manifest.get("all_variant_state_checks_match") is not True:
        raise ValueError("Variant freeze/background checks did not pass")
    labels = {}
    for check in checks:
        variant = check.get("variant")
        if (variant not in records or check.get("matches") is not True
                or check.get("target_present") is not (variant == "present")
                or check.get("resolved_scene_state_hash") != records[variant]["resolved_scene_state_hash"]
                or check.get("parent_scene_hash") != parent or check.get("background_scene_hash") != background
                or check.get("label") in labels):
            raise ValueError("A variant state/background checkpoint differs from its declared identity")
        labels[check["label"]] = variant
    images, cameras, camera_invariants = [], {}, None
    for index, item in enumerate(manifest["captures"]):
        variant = "present" if index < 5 else "absent"
        condition = index % 5
        gsd = GSDS[condition]
        label = f"{variant}_order_0_condition_{condition}"
        if (item.get("variant") != variant or item.get("target_present") is not (variant == "present")
                or item.get("order_index") != 0 or item.get("condition_index") != condition or item.get("gsd_cm_px") != gsd
                or item.get("artificial_delay_s") != 0 or item.get("parent_scene_hash") != parent
                or item.get("background_scene_hash") != background
                or item.get("resolved_scene_state_hash") != records[variant]["resolved_scene_state_hash"]):
            raise ValueError("Capture source, presence, variant or GSD is inconsistent")
        if (item["annotation_file"] != label + "/annotation.json" or item["yolo_file"] != label + "/labels.txt"
                or json.loads((group / label / "capture.json").read_text()) != item):
            raise ValueError("Condition annotation files/sidecar are inconsistent")
        camera_check = validate_camera_pixels(group, item, state)
        annotation_check = validate_annotation(group, item, state)
        camera = item["camera_condition"]
        if gsd in cameras and camera != cameras[gsd]:
            raise ValueError("Positive/negative camera conditions are not identical")
        cameras[gsd] = camera
        invariant = {key: value for key, value in camera["camera_condition"].items()
                     if key not in ("nominal_gsd_cm_px", "composed_camera_matrix")}
        if camera_invariants is None:
            camera_invariants = invariant
        if invariant != camera_invariants:
            raise ValueError("A camera intrinsic/exposure field changed across GSD conditions")
        expected_labels = [variant + "_after_attach"] + [label + suffix for suffix in ("_before_delay", "_after_delay", "_after_warmup", "_complete")]
        expected_labels.extend(label + f"_probe_{attempt}_{suffix}"
                               for attempt in range(1, len(item["settling_probes"]) + 1) for suffix in ("before", "after"))
        if any(labels.get(name) != variant for name in expected_labels):
            raise ValueError("Capture lacks frozen state/background checks around a delay/warmup/probe")
        images.append({"variant": variant, "target_present": item["target_present"], "gsd_cm_px": gsd,
                       "rgb_file": item["rgb_file"], "rgb_sha256": item["rgb_sha256"],
                       "annotation_file": item["annotation_file"], "annotation_sha256": item["annotation_sha256"],
                       "yolo_file": item["yolo_file"], "yolo_sha256": item["yolo_sha256"],
                       "variant_scene_hash": item["resolved_scene_state_hash"], "parent_scene_hash": parent,
                       "background_scene_hash": background, "camera_condition_hash": camera_check["camera_condition_hash"],
                       "camera_and_pixel_checks": camera_check, "annotation_checks": annotation_check})
    return {"passed": True, "parent_scene_hash": parent, "background_scene_hash": background,
            "state_checks": len(checks), "capture_count": len(images), "images": images,
            "local_dependencies_verified": checked_dependencies,
            "runtime_dependencies_not_inspected": unresolved_dependencies,
            "independent_retained_usd_verification_required": True,
            "annotation_scope": "Owned harbour porpoise only; other demonstration animals are unlabelled background",
            "source_counterfactual_pairing_verified_from_metadata_and_hashes": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8011")
    parser.add_argument("--output", type=Path, required=True, help="New exclusive campaign evidence directory")
    parser.add_argument("--declaration", type=Path, default=DECLARATION, help="Prior approved immutable M7 declaration")
    parser.add_argument("--preflight-only", action="store_true", help="Verify source seals, disk capacity and two read-only marine audits")
    args = parser.parse_args()
    address = urlparse(args.url)
    if (address.scheme not in ("http", "https") or address.hostname not in ("localhost", "127.0.0.1", "::1")
            or address.username or address.password or address.query or address.fragment or address.path not in ("", "/")):
        parser.error("Use a loopback MARLIN URL without credentials, paths or query parameters")
    output = live.safe_path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    declaration_path = live.safe_path(args.declaration)
    token = None
    seals, code_pins, declaration_pin = [], None, None
    report = {"milestone": 7, "passed": False, "preflight_only": args.preflight_only,
              "started_at_utc": datetime.now(timezone.utc).isoformat(), "scene_mutation_attempted": False,
              "biological_approval": False, "milestone_8_started": False, "runs": [], "traceable_images": [],
              "annotation_semantics": "amodal_direct_evaluated_mesh_projection",
              "annotation_scope": "Owned harbour porpoise only; other demonstration animals are unlabelled background",
              "exact_visible_or_refracted_outlines_claimed": False}

    def request(path, payload=None, expect_ok=True, with_http_code=False):
        body = None if payload is None else json.dumps(payload, allow_nan=False).encode()
        req = urllib.request.Request(args.url.rstrip("/") + path, data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=1200) as response:
            value = json.load(response)
            http_code = response.status
        if not isinstance(value, dict) or (expect_ok and value.get("ok") is not True):
            raise ValueError(f"{path}: {live.redact(value, token)}")
        return (value, http_code) if with_http_code else value

    def audit():
        return request("/integration/gama/marine/audit")

    def cleanup_checks(before, after, status):
        checks = live.coexistence(before, after)
        checks.update(layers_restored=before["inspection"]["layers"] == after["inspection"]["layers"],
                      actor_released=status["owned"] is False and status["actor_count"] == 0,
                      private_root_absent=status["root_present_on_active_stage"] is False)
        return checks

    def capture_run(run):
        nonlocal token
        run_output = output / "captures" / run["run_id"]
        run_output.mkdir(parents=True, exist_ok=False)
        result = {"run_id": run["run_id"], "seed": run["seed"], "split": run["split"],
                  "encounter_group_id": run["encounter_group_id"], "passed": False, "groups": []}
        report["runs"].append(result)
        try:
            states, actual_source = verified_run(run["seed"])
            for key in ("source_files", "canonical_state_sha256", "runtime", "actual_execution"):
                if actual_source[key] != run[key]:
                    raise ValueError("Declared actual GAMA execution changed before its replay")
            result["before"] = audit()
            live.require_demo(result["before"])
            result["actor_before"] = request(BASE + "/status")
            if result["actor_before"]["owned"] or result["actor_before"]["root_present_on_active_stage"]:
                raise ValueError("Refusing an existing porpoise owner/private root before trajectory replay")
            result["checkpoint_before_acquire"] = request("/debug/scene/checkpoint", {})
            report["scene_mutation_attempted"] = True
            acquired = request(BASE + "/acquire", {"agent_id": states[0]["agents"][0]["agent_id"]})
            token = acquired["ownership_token"]
            result["acquired"] = live.redact(acquired, token)
            for step in states[:max(STEPS) + 1]:
                applied = request(BASE + "/step", {"ownership_token": token, "step": step})
                if applied.get("applied") is not True or applied.get("duplicate") is not False:
                    raise ValueError("Actual ordered GAMA step was not accepted exactly once")
                index = step["step_index"]
                if index not in STEPS:
                    continue
                capture_output = run_output / f"step_{index:03d}"
                capture_output.mkdir(exist_ok=False)
                group_result = {"run_id": run["run_id"], "step_index": index,
                                "source_state": step, "split": run["split"],
                                "encounter_group_id": run["encounter_group_id"], "passed": False}
                result["groups"].append(group_result)
                print(json.dumps({"event": "capture_started", "run_id": run["run_id"], "step_index": index,
                                  "completed_groups": sum(g["passed"] for r in report["runs"] for g in r["groups"]),
                                  "planned_groups": 15}), flush=True)
                try:
                    group_result["actor_before"] = request(BASE + "/status")
                    group_result["pose_before"] = live.compare_pose(step, group_result["actor_before"], acquired["meters_per_scene_unit"])
                    if (group_result["actor_before"]["accepted_steps"] != index + 1
                            or group_result["actor_before"]["latest"] != step):
                        raise ValueError("Replay failed to stop at the exact predeclared actual GAMA snapshot")
                    group_result["capture_attempts"] = []
                    capture = capture_with_headroom_retry(
                        lambda: request(BASE + "/dataset-capture", {"ownership_token": token}, expect_ok=False, with_http_code=True),
                        lambda: request(BASE + "/status"), step, group_result["actor_before"],
                        acquired["meters_per_scene_unit"], group_result["capture_attempts"], code_pins)
                    group_result["capture_response"] = live.redact(capture, token)
                    if capture.get("directory"):
                        group_result["retained_group"] = live.copy_group(capture["directory"], capture_output)
                    if capture.get("ok") is not True:
                        if group_result.get("retained_group"):
                            raise ValueError("Dataset capture failed; returned group evidence was retained")
                        raise ValueError("Dataset capture failed before returning an evidence group; all responses were retained")
                    if not group_result.get("retained_group"):
                        raise ValueError("Dataset endpoint returned no retained evidence group")
                    if group_result["capture_attempts"][-1].get("held_state_after_response") is not True:
                        raise ValueError("Capture response was retained, but the held GAMA actor could not be verified unchanged")
                    checks = validate_group(capture_output / "group", step, capture)
                    group_result["group_checks"] = checks
                    group_result["actor_after"] = request(BASE + "/status")
                    group_result["capture_attempts"][-1]["status_after_capture"] = group_result["actor_after"]
                    group_result["pose_after"] = live.compare_pose(step, group_result["actor_after"], acquired["meters_per_scene_unit"])
                    group_result["held_state"] = (group_result["actor_after"]["accepted_steps"] == index + 1
                        and group_result["actor_after"]["latest"] == step
                        and group_result["actor_after"]["world_pose"] == group_result["actor_before"]["world_pose"])
                    group_result["capture_attempts"][-1]["held_state_after_capture"] = group_result["held_state"]
                    group_result["during"] = audit()
                    group_result["coexistence_checks"] = live.coexistence(result["before"], group_result["during"])
                    if not group_result["held_state"] or not all(group_result["coexistence_checks"].values()):
                        raise ValueError("Capture changed the held GAMA state or original marine demonstration")
                    for image in checks["images"]:
                        image_record = {"image_id": f"{run['run_id']}__step_{index:03d}__{image['variant']}__gsd_{image['gsd_cm_px']:g}",
                                        "run_id": run["run_id"], "related_run_ids": run["related_run_ids"],
                                        "encounter_group_id": run["encounter_group_id"], "split": run["split"],
                                        "seed": run["seed"], "step_index": index, "simulation_time_s": step["simulation_time_s"],
                                        "original_gama_depth_m": step["agents"][0]["depth_m"],
                                        "behavioural_state": step["agents"][0]["behavioural_state"],
                                        "source_canonical_state_sha256": run["canonical_state_sha256"],
                                        "source_files": run["source_files"], **image}
                        for key in ("rgb_file", "annotation_file", "yolo_file"):
                            image_record[key] = str((capture_output / "group" / image[key]).relative_to(output))
                        image_record["group_manifest"] = str((capture_output / "group/manifest.json").relative_to(output))
                        image_record["group_manifest_sha256"] = live.digest(capture_output / "group/manifest.json")
                        report["traceable_images"].append(image_record)
                    group_result["passed"] = True
                except BaseException as error:
                    group_result["error"] = live.redact(f"{type(error).__name__}: {error}", token)
                    raise
                finally:
                    live.write_json(capture_output / "group_result.json", live.redact(group_result, token))
                    print(json.dumps({"event": "capture_finished", "run_id": run["run_id"], "step_index": index,
                                      "passed": group_result["passed"], "evidence": str(capture_output)}), flush=True)
        except BaseException as error:
            result["error"] = live.redact(f"{type(error).__name__}: {error}", token)
        finally:
            if token is not None:
                try:
                    result["release"] = request(BASE + "/release", {"ownership_token": token})
                except BaseException as error:
                    result["cleanup_error"] = live.redact(f"{type(error).__name__}: {error}", token)
                try:
                    time.sleep(2)
                    result["after_release"] = audit()
                    result["actor_after_release"] = request(BASE + "/status")
                    result["cleanup_checks"] = cleanup_checks(result["before"], result["after_release"], result["actor_after_release"])
                except BaseException as error:
                    result["cleanup_verification_error"] = live.redact(f"{type(error).__name__}: {error}", token)
                result["passed"] = (not result.get("error") and not result.get("cleanup_error")
                    and not result.get("cleanup_verification_error") and len(result["groups"]) == 3
                    and all(group["passed"] for group in result["groups"])
                    and all(result.get("cleanup_checks", {"missing": False}).values()))
            live.write_json(run_output / "run_result.json", live.redact(result, token))
            token = None
        return result["passed"]

    try:
        declaration = validate_declaration(declaration_path)
        declaration_pin = pin(declaration_path)
        report["declaration"] = declaration_pin
        shutil.copyfile(declaration_path, output / "declaration.json")
        if live.digest(output / "declaration.json") != declaration_pin["sha256"]:
            raise ValueError("Retained immutable declaration copy differs from the approved source")
        seals = [load_seal(live.M5_MANIFEST), load_seal(M6_MANIFEST, ALLOWED_M6_DELTAS)]
        report["preservation_before"] = [verify_seal(seal) for seal in seals]
        if not all(check["passed"] for check in report["preservation_before"]):
            raise ValueError("Protected M5/M6 evidence changed before the declared M7 workload")
        code_pins = runtime_code_pins()
        report["runtime_code_before"] = code_pins
        report["disk_preflight"] = disk_preflight(output)
        if not report["disk_preflight"]["passed"]:
            raise ValueError("Insufficient free space for the declared bounded evidence workload")
        report["before"] = audit()
        report["actor_before"] = request(BASE + "/status")
        live.require_demo(report["before"])
        if report["actor_before"]["owned"] or report["actor_before"]["root_present_on_active_stage"]:
            raise ValueError("Refusing an existing porpoise owner/private root")
        if args.preflight_only:
            time.sleep(2)
            report["second_audit"] = audit()
            report["preflight_checks"] = live.coexistence(report["before"], report["second_audit"])
            report["preflight_checks"]["layers_unchanged"] = report["before"]["inspection"]["layers"] == report["second_audit"]["inspection"]["layers"]
            report["passed"] = all(report["preflight_checks"].values())
        else:
            for run in declaration["runs"]:
                if not capture_run(run):
                    raise ValueError("A declared trajectory capture failed; no replacement state/trajectory was selected")
            report["after"] = audit()
            report["actor_after"] = request(BASE + "/status")
            report["cleanup_checks"] = cleanup_checks(report["before"], report["after"], report["actor_after"])
            images = report["traceable_images"]
            present = sum(image["target_present"] for image in images)
            assignments = {}
            for run in declaration["runs"]:
                for related in run["related_run_ids"]:
                    if related in assignments and assignments[related] != run["split"]:
                        raise ValueError("Related trajectories cross declared dataset splits")
                    assignments[related] = run["split"]
            manifest = {"milestone": 7, "declaration": declaration_pin, "split_policy": declaration["split_policy"],
                        "trajectory_assignments": [{"run_id": run["run_id"], "related_run_ids": run["related_run_ids"],
                                                    "encounter_group_id": run["encounter_group_id"], "split": run["split"]}
                                                   for run in declaration["runs"]],
                        "related_run_split_assignments": assignments, "images": images,
                        "target_present_captures": present, "target_absent_captures": len(images) - present,
                        "related_trajectories_cross_splits": False, "biological_approval": False,
                        "annotation_semantics": "amodal_direct_evaluated_mesh_projection",
                        "rendered_visibility": "unknown", "target_class_scope": report["annotation_scope"]}
            live.write_json(output / "trajectory_split_manifest.json", manifest)
            report["trajectory_split_manifest"] = {"path": "trajectory_split_manifest.json", "sha256": live.digest(output / "trajectory_split_manifest.json")}
            report["capture_counts"] = {"target_present": present, "target_absent": len(images) - present,
                                         "groups": sum(len(run["groups"]) for run in report["runs"])}
            report["passed"] = (len(report["runs"]) == 5 and all(run["passed"] for run in report["runs"])
                and present == 75 and len(images) - present == 75 and len({image["image_id"] for image in images}) == 150
                and all(report["cleanup_checks"].values()))
    except BaseException as error:
        report["error"] = live.redact(f"{type(error).__name__}: {error}", token)
        report["passed"] = False
    finally:
        try:
            report["preservation_after"] = [verify_seal(seal) for seal in seals]
            report["runtime_code_after"] = runtime_code_pins() if code_pins is not None else None
            report["runtime_code_unchanged"] = code_pins is not None and report["runtime_code_after"] == code_pins
            report["declaration_unchanged"] = declaration_pin is not None and pin(declaration_path) == declaration_pin
            report["passed"] = (report["passed"] and all(check["passed"] for check in report["preservation_after"])
                and report["runtime_code_unchanged"] and report["declaration_unchanged"])
        except BaseException as error:
            report["preservation_error"] = live.redact(f"{type(error).__name__}: {error}", token)
            report["passed"] = False
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        live.write_json(output / "results.json", live.redact(report, token))
    print(json.dumps({"event": "campaign_finished", "passed": report["passed"],
                      "preflight_only": args.preflight_only, "results": str(output / "results.json"),
                      "capture_counts": report.get("capture_counts"), "error": report.get("error")}), flush=True)
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
