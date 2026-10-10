"""Measure the copied USD and prepare bounded recovery evidence, without Kit."""
import ast
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

from pxr import Sdf, Usd, UsdGeom

OUTPUT = Path(__file__).resolve().parent
REPO = OUTPUT.parents[3]
BACKUP = OUTPUT.parent / "memory_reclaim_01"
SERVICE = REPO / "source/extensions/cris.madil.render_service/cris/madil/render_service"


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def literal_ocean_configuration(path):
    tree = ast.parse(path.read_text())
    function = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                    and node.name == "apply_demonstration_environment")
    call = next(node for node in ast.walk(function) if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name) and node.func.id == "OceanAnimationDataModel")
    return {keyword.arg: ast.literal_eval(keyword.value) for keyword in call.keywords}, call.lineno


def main():
    destination = OUTPUT / "recovery_payloads.json"
    if destination.exists():
        raise ValueError("Existing recovery payload evidence cannot be overwritten")
    checkpoint_record_path = BACKUP / "checkpoint_result.json"
    scene = BACKUP / "checkpoint_snapshot/scene.usdc"
    metadata_path = BACKUP / "checkpoint_snapshot/metadata.json"
    saved = json.loads(checkpoint_record_path.read_text())
    metadata = json.loads(metadata_path.read_text())
    original_scene_sha = sha(scene)
    if original_scene_sha != metadata["scene_sha256"] or original_scene_sha != saved["checkpoint_response"]["scene_sha256"]:
        raise ValueError("Copied checkpoint hash differs from the preserved API record")
    layer = Sdf.Layer.OpenAsAnonymous(str(scene))
    stage = Usd.Stage.Open(layer, Usd.Stage.LoadNone)
    if stage is None or not layer.anonymous:
        raise ValueError("Copied checkpoint did not open in a private USD layer")
    if stage.GetPrimAtPath("/MarlinGamaPorpoise"):
        raise ValueError("Unexpected private porpoise root in recovery checkpoint")
    animals = saved["before"]["swimming"]["animals"]
    if len(animals) != 11:
        raise ValueError("Expected exactly eleven preserved gallery controllers")
    respawns = []
    for animal in animals:
        root = stage.GetPrimAtPath(animal["prim_path"])
        model = stage.GetPrimAtPath(animal["prim_path"] + "/Model")
        if not root or not model:
            raise ValueError("Checkpoint omitted a gallery root or model")
        scale = list(root.GetAttribute("xformOp:scale").Get())
        if len(scale) != 3 or not scale[0] == scale[1] == scale[2] or scale[0] <= 0:
            raise ValueError("Existing spawn API requires positive uniform scale")
        asset = REPO / "assets/cetaceans" / animal["species"] / "usd" / (animal["species"] + ".usd")
        if not asset.is_file():
            raise ValueError("Canonical gallery asset is missing: " + animal["species"])
        payload = {"name": animal["name"], "asset_path": str(asset),
                   "position": list(root.GetAttribute("xformOp:translate").Get()),
                   "rotation": list(root.GetAttribute("xformOp:rotateXYZ").Get()),
                   "model_rotation": list(model.GetAttribute("xformOp:rotateXYZ").Get()),
                   "scale": scale[0]}
        matrix = UsdGeom.Xformable(root).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        position = list(matrix.ExtractTranslation())
        if any(abs(a - b) > 1e-9 for a, b in zip(position, payload["position"])):
            raise ValueError("Composed root position differs from spawn translation")
        respawns.append({"method": "POST", "endpoint": "/scene/cetacean/spawn", "payload": payload,
                         "species": animal["species"], "canonical_asset_exists": True,
                         "measurement": {"root_path": animal["prim_path"],
                                         "composed_root_matrix": [list(row) for row in matrix],
                                         "composed_root_position": position,
                                         "root_scale_xyz": scale,
                                         "position_source": "Measured from privately reopened copied checkpoint USD, not the earlier moving live audit"}})

    fixed, fixed_line = literal_ocean_configuration(SERVICE / "survey_environment.py")
    ocean_payload = {"name": "Ocean", **fixed, "position": [0.0, 0.0, 0.0]}
    if fixed["wave_height"] != 5 or fixed["wave_length"] != 650:
        raise ValueError("The established demonstration wave configuration changed")
    m4_path = OUTPUT.parent / "m4_live_01/results.json"
    m4 = json.loads(m4_path.read_text())
    actual_setup = m4["demo_setup"][0]
    if actual_setup["ok"] is not True or actual_setup["results"]["ocean"]["ok"] is not True:
        raise ValueError("Actual original demonstration setup was unsuccessful")
    actual_ocean = actual_setup["results"]["ocean"]
    for key in ("size", "resolution", "speed", "target_fps"):
        if actual_ocean[key] != fixed[key] or saved["before"]["ocean"][key] != fixed[key]:
            raise ValueError("Recorded original/current ocean configuration differs")
    if saved["before"]["ocean"]["choppiness"] != fixed["choppiness"]:
        raise ValueError("Recorded ocean choppiness differs from fixed demonstration")
    ocean_source = SERVICE / "ocean.py"
    ocean_tree = ast.parse(ocean_source.read_text())
    start = next(node for node in ocean_tree.body if isinstance(node, ast.AsyncFunctionDef)
                 and node.name == "start_ocean_animation")
    assignments = {target.id: node for node in ast.walk(start) if isinstance(node, ast.Assign)
                   for target in node.targets if isinstance(target, ast.Name)}
    if (ast.unparse(assignments["amplitude"].value) != "data.wave_height * amplitude_factor"
            or ast.unparse(assignments["wavelength"].value) != "data.wave_length * wavelength_factor"):
        raise ValueError("Animated ocean no longer derives waves from height and wavelength")
    definitions = ast.literal_eval(assignments["definitions"].value)
    components = []
    for dx, dz, amplitude_factor, wavelength_factor, phase, phase_rate in definitions:
        length = math.hypot(dx, dz)
        components.append({"dx": dx / length, "dz": dz / length,
                           "amplitude": fixed["wave_height"] * amplitude_factor,
                           "wavelength": fixed["wave_length"] * wavelength_factor,
                           "k": 2 * math.pi / (fixed["wave_length"] * wavelength_factor),
                           "phase": phase, "phase_rate": phase_rate})
    samples = next(node for node in ocean_tree.body if isinstance(node, ast.FunctionDef)
                   and node.name == "_sample_animated_ocean_point")
    sample_code = ast.unparse(samples)
    if "amplitude * sin_theta" not in sample_code or "k * (dx * x + dz * z)" not in sample_code:
        raise ValueError("Animated ocean evaluator does not use wave amplitude/wavenumber")
    common_keys = ("depth", "speed", "travel_half_extent", "deformation_fps")
    common = {key: animals[0][key] for key in common_keys}
    if any(any(animal[key] != common[key] for key in common_keys) for animal in animals):
        raise ValueError("Existing gallery endpoint cannot resume unequal common configurations")
    gallery_payload = {**common, "activate_viewport_camera": False}
    varying = {"z", "direction", "heading", "model_yaw"}
    expected_controllers = {animal["name"]: {key: value for key, value in animal.items() if key not in varying}
                            for animal in animals}
    report = {
        "schema_version": 1, "kind": "measured_checkpoint_controller_restart_plan", "usable": True, "passed": True,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "inspection_command": [sys.executable, "-B", str(Path(__file__).resolve())],
        "kit_imported": False, "kit_stage_attached": False, "renderer_created": False,
        "live_scene_mutated": False, "controller_phase_recovery_claimed": False,
        "checkpoint_id": saved["checkpoint_response"]["checkpoint_id"],
        "copied_checkpoint_scene": str(scene), "copied_checkpoint_scene_sha256": original_scene_sha,
        "copied_checkpoint_metadata_sha256": sha(metadata_path),
        "checkpoint_record_sha256": sha(checkpoint_record_path),
        "restore": {"method": "POST", "endpoint": "/debug/scene/checkpoint/" + saved["checkpoint_response"]["checkpoint_id"] + "/restore", "payload": {}},
        "animals": [entry["payload"] for entry in respawns],
        "ocean": ocean_payload,
        "gallery": gallery_payload,
        "respawn_animals": respawns,
        "ocean_restart": {"method": "POST", "endpoint": "/scene/ocean/animation/start", "payload": ocean_payload},
        "gallery_restart": {"method": "POST", "endpoint": "/scene/cetaceans/gallery/swim/start", "payload": gallery_payload},
        "expected_camera": metadata["camera"], "expected_resolution": metadata["resolution"],
        "expected_fill_frame": metadata["fill_frame"],
        "expected_renderer_settings": metadata["renderer_settings"],
        "expected_stable_scene_attributes": saved["before"]["stable_scene_attributes"],
        "expected_controller_configuration": expected_controllers,
        "expected_ocean_configuration": {key: value for key, value in saved["before"]["ocean"].items() if key != "elapsed"},
        "recorded_original_controller_states": saved["before"]["swimming"],
        "recorded_original_ocean_state": saved["before"]["ocean"],
        "wave_parameter_provenance": {
            "actual_original_demo_result": str(m4_path), "actual_original_demo_result_sha256": sha(m4_path),
            "actual_original_setup_ocean_response": actual_ocean,
            "fixed_endpoint_source": str(SERVICE / "survey_environment.py"),
            "fixed_endpoint_source_sha256": sha(SERVICE / "survey_environment.py"),
            "fixed_OceanAnimationDataModel_call_line": fixed_line, "fixed_configuration": fixed,
            "actual_call_source": str(REPO / "tools/verify_gama_porpoise_live.py"),
            "actual_call_source_sha256": sha(REPO / "tools/verify_gama_porpoise_live.py"),
            "animated_ocean_source": str(ocean_source), "animated_ocean_source_sha256": sha(ocean_source),
            "amplitude_calculation_line": assignments["amplitude"].lineno,
            "wavelength_calculation_line": assignments["wavelength"].lineno,
            "effective_wave_components_at_restart": components,
            "source_effective_use_verified": True,
            "note": "wave_height=5 and wave_length=650 are fixed by the endpoint actually used for original M4 setup; status does not echo these two fields. AST inspection verifies both feed the live animated wave amplitudes/wavenumbers and the evaluator uses them. This proves configuration provenance/effective use, not recovery of the prior wave phase."},
        "limitations": [
            "The checkpoint preserves a frozen visual scene; controller/animation phase is not serialized.",
            "Canonical respawn avoids adding new procedural deformation on top of the frozen deformed mesh.",
            "Ocean restart preserves material binding but replaces points and resets elapsed/accumulator to zero.",
            "Gallery restart preserves checkpoint root positions and engineering display scale but reinitializes directions/yaw/phases and rebuilds skeletal animation.",
            "The restore endpoint restores scene/camera/renderer settings; its saved timeline_seconds field is not used to restore live timeline time.",
            "The original animation phase, swimming direction and ocean phase are not claimed to continue exactly.",
        ],
    }
    if sha(scene) != original_scene_sha or any(name == "omni" or name.startswith("omni.") for name in sys.modules):
        raise ValueError("Private inspection modified checkpoint bytes or imported Kit")
    with destination.open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"usable": True, "output": str(destination),
                      "respawn_payloads": len(respawns), "private_checkpoint_sha256": original_scene_sha,
                      "wave_height": fixed["wave_height"], "wave_length": fixed["wave_length"],
                      "effective_wave_use_verified": True, "controller_phase_recovery_claimed": False}, indent=2))


if __name__ == "__main__":
    main()
