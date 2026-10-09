"""Recompose retained M7 pairs and verify camera, removal and amodal labels.

Run with installed Blender USD Python and -B. Retained stages are opened into
private layers. Only one exclusive verification JSON is written; no Kit or
renderer is imported and no captured or generated-runtime file is modified.
"""
import argparse
import importlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import sys

from pxr import Gf, Sdf, Usd, UsdGeom

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("_m7_existing_scene_verification", Path(__file__).with_name("verify_m6_scene.py"))
existing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(existing)
paired = existing.identity
geometry = existing.geometry
dataset = importlib.import_module("_m6_retained_bridge.dataset_state_v2")
projection_module = importlib.import_module("_m6_retained_geometry.capture_projection")
for name in ("cris", "cris.madil", "cris.madil.render_service"):
    if name not in sys.modules:
        existing._package(name, existing.SERVICE)
sys.modules["cris.madil.render_service.capture_projection"] = projection_module

POSITION_TOLERANCE_M = 1e-5
HEADING_TOLERANCE_DEG = 1e-4


def _private(path):
    layer = Sdf.Layer.OpenAsAnonymous(str(path))
    stage = Usd.Stage.Open(layer) if layer is not None else None
    if stage is None:
        raise ValueError("Could not privately open retained USD: " + str(path))
    if layer.ListAllTimeSamples():
        raise ValueError("Retained variant contains time samples")
    return stage


