"""Seal the final provisional MARLIN GSD pilot without changing M1-M7 bytes."""

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
    for milestone in range(1, 8):
        previous = read(EXP / f"qa/milestone_{milestone}_manifest.json")
        redirects = read(EXP / f"history/milestone_{milestone}/path_relocations.json")["path_relocations"]
        for record in previous["outputs"]:
            path = EXP / redirects.get(record["path"], record["path"])
            if not path.is_file() or sha(path) != record["sha256"]:
                raise ValueError(f"Historical output changed: {path}")
        history[str(milestone)] = len(previous["outputs"])
    spec = read(EXP / "specification.json")
    old = read(EXP / "history/milestone_7/specification.json")
    assert spec["schema_version"] == "1.7.0" and spec["outstanding_gates"] == []
    for key in ("gsd_levels_cm_px", "coordinates", "camera", "targets", "environment",
                "scene_generation", "dataset", "annotations", "splits", "model_input",
                "training", "evaluation", "native_capture", "provenance"):
        if spec[key] != old[key]:
            raise ValueError(f"Frozen protocol changed: {key}")
    qa = read(EXP / "qa/m8_result_validation.json")
    regression = read(EXP / "qa/m8_regression_validation.json")
    preview = read(EXP / "qa/milestone_8_animation_preview.json")
    test = read(EXP / "results/m7_test_metrics.json")
    provenance = read(EXP / "qa/m8_provenance.json")
    assert qa["passed"] and qa["species_gsd_cells"] == 10
    assert regression["passed"] and regression["service_tests"] == 77
    assert preview["passed"] and preview["after"]["gallery"]["animal_count"] == 11
    assert preview["after"]["ocean"]["elapsed"] > preview["before"]["ocean"]["elapsed"]
    checkpoint = REPO / test["best_checkpoint_ignored_artifact"]
    assert checkpoint.is_file() and sha(checkpoint) == test["best_checkpoint_sha256"]
    assert provenance["best_checkpoint"]["sha256"] == test["best_checkpoint_sha256"]
    files = [EXP / name for name in (
        "README.md", "specification.json", "results/M8_FINAL_REPORT.md",
        "results/m8_gsd_analysis.json", "results/m8_performance_vs_gsd.png",
        "results/m8_performance_vs_gsd.svg", "results/m8_pixels_on_target.png",
        "results/m8_pixels_on_target.svg", "results/m8_analyse.py",
        "qa/m8_provenance.py", "qa/m8_provenance.json", "qa/m8_regressions.py",
        "qa/m8_regression_blender_usd.log", "qa/m8_regression_reconstruction.log",
        "qa/m8_regression_metrics.log", "qa/m8_regression_m7_package.log",
        "qa/m8_regression_validation.json", "qa/m8_validate.py",
        "qa/m8_result_validation.json", "qa/m8_package.py",
        "qa/milestone_8_animation_preview.json",
        "history/milestone_7/README.md", "history/milestone_7/specification.json",
        "history/milestone_7/path_relocations.json")]
    for path in files:
        if not path.is_file():
            raise FileNotFoundError(path)
        if path.suffix == ".py":
            ast.parse(path.read_text(), filename=str(path))
    outputs = [{"path": str(path.relative_to(EXP)), "bytes": path.stat().st_size,
                "sha256": sha(path)} for path in sorted(files)]
    target = EXP / "qa/milestone_8_manifest.json"
    if target.exists():
        existing = read(target)
        if existing["outputs"] != outputs or existing["historical_outputs_preserved"] != history:
            raise ValueError("Sealed M8 output changed")
        print(json.dumps({"passed": True, "sealed_manifest_verified": True,
                          "outputs": len(outputs), "historical_outputs_preserved": history}, indent=2))
        return
    value = {"milestone": 8, "status": "complete_provisional_synthetic_to_synthetic_pilot",
             "completed_at_utc": datetime.now(timezone.utc).isoformat(),
             "next_milestone": None, "specification_version": "1.7.0",
             "test_images": test["metrics"]["overall"]["images"],
             "test_AP50": test["metrics"]["overall"]["AP50"],
             "best_checkpoint_sha256": test["best_checkpoint_sha256"],
             "test_set_tuning": False, "operational_threshold_claim": False,
             "completion_preview": "moving_water_and_11_default_animals_swimming_in_live_viewport",
             "historical_outputs_preserved": history, "outputs": outputs}
    target.write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps({"passed": True, "outputs": len(outputs),
                      "historical_outputs_preserved": history}, indent=2))


if __name__ == "__main__":
    main()
