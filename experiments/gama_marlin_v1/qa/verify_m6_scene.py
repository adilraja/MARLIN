"""Independently verify retained M6 USD and camera records without Kit.

Run with the installed Blender USD Python and -B. This script reads retained
files and creates exactly one exclusive JSON result. It never opens generated
runtime dependencies, attaches a stage, renders, or edits the retained scene.
"""
import argparse
import hashlib
import importlib
import json
import math
from pathlib import Path
import struct
import sys
import types

from pxr import Gf, Sdf, Usd, UsdGeom

ROOT = Path(__file__).resolve().parents[3]
BRIDGE = ROOT / "source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge"
SERVICE = ROOT / "source/extensions/cris.madil.render_service/cris/madil/render_service"
CAMERA = "/MarlinGamaPairCamera"
MATRIX_ABS_TOLERANCE = 1e-7
OPTICS_REL_TOLERANCE = 1e-6
BLOCKED_PARTS = {"_build", "extscache", "__pycache__", ".cache"}


def _package(name, path):
    package = types.ModuleType(name)
    package.__path__ = [str(path)]
    sys.modules[name] = package
    return name


identity = importlib.import_module(_package("_m6_retained_bridge", BRIDGE) + ".paired_state_v2")
geometry = importlib.import_module(_package("_m6_retained_geometry", SERVICE) + ".calibration_geometry")


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def read(path):
    return json.loads(path.read_text())


def _matrix_error(actual, expected):
    if len(actual) != 4 or any(len(row) != 4 for row in actual):
        raise ValueError("Expected a retained 4 by 4 USD matrix")
    if any(type(value) not in (int, float) or not math.isfinite(value) for row in actual for value in row):
        raise ValueError("Retained projection matrices must be finite")
    return max(abs(actual[i][j] - expected[i][j]) for i in range(4) for j in range(4))


def _safe_child(group, value):
    path = (group / value).resolve()
    if not path.is_relative_to(group):
        raise ValueError("Capture paths must stay inside their retained group")
    return path


def _dependency_checks(dependencies):
    records = []
    for item in dependencies:
        if item.get("sha256") is None:
            if item.get("status") != "runtime_or_unresolved":
                raise ValueError("Unhashed dependency lacks explicit unresolved/runtime status")
            records.append({"path": item["path"], "status": item["status"],
                            "bytes_read": False, "content_verified": False})
            continue
        path = Path(item["path"])
        path = (ROOT / path).resolve() if not path.is_absolute() else path.resolve()
        if set(path.parts) & BLOCKED_PARTS or path.suffix == ".pyc":
            raise ValueError("Refusing to inspect a dependency in a generated/runtime directory")
        actual = digest(path)
        if actual != item["sha256"]:
            raise ValueError("Local dependency bytes changed: " + item["path"])
        records.append({"path": item["path"], "resolved_local_path": str(path),
                        "status": "local_hashed", "expected_sha256": item["sha256"],
                        "before_sha256": actual, "bytes_read": True})
    return records