def verify(group):
    manifest_path = group / "manifest.json"
    manifest = existing.read(manifest_path)
    result = {"kind": "m7_independent_retained_group_verification", "passed": False,
              "runtime": {"python": sys.version, "usd_version": list(Usd.GetVersion())},
              "group": str(group), "verifier_sha256": existing.digest(Path(__file__).resolve()),
              "reused_m6_verifier_sha256": existing.digest(Path(__file__).with_name("verify_m6_scene.py")),
              "helper_source_sha256": {name: existing.digest(path) for name, path in {
                  "dataset_state_v2": Path(dataset.__file__), "paired_state_v2": Path(paired.__file__),
                  "calibration_geometry": Path(geometry.__file__), "capture_projection": Path(projection_module.__file__)
              }.items()},
              "inputs": {"manifest_sha256": existing.digest(manifest_path)}, "checks": {}, "captures": [],
              "tolerances": {"position_m": POSITION_TOLERANCE_M, "heading_deg": HEADING_TOLERANCE_DEG,
                             "matrix_max_abs": existing.MATRIX_ABS_TOLERANCE, "optics_relative": existing.OPTICS_REL_TOLERANCE}}
    try:
        if manifest.get("milestone") != 7 or not manifest.get("passed") or manifest.get("recovery_required") or not manifest.get("all_variant_state_checks_match"):
            raise ValueError("The retained M7 transaction did not pass capture/restoration")
        if manifest["orders"] != [[.5, 1, 2, 3, 4]] or len(manifest["captures"]) != 10:
            raise ValueError("Expected five positive and five physically removed conditions")
        retained = {"present": existing.read(group / "resolved_state.json"),
                    "absent": existing.read(group / "absent_resolved_state.json")}
        result["inputs"].update(resolved_state_sha256=existing.digest(group / "resolved_state.json"),
                                  absent_resolved_state_sha256=existing.digest(group / "absent_resolved_state.json"))
        if retained != manifest["variant_records"]:
            raise ValueError("Retained variant identity files differ from manifest")
        state, clock = manifest["source_state"], manifest["environment_clock"]
        positive_hash = retained["present"]["resolved_scene_state_hash"]
        if manifest["parent_scene_hash"] != positive_hash or manifest["resolved_scene_state_hash"] != positive_hash:
            raise ValueError("Positive parent identity differs across records")
        fields = retained["present"]["identity"]
        renderer, dependencies = fields["renderer_settings"], fields["dependencies"]
        if fields["gama_source_state"] != state or fields["environment_clock"] != clock:
            raise ValueError("Manifest GAMA state or environment clock differs from positive identity")
        if sorted(manifest["dependencies"], key=lambda item: item["path"]) != dependencies:
            raise ValueError("Manifest does not preserve the common positive dependency records")
        result["dependency_checks"] = existing._dependency_checks(dependencies)
        stages = {}
        original_serializations = {}
        for variant in ("present", "absent"):
            file_record = manifest["variant_scene_files"][variant]
            scene_path = existing._safe_child(group, file_record["file"])
            actual = existing.digest(scene_path)
            if actual != file_record["sha256"]:
                raise ValueError("Retained variant USD bytes differ: " + variant)
            result["inputs"][variant + "_scene_sha256"] = actual
            stage = _private(scene_path)
            stages[variant] = stage
            original_serializations[variant] = stage.GetRootLayer().ExportToString()
            recomputed = dataset.variant_record(stage, state, renderer, dependencies, clock,
                                               variant == "present", positive_hash)
            if recomputed != retained[variant]:
                raise ValueError("Recomputed variant identity/hash differs: " + variant)
            background = dataset.background_record(stage, state, renderer, dependencies, clock)
            if background["background_hash"] != manifest["background_scene_hash"]:
                raise ValueError("Recomputed background identity differs: " + variant)
            result["checks"][variant + "_identity_exact"] = True
            result["checks"][variant + "_background_exact"] = True
            result["checks"][variant + "_zero_time_samples"] = True
        if result["inputs"]["present_scene_sha256"] != manifest["source_scene_sha256"]:
            raise ValueError("Positive scene file disagrees with the source-scene hash")
        result["checks"]["positive_source_scene_file_hash"] = True
        positive, negative = stages["present"], stages["absent"]
        if not positive.GetPrimAtPath(dataset.TARGET_ACTOR) or negative.GetPrimAtPath(dataset.TARGET_ROOT) or negative.GetPrimAtPath(dataset.TARGET_ACTOR):
            raise ValueError("Retained target presence/removal is incorrect")
        expected_negative = Usd.Stage.Open(positive.Flatten(False))
        if not expected_negative.RemovePrim(dataset.TARGET_ROOT):
            raise ValueError("Could not independently apply the exact target-removal operation")
        if paired.source_content_hash(expected_negative) != paired.source_content_hash(negative):
            raise ValueError("Negative physical USD changed more than the owned root removal")
        result["checks"]["only_owned_target_root_removed"] = True
        actual_removal = manifest["target_removal"]
        independently_prepared = dataset.prepare_variants(positive, state, renderer, dependencies, clock)
        if independently_prepared["removal_record"] != actual_removal:
            raise ValueError("Retained removal counts/root paths/source binding differ")
        result["checks"]["removal_record_exact"] = True
        actor = positive.GetPrimAtPath(dataset.TARGET_ACTOR)
        matrix = UsdGeom.Xformable(actor).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        units = UsdGeom.GetStageMetersPerUnit(positive)
        agent = state["agents"][0]
        position = [float(value) * units for value in matrix.ExtractTranslation()]
        expected_position = [agent["horizontal_position_m"][0], -agent["depth_m"], agent["horizontal_position_m"][1]]
        position_error = math.dist(position, expected_position)
        forward = matrix.TransformDir(Gf.Vec3d(0, 0, 1))
        heading = math.degrees(math.atan2(forward[0], forward[2])) % 360
        heading_error = abs((heading - agent["heading_deg"] + 180) % 360 - 180)
        if position_error > POSITION_TOLERANCE_M or heading_error > HEADING_TOLERANCE_DEG:
            raise ValueError("The retained actual actor pose differs from source GAMA state")
        result["source_pose_measurement"] = {"position_m": position, "heading_deg": heading,
                                             "position_error_m": position_error, "heading_error_deg": heading_error,
                                             "original_gama_depth_m": agent["depth_m"]}
        result["checks"]["positive_actual_gama_pose"] = True
        protocol = manifest["protocol"]
        resolution, anchor, plane = protocol["image_resolution"], protocol["camera_anchor_xz_m"], protocol["reference_plane_y_m"]
        exposure_path = ROOT / "experiments/gsd_pilot_v1/environment.json"
        exposure = existing.read(exposure_path)["camera_exposure_attributes"]
        result["inputs"]["pilot_environment_sha256"] = existing.digest(exposure_path)
        pairs = {}
        camera_positions = []
        for item in manifest["captures"]:
            variant, condition_index = item["variant"], item["condition_index"]
            folder = group / f"{variant}_order_{item['order_index']}_condition_{condition_index}"
            if existing.read(folder / "capture.json") != item:
                raise ValueError("Per-capture metadata differs from group manifest")
            if item["target_present"] != (variant == "present") or item["resolved_scene_state_hash"] != retained[variant]["resolved_scene_state_hash"]:
                raise ValueError("Capture target-presence or variant-state identity differs")
            if item["parent_scene_hash"] != positive_hash or item["background_scene_hash"] != manifest["background_scene_hash"] or item.get("render_product_camera_verified") is not True:
                raise ValueError("Capture lacks parent/background/camera-delivery binding")
            gsd = item["gsd_cm_px"]
            if item["order_index"] != 0 or gsd != manifest["orders"][0][condition_index]:
                raise ValueError("Capture order differs from declared five-GSD workload")
            private = Usd.Stage.Open(stages[variant].Flatten(False))
            config = geometry.CalibrationConfig(meters_per_scene_unit=units, image_width_px=resolution[0],
                image_height_px=resolution[1], focal_length_mm=protocol["focal_length_mm"],
                pixel_pitch_um=protocol["pixel_pitch_um"], height_above_target_m=gsd * 100,
                target_plane_y_m=plane, target_width_m=2, target_height_m=1)
            camera = geometry.build_camera(private, config, existing.CAMERA, (anchor[0], 0, anchor[1]))
            camera.CreateClippingRangeAttr(Gf.Vec2f(1, 100000))
            for name, value in exposure.items():
                camera.GetPrim().CreateAttribute(name, Sdf.ValueTypeNames.Float).Set(value)
            condition = paired.camera_condition(private, existing.CAMERA, gsd, [anchor[0], plane, anchor[1]], plane, resolution)
            if condition != item["camera_condition"]:
                raise ValueError("Reconstructed camera condition differs from retained condition")
            pairs.setdefault(gsd, {})[variant] = condition["camera_condition_hash"]
            optics = condition["camera_condition"]
            camera_matrix = optics["composed_camera_matrix"]
            camera_positions.append(camera_matrix[3][:3])
            height_m = camera_matrix[3][1] * optics["meters_per_scene_unit"] - plane
            measured_gsd = [100 * height_m * optics[aperture] / optics["focal_length"] / pixels
                            for aperture, pixels in (("horizontal_aperture", resolution[0]), ("vertical_aperture", resolution[1]))]
            if any(not math.isclose(value, gsd, rel_tol=existing.OPTICS_REL_TOLERANCE, abs_tol=1e-8) for value in measured_gsd):
                raise ValueError("Reconstructed actual camera GSD differs from its declared condition")
            frustum = camera.GetCamera(Usd.TimeCode.Default()).frustum
            view = [list(row) for row in frustum.ComputeViewMatrix()]
            projection = [list(row) for row in frustum.ComputeProjectionMatrix()]
            maximum_error = 0
            for name in ("projection_before_capture", "projection_after_capture"):
                metadata = item[name]
                product = metadata["render_product"]
                if product["camera"] != existing.CAMERA or product["resolution"] != resolution or metadata["actual_viewport_resolution"] != resolution:
                    raise ValueError("Actual retained render product differs from reconstructed camera")
                if product["pixel_aspect_ratio"] not in (None, 1) or product["data_window_ndc"] not in (None, [0, 0, 1, 1]):
                    raise ValueError("Retained render product cropped or stretched the image")
                for field, expected in (("capture_view_matrix", view), ("actual_view_matrix", view),
                                        ("capture_projection_matrix", projection), ("actual_projection_matrix", projection)):
                    error = existing._matrix_error(metadata[field], expected)
                    maximum_error = max(maximum_error, error)
                    if error > existing.MATRIX_ABS_TOLERANCE:
                        raise ValueError("Independent USD projection differs from retained metadata")
            labels = dataset.annotation(private, item["projection_after_capture"], state, variant == "present")
            annotation_path, label_path = existing._safe_child(group, item["annotation_file"]), existing._safe_child(group, item["yolo_file"])
            if existing.digest(annotation_path) != item["annotation_sha256"] or existing.digest(label_path) != item["yolo_sha256"]:
                raise ValueError("Retained annotation or YOLO file hash differs")
            if existing.read(annotation_path) != labels["annotation"] or item["annotation"] != labels["annotation"] or label_path.read_text() != labels["yolo_label"]:
                raise ValueError("Recomputed actual mesh annotation or YOLO text differs")
            if variant == "absent" and (labels["yolo_label"] or labels["annotation"]["amodal_bbox_xyxy_px"] is not None):
                raise ValueError("A physically removed counterpart has a target label")
            if labels["annotation"]["original_gama_depth_m"] != agent["depth_m"] or labels["annotation"]["rendered_visibility"] != "unknown":
                raise ValueError("Annotation lost original depth or implied rendered visibility")
            current = dataset.variant_record(private, state, renderer, dependencies, clock, variant == "present", positive_hash)
            if current["resolved_scene_state_hash"] != retained[variant]["resolved_scene_state_hash"]:
                raise ValueError("Camera reconstruction changed the physical variant identity")
            rgb = existing._safe_child(group, item["rgb_file"])
            if existing.digest(rgb) != item["rgb_sha256"]:
                raise ValueError("Retained RGB file hash differs")
            with rgb.open("rb") as stream:
                header = stream.read(24)
            if header[:8] != b"\x89PNG\r\n\x1a\n" or struct.unpack(">II", header[16:24]) != tuple(resolution):
                raise ValueError("Retained RGB dimensions differ")
            result["captures"].append({"variant": variant, "target_present": variant == "present",
                "gsd_cm_px": gsd, "camera_condition_hash": condition["camera_condition_hash"],
                "resolved_scene_state_hash": current["resolved_scene_state_hash"],
                "background_scene_hash": manifest["background_scene_hash"], "maximum_projection_matrix_error": maximum_error,
                "measured_reference_gsd_xy_cm_px": measured_gsd,
                "rgb_sha256": item["rgb_sha256"], "annotation_sha256": item["annotation_sha256"], "yolo_sha256": item["yolo_sha256"],
                "vertex_count": labels["annotation"]["vertex_count"], "annotation_status": labels["annotation"]["annotation_status"], "passed": True})
        result["checks"]["five_exact_camera_condition_pairs"] = len(pairs) == 5 and all(pair.get("present") == pair.get("absent") for pair in pairs.values())
        result["checks"]["only_camera_y_varied"] = all(position[0] == camera_positions[0][0] and position[2] == camera_positions[0][2] for position in camera_positions)
        result["checks"]["all_ten_actual_annotations_and_images"] = len(result["captures"]) == 10
        result["checks"]["retained_private_sources_unchanged"] = all(stages[name].GetRootLayer().ExportToString() == original_serializations[name] for name in stages)
        for item in result["dependency_checks"]:
            if item["bytes_read"]:
                actual = existing.digest(Path(item["resolved_local_path"]))
                item.update(after_sha256=actual, content_verified=actual == item["before_sha256"] == item["expected_sha256"])
                if not item["content_verified"]:
                    raise ValueError("Local dependency changed during retained-group verification")
        result["checks"]["all_local_dependency_hashes_before_after"] = all(item["content_verified"] for item in result["dependency_checks"] if item["bytes_read"])
        result["unresolved_dependency_limitation"] = {"paths": retained["present"]["unresolved_dependencies"],
            "bytes_inspected": False, "note": "Generated/runtime dependencies were not opened; recorded unresolved limitation remained explicit"}
        result["passed"] = all(result["checks"].values())
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Output exists; choose a new exclusive result path")
    result = verify(args.group.resolve())
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": result["passed"], "captures_verified": len(result["captures"]),
                      "output": str(args.output), "error": result.get("error")}, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
