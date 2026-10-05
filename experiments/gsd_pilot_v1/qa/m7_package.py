"""Seal the one-baseline M7 run and preserve M1-M6 output bytes."""

import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
REPO = EXP.parents[1]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    history = {}
    for milestone in range(1, 7):
        previous = read(EXP / f"qa/milestone_{milestone}_manifest.json")
        redirects = read(EXP / f"history/milestone_{milestone}/path_relocations.json")["path_relocations"]
        for record in previous["outputs"]:
            path = EXP / redirects.get(record["path"], record["path"])
            if not path.is_file() or sha(path) != record["sha256"]:
                raise ValueError(f"Historical output changed: {path}")
        history[str(milestone)] = len(previous["outputs"])
    spec = read(EXP / "specification.json")
    old = read(EXP / "history/milestone_6/specification.json")
    assert spec["schema_version"] == "1.6.0"
    for key in ("gsd_levels_cm_px", "coordinates", "camera", "targets", "environment",
                "scene_generation", "dataset", "annotations", "splits", "model_input",
                "evaluation", "native_capture"):
        if spec[key] != old[key]:
            raise ValueError(f"Frozen protocol changed: {key}")
    for key, value in old["training"].items():
        if spec["training"][key] != value:
            raise ValueError(f"Frozen training policy changed: {key}")
    validation = read(EXP / "qa/m7_result_validation.json")
    training = read(EXP / "results/m7_training_history.json")
    selection = read(EXP / "results/m7_validation_selection.json")
    test = read(EXP / "results/m7_test_metrics.json")
    frames = read(EXP / "results/m7_test_predictions.json")
    preview = read(EXP / "qa/milestone_7_animation_preview.json")
    assert validation["passed"] and validation["epochs"] == 20
    assert training["training_epochs_completed"] == 20
    assert selection["best_epoch"] == training["best_epoch"] == test["best_epoch_selected_on_validation"]
    assert len(frames) == 60 and test["metrics"]["overall"]["positive_images"] == 50
    assert test["metrics"]["overall"]["negative_images"] == 10
    assert test["test_used_for_selection"] is False
    checkpoint = REPO / test["best_checkpoint_ignored_artifact"]
    assert checkpoint.is_file() and sha(checkpoint) == test["best_checkpoint_sha256"]
    assert preview["passed"] and preview["after"]["gallery"]["animal_count"] == 11
    assert preview["after"]["ocean"]["elapsed"] > preview["before"]["ocean"]["elapsed"]
    files = [EXP / name for name in (
        "README.md", "specification.json", "qa/M7_TRAINING.md",
        "qa/m7_result_validation.json", "qa/milestone_7_animation_preview.json",
        "qa/m7_validate.py", "qa/m7_package.py", "ml/metrics.py",
        "ml/train_evaluate.py", "results/m7_training_history.json",
        "results/m7_validation_selection.json", "results/m7_test_predictions.json",
        "results/m7_test_metrics.json", "history/milestone_6/README.md",
        "history/milestone_6/specification.json",
        "history/milestone_6/path_relocations.json")]
    for path in files:
        if not path.is_file():
            raise FileNotFoundError(path)
        if path.suffix == ".py":
            ast.parse(path.read_text(), filename=str(path))
    outputs = [{"path": str(path.relative_to(EXP)), "bytes": path.stat().st_size,
                "sha256": sha(path)} for path in sorted(files)]
    target = EXP / "qa/milestone_7_manifest.json"
    if target.exists():
        existing = read(target)
        if existing["outputs"] != outputs or existing["historical_outputs_preserved"] != history:
            raise ValueError("Sealed M7 output changed")
        print(json.dumps({"passed": True, "sealed_manifest_verified": True,
                          "outputs": len(outputs), "historical_outputs_preserved": history}, indent=2))
        return
    value = {"milestone": 7, "status": "complete_provisional_one_baseline_evaluation",
             "completed_at_utc": datetime.now(timezone.utc).isoformat(),
             "next_milestone": 8, "specification_version": "1.6.0",
             "epochs": 20, "best_epoch": selection["best_epoch"],
             "validation_AP50": selection["pooled_validation_AP50"],
             "selected_confidence_threshold": selection["selected_confidence_threshold"],
             "test_images": len(frames), "test_AP50": test["metrics"]["overall"]["AP50"],
             "best_checkpoint_sha256": test["best_checkpoint_sha256"],
             "test_set_tuning": False,
             "completion_preview": "moving_water_and_11_default_animals_swimming_in_live_viewport",
             "historical_outputs_preserved": history, "outputs": outputs}
    target.write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps({"passed": True, "outputs": len(outputs),
                      "historical_outputs_preserved": history}, indent=2))


if __name__ == "__main__":
    main()