def verify(group):
    manifest_path = group / "manifest.json"
    retained_path = group / "resolved_state.json"
    scene_path = group / "source_scene.usdc"
    manifest, retained = read(manifest_path), read(retained_path)
    result = {"kind": "m6_independent_retained_scene_verification", "passed": False,
              "runtime": {"python": sys.version, "usd_version": list(Usd.GetVersion())},
              "group": str(group), "verifier_sha256": digest(Path(__file__).resolve()),
              "inputs": {"manifest_sha256": digest(manifest_path), "resolved_state_sha256": digest(retained_path),
                         "source_scene_sha256": digest(scene_path)},
              "tolerances": {"matrix_max_abs": MATRIX_ABS_TOLERANCE, "optics_relative": OPTICS_REL_TOLERANCE},
              "checks": {}, "captures": []}
    try:
        if not manifest.get("passed") or manifest.get("recovery_required") or not manifest.get("all_state_hashes_equal"):
            raise ValueError("The retained transaction did not pass capture and restoration")
        result["checks"]["source_scene_file_hash"] = result["inputs"]["source_scene_sha256"] == manifest["source_scene_sha256"]
        if not result["checks"]["source_scene_file_hash"]:
            raise ValueError("Retained source_scene.usdc file hash mismatch")
        expected_hash = retained["resolved_scene_state_hash"]
        if expected_hash != manifest["resolved_scene_state_hash"]:
            raise ValueError("Retained resolved-state and capture-manifest hashes disagree")
        if retained["identity"]["gama_source_state"] != manifest["source_state"] or retained["identity"]["environment_clock"] != manifest["environment_clock"]:
            raise ValueError("Retained scene source state or environment clock disagrees with manifest")
        dependencies = retained["identity"]["dependencies"]
        if sorted(dependencies, key=lambda item: item["path"]) != sorted(manifest["dependencies"], key=lambda item: item["path"]):
            raise ValueError("Retained dependency records disagree")
        result["dependency_checks"] = _dependency_checks(dependencies)
        layer = Sdf.Layer.OpenAsAnonymous(str(scene_path))
        if layer is None:
            raise ValueError("Could not open retained USD into a private layer")
        stage = Usd.Stage.Open(layer)
        if stage is None:
            raise ValueError("Could not compose the privately opened retained USD")
        result["checks"]["zero_retained_time_samples"] = not list(layer.ListAllTimeSamples())
        if not result["checks"]["zero_retained_time_samples"]:
            raise ValueError("Retained scene still contains time samples")
        source_before = layer.ExportToString()
        fields = retained["identity"]
        recomputed = identity.resolved_record(stage, manifest["source_state"], fields["renderer_settings"], dependencies, manifest["environment_clock"])
        result["recomputed_resolved_scene_state_hash"] = recomputed["resolved_scene_state_hash"]
        result["checks"]["retained_identity_exact"] = recomputed["identity"] == retained["identity"]
        result["checks"]["retained_hash_exact"] = recomputed["resolved_scene_state_hash"] == expected_hash
        if not result["checks"]["retained_identity_exact"] or not result["checks"]["retained_hash_exact"]:
            result["identity_different_top_level_fields"] = [key for key in recomputed["identity"] if recomputed["identity"].get(key) != retained["identity"].get(key)]
            raise ValueError("Recomputed retained USD identity differs from capture-time identity")
        if len(manifest["captures"]) != 10 or len(manifest["captures"]) != sum(len(order) for order in manifest["orders"]):
            raise ValueError("Expected the declared ten-condition acceptance group")
        protocol = manifest["protocol"]
        resolution = protocol["image_resolution"]
        anchor = protocol["camera_anchor_xz_m"]
        plane = protocol["reference_plane_y_m"]
        environment_path = ROOT / "experiments/gsd_pilot_v1/environment.json"
        exposure = read(environment_path)["camera_exposure_attributes"]
        result["inputs"]["pilot_environment_sha256"] = digest(environment_path)
        camera_positions = []
        for item in manifest["captures"]:
            folder = group / f"order_{item['order_index']}_condition_{item['condition_index']}"
            if read(folder / "capture.json") != item:
                raise ValueError("Per-capture metadata differs from group manifest")
            if item["resolved_scene_state_hash"] != expected_hash or item.get("render_product_camera_verified") is not True:
                raise ValueError("Capture lacks the expected frozen-state or camera-delivery identity")
            gsd = item["gsd_cm_px"]
            if gsd != manifest["orders"][item["order_index"]][item["condition_index"]]:
                raise ValueError("Capture condition order differs from declared order")
            private = Usd.Stage.Open(stage.Flatten(False))
            config = geometry.CalibrationConfig(meters_per_scene_unit=UsdGeom.GetStageMetersPerUnit(private),
                image_width_px=resolution[0], image_height_px=resolution[1],
                focal_length_mm=protocol["focal_length_mm"], pixel_pitch_um=protocol["pixel_pitch_um"],
                height_above_target_m=gsd * 100, target_plane_y_m=plane,
                target_width_m=2, target_height_m=1)
            camera = geometry.build_camera(private, config, CAMERA, (anchor[0], 0, anchor[1]))
            camera.CreateClippingRangeAttr(Gf.Vec2f(1, 100000))
            for name, value in exposure.items():
                camera.GetPrim().CreateAttribute(name, Sdf.ValueTypeNames.Float).Set(value)
            condition = identity.camera_condition(private, CAMERA, gsd, [anchor[0], plane, anchor[1]], plane, resolution)
            if condition != item["camera_condition"]:
                raise ValueError("Independently reconstructed camera condition/hash differs")
            frustum = camera.GetCamera(Usd.TimeCode.Default()).frustum
            computed_view = [list(row) for row in frustum.ComputeViewMatrix()]
            computed_projection = [list(row) for row in frustum.ComputeProjectionMatrix()]
            errors = []
            for name in ("projection_before_capture", "projection_after_capture"):
                projection = item[name]
                product = projection["render_product"]
                if product["camera"] != CAMERA or product["resolution"] != resolution or projection["actual_viewport_resolution"] != resolution:
                    raise ValueError("Retained render product camera or resolution differs")
                if product["pixel_aspect_ratio"] not in (None, 1) or product["data_window_ndc"] not in (None, [0, 0, 1, 1]):
                    raise ValueError("Retained render product cropped or stretched the image")
                for field, matrix in (("capture_view_matrix", computed_view), ("actual_view_matrix", computed_view),
                                      ("capture_projection_matrix", computed_projection), ("actual_projection_matrix", computed_projection)):
                    error = _matrix_error(projection[field], matrix)
                    errors.append(error)
                    if error > MATRIX_ABS_TOLERANCE:
                        raise ValueError("Independently computed USD projection differs: " + field)
            optics = condition["camera_condition"]
            matrix = optics["composed_camera_matrix"]
            camera_positions.append(matrix[3][:3])
            height = matrix[3][1] * optics["meters_per_scene_unit"] - plane
            measured_gsd = [100 * height * optics[aperture] / optics["focal_length"] / pixels
                            for aperture, pixels in (("horizontal_aperture", resolution[0]), ("vertical_aperture", resolution[1]))]
            if any(not math.isclose(value, gsd, rel_tol=OPTICS_REL_TOLERANCE, abs_tol=1e-8) for value in measured_gsd):
                raise ValueError("Reconstructed actual camera GSD differs from its condition")
            after = identity.resolved_record(private, manifest["source_state"], fields["renderer_settings"], dependencies, manifest["environment_clock"])
            if after["resolved_scene_state_hash"] != expected_hash:
                raise ValueError("A reconstructed camera variant changed physical scene identity")
            rgb = _safe_child(group, item["rgb_file"])
            if digest(rgb) != item["rgb_sha256"]:
                raise ValueError("Retained RGB hash differs")
            with rgb.open("rb") as stream:
                header = stream.read(24)
            if header[:8] != b"\x89PNG\r\n\x1a\n" or struct.unpack(">II", header[16:24]) != tuple(resolution):
                raise ValueError("Retained RGB dimensions differ from camera metadata")
            result["captures"].append({"order_index": item["order_index"], "condition_index": item["condition_index"],
                "gsd_cm_px": gsd, "camera_condition_hash": condition["camera_condition_hash"],
                "resolved_scene_state_hash": after["resolved_scene_state_hash"],
                "maximum_projection_matrix_error": max(errors), "measured_reference_gsd_xy_cm_px": measured_gsd,
                "rgb_sha256": digest(rgb), "passed": True})
        result["checks"]["only_camera_y_varied"] = all(position[0] == camera_positions[0][0] and position[2] == camera_positions[0][2] for position in camera_positions)
        result["checks"]["all_ten_camera_variants_preserved_identity"] = len(result["captures"]) == 10
        result["checks"]["private_source_unchanged"] = layer.ExportToString() == source_before
        for item in result["dependency_checks"]:
            if item["bytes_read"]:
                actual = digest(Path(item["resolved_local_path"]))
                item.update(after_sha256=actual, content_verified=actual == item["before_sha256"] == item["expected_sha256"])
                if not item["content_verified"]:
                    raise ValueError("A local dependency changed during independent verification")
        result["checks"]["all_local_dependency_hashes_before_after"] = all(item["content_verified"] for item in result["dependency_checks"] if item["bytes_read"])
        result["unresolved_dependency_limitation"] = {"paths": retained["unresolved_dependencies"],
            "bytes_inspected": False, "note": "Runtime/unresolved dependencies remained explicitly unverified; generated runtime files were not opened"}
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
        raise ValueError("Output already exists; choose a new result path")
    result = verify(args.group.resolve())
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": result["passed"], "captures_verified": len(result["captures"]),
                      "output": str(args.output), "error": result.get("error")}, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
