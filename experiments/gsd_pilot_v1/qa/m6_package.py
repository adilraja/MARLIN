"""Seal M6 outputs and verify all earlier milestone delivery hashes."""

import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    history = {}
    for milestone in range(1, 6):
        records = read(EXP / f"qa/milestone_{milestone}_manifest.json")["outputs"]
        redirects = read(EXP / f"history/milestone_{milestone}/path_relocations.json")["path_relocations"]
        for record in records:
            path = EXP / redirects.get(record["path"], record["path"])
            if not path.is_file() or sha(path) != record["sha256"]:
                raise ValueError(f"Historical output changed: {path}")
        history[str(milestone)] = len(records)
    spec = read(EXP / "specification.json")
    old = read(EXP / "history/milestone_5/specification.json")
    assert spec["schema_version"] == "1.5.0"
    for key in ("gsd_levels_cm_px", "coordinates", "camera", "targets", "environment",
                "scene_generation", "dataset", "annotations", "evaluation", "native_capture"):
        if spec[key] != old[key]:
            raise ValueError(f"Frozen protocol changed: {key}")
    for key in ("counts_per_target", "seed", "assignment", "protected_identifiers",
                "validator", "negative_counterpart_inherits_parent_split",
                "source_asset_hash_shared_across_splits", "unseen_individual_or_mesh_generalisation_claim"):
        if spec["splits"][key] != old["splits"][key]:
            raise ValueError(f"Frozen split policy changed: {key}")
    for key in ("original_image_size_px", "padded_input_size_px", "resize_scale",
                "forbidden_augmentations", "require_full_image_to_model_affine_and_box_check",
                "record_original_and_model_input_pixels_on_target"):
        if spec["model_input"][key] != old["model_input"][key]:
            raise ValueError(f"Frozen input policy changed: {key}")
    for key in ("number_of_baselines", "pool_all_training_gsds", "seed", "epochs",
                "checkpoint_selection", "threshold_selection",
                "same_threshold_for_all_gsds_and_targets", "test_set_tuning"):
        if spec["training"][key] != old["training"][key]:
            raise ValueError(f"Frozen training policy changed: {key}")
    input_qa = read(EXP / "qa/m6_input_validation.json")
    loader_qa = read(EXP / "qa/m6_loader_validation.json")
    preview = read(EXP / "qa/milestone_6_animation_preview.json")
    assert input_qa["passed"] and input_qa["protected_identity_leakage"] == 0
    assert input_qa["decoded_rgb_pngs"] == 300 and input_qa["verified_amodal_boxes"] == 250
    assert loader_qa["passed"] and loader_qa["decoded_padded_images"] == 300
    assert preview["passed"] and preview["after"]["gallery"]["animal_count"] == 11
    assert preview["after"]["ocean"]["elapsed"] > preview["before"]["ocean"]["elapsed"]
    lock = read(EXP / "ml/detector_lock.json")
    weights = EXP.parents[1] / lock["local_weights_path"]
    assert weights.is_file() and sha(weights) == lock["weights_sha256"]
    files = [EXP / name for name in (
        "README.md", "specification.json", "qa/M6_SPLITS_AND_INPUTS.md",
        "qa/m6_input_validation.json", "qa/m6_loader_validation.json",
        "qa/milestone_6_animation_preview.json", "ml/dataset.py", "ml/m6_freeze.py",
        "ml/verify_loader.py", "ml/lock_detector.py", "ml/detector_lock.json",
        "ml/requirements-cu126.lock", "qa/m6_package.py",
        "history/milestone_5/README.md", "history/milestone_5/specification.json",
        "history/milestone_5/path_relocations.json", "splits/scene_groups.json",
        "splits/image_assignments.json", "splits/train.json", "splits/validation.json",
        "splits/test.json")]
    for path in files:
        if not path.is_file():
            raise FileNotFoundError(path)
        if path.suffix == ".py":
            ast.parse(path.read_text(), filename=str(path))
    outputs = [{"path": str(path.relative_to(EXP)), "bytes": path.stat().st_size,
                "sha256": sha(path)} for path in sorted(files)]
    target = EXP / "qa/milestone_6_manifest.json"
    if target.exists():
        existing = read(target)
        if existing["outputs"] != outputs or existing["historical_outputs_preserved"] != history:
            raise ValueError("Sealed M6 output changed")
        print(json.dumps({"passed": True, "sealed_manifest_verified": True,
                          "outputs": len(outputs), "historical_outputs_preserved": history}, indent=2))
        return
    value = {"milestone": 6, "status": "complete_frozen_splits_and_inputs",
             "completed_at_utc": datetime.now(timezone.utc).isoformat(),
             "next_milestone": 7, "specification_version": "1.5.0",
             "scene_groups_by_split": {k: input_qa["split_summary"][k]["scene_groups"] for k in ("train", "validation", "test")},
             "images_by_split": {k: input_qa["split_summary"][k]["images"] for k in ("train", "validation", "test")},
             "protected_identity_leakage": 0, "detector_weights_sha256": lock["weights_sha256"],
             "completion_preview": "moving_water_and_11_default_animals_swimming_in_live_viewport",
             "historical_outputs_preserved": history, "outputs": outputs}
    target.write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps({"passed": True, "outputs": len(outputs),
                      "historical_outputs_preserved": history}, indent=2))


if __name__ == "__main__":
    main()
