"""Independently inspect a copied visual checkpoint; never attach it to Kit."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

from pxr import Sdf, Usd, UsdGeom

BASE = Path(__file__).resolve().parent
EXPECTED_ANIMALS = {
    "Bottlenose_Carimam", "Cuvier_Whale", "Frasers_Dolphin", "Humpback_Whale",
    "Manatee", "Bottlenose_DigitalLife", "Spotted_Dolphin", "Pilot_Whale",
    "Pygmy_Sperm_Whale", "Sperm_Whale", "Steno_Dolphin",
}


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    output = BASE / "checkpoint_verification_result.json"
    if output.exists():
        raise ValueError("Existing independent checkpoint verification cannot be overwritten")
    report = {
        "kind": "independent_private_usd_checkpoint_verification", "passed": False,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "command": [sys.executable, "-B", str(Path(__file__).resolve())],
        "kit_imported": False, "kit_stage_attached": False,
        "renderer_created": False, "live_scene_mutated": False,
        "controller_phase_recovery_verified": False,
        "limitations": "Frozen visual checkpoint and recorded controller configuration only; controller/animation phase is not serialized or verified as recoverable.",
    }
    try:
        source_result = BASE / "checkpoint_result.json"
        scene = BASE / "checkpoint_snapshot" / "scene.usdc"
        metadata_path = BASE / "checkpoint_snapshot" / "metadata.json"
        original_hashes = {path.name: sha(path) for path in (scene, metadata_path)}
        saved = json.loads(source_result.read_text())
        metadata = json.loads(metadata_path.read_text())
        api = saved["checkpoint_response"]
        copies = {Path(row["copy"]).name: row for row in saved["verified_copies"]}
        checks = {
            "source_checkpoint_preparation_passed": saved["passed"] is True,
            "scene_sha_matches_api_metadata_and_copy_record": original_hashes["scene.usdc"] == api["scene_sha256"] == metadata["scene_sha256"] == copies["scene.usdc"]["sha256"],
            "metadata_sha_matches_copy_record": original_hashes["metadata.json"] == copies["metadata.json"]["sha256"],
            "metadata_fields_match_api_response": all(api.get(key) == value for key, value in metadata.items()),
            "copied_scene_size_matches_record": scene.stat().st_size == copies["scene.usdc"]["bytes"],
            "copied_metadata_size_matches_record": metadata_path.stat().st_size == copies["metadata.json"]["bytes"],
            "checkpoint_declares_phase_limitation": "controller/animation phase is not serialized" in metadata["limitations"],
        }
        # Use a new anonymous layer rather than Stage.Open(filename), which can
        # reuse a dirty USD layer. No Kit context, viewport, or GPU is involved.
        layer = Sdf.Layer.OpenAsAnonymous(str(scene))
        if layer is None:
            raise ValueError("Copied checkpoint layer could not be opened privately")
        checks["private_layer_is_anonymous"] = layer.anonymous
        checks["flattened_snapshot_has_no_sublayers"] = not layer.subLayerPaths
        stage = Usd.Stage.Open(layer, Usd.Stage.LoadNone)
        checks["copied_usd_stage_opened"] = stage is not None
        if stage is None:
            raise ValueError("Copied checkpoint USD stage could not be opened")
        camera = stage.GetPrimAtPath(metadata["camera"])
        ocean = stage.GetPrimAtPath("/World/Ocean")
        gallery = stage.GetPrimAtPath("/World/Cetaceans")
        animals = [] if not gallery else sorted(child.GetName() for child in gallery.GetChildren())
        audited_animals = {animal["name"] for animal in saved["before"]["swimming"]["animals"]}
        time_sampled = [(str(prim.GetPath()), attr.GetName()) for prim in stage.TraverseAll()
                        for attr in prim.GetAttributes() if attr.GetNumTimeSamples()]
        checks.update({
            "saved_camera_exists_and_is_camera": bool(camera and camera.IsA(UsdGeom.Camera)),
            "ocean_exists_and_is_mesh": bool(ocean and ocean.IsA(UsdGeom.Mesh)),
            "exact_eleven_expected_gallery_animals_retained": set(animals) == EXPECTED_ANIMALS and len(animals) == 11,
            "gallery_animals_match_pre_checkpoint_live_audit": set(animals) == audited_animals,
            "private_porpoise_root_absent": not stage.GetPrimAtPath("/MarlinGamaPorpoise"),
            "transient_render_tree_absent": not stage.GetPrimAtPath("/Render"),
            "frozen_snapshot_has_no_remaining_time_samples": not time_sampled,
            "stage_is_y_up_centimetres": UsdGeom.GetStageUpAxis(stage) == "Y" and UsdGeom.GetStageMetersPerUnit(stage) == .01,
            "no_kit_module_imported": not any(name == "omni" or name.startswith("omni.") for name in sys.modules),
            "copied_bytes_unchanged_after_private_inspection": all(sha(path) == original_hashes[path.name] for path in (scene, metadata_path)),
        })
        report.update({"checkpoint_id": api["checkpoint_id"],
                       "scene": str(scene), "metadata": str(metadata_path),
                       "source_result": str(source_result),
                       "source_result_sha256": sha(source_result),
                       "copied_file_sha256": original_hashes,
                       "camera": metadata["camera"], "gallery_animals": animals,
                       "remaining_time_sampled_attributes": time_sampled,
                       "checks": checks, "passed": all(checks.values())})
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    finally:
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        with output.open("x") as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write("\n")
    print(json.dumps(report, indent=2, allow_nan=False))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
