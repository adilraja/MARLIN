"""Record the final pilot's source, asset, dataset, model and plot identities."""

import hashlib
import json
from pathlib import Path
import re
import subprocess

EXP = Path(__file__).resolve().parents[1]
REPO = EXP.parents[1]


def read(name):
    return json.loads((EXP / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=REPO)


def version(path):
    match = re.search(r'^version\s*=\s*"([^"]+)"', path.read_text(), re.M)
    assert match, path
    return match.group(1)


def main():
    spec = read("specification.json")
    m7 = read("results/m7_test_metrics.json")
    history = read("results/m7_training_history.json")
    analysis = read("results/m8_gsd_analysis.json")
    assert spec["schema_version"] == "1.7.0"
    assert history["training_epochs_completed"] == 20
    assert analysis["paired_scene_bootstrap"]["resampling_unit"] == "scene_group_with_all_paired_GSD_outcomes"
    asset_records = {}
    for species in ("european_storm_petrel", "harbour_porpoise"):
        path = EXP / f"wildlife/{species}.json"
        record = json.loads(path.read_text())
        dependencies = []
        for item in record["asset"]["dependencies"]:
            source = REPO / item["path"]
            actual = sha(source)
            assert actual == item["sha256"], source
            dependencies.append({"path": item["path"], "sha256": actual})
        asset_records[species] = {"calibration_record": str(path.relative_to(EXP)),
                                  "calibration_sha256": sha(path),
                                  "license": record["asset"]["license"],
                                  "asset_dependencies": dependencies}
    key_files = [
        "specification.json", "environment.json",
        "renders/milestone_5/variant_index.json", "annotations/milestone_5_coco.json",
        "annotations/milestone_5_frames.json", "splits/scene_groups.json",
        "splits/image_assignments.json", "ml/detector_lock.json",
        "ml/requirements-cu126.lock", "ml/dataset.py", "ml/metrics.py",
        "ml/train_evaluate.py", "results/m7_test_metrics.json",
        "results/m7_test_predictions.json", "results/m8_gsd_analysis.json",
        "results/m8_performance_vs_gsd.png", "results/m8_performance_vs_gsd.svg",
        "results/m8_pixels_on_target.png", "results/m8_pixels_on_target.svg",
    ]
    hashes = {name: sha(EXP / name) for name in key_files}
    checkpoint = REPO / m7["best_checkpoint_ignored_artifact"]
    assert checkpoint.is_file() and sha(checkpoint) == m7["best_checkpoint_sha256"]
    source_diff = git("diff", "--binary", "--", "source/apps", "source/extensions")
    app = REPO / "source/apps/cris.madil.kit"
    extension = REPO / "source/extensions/cris.madil.render_service/config/extension.toml"
    value = {
        "experiment_id": spec["experiment_id"], "specification_version": spec["schema_version"],
        "git_head_at_package": git("rev-parse", "HEAD").decode().strip(),
        "source_baseline_commit": spec["source_baseline_commit"],
        "runtime_source_diff_sha256": hashlib.sha256(source_diff).hexdigest(),
        "runtime_source_diff_bytes": len(source_diff),
        "repository_status_at_package": git("status", "--short").decode().splitlines(),
        "app": {"path": str(app.relative_to(REPO)), "version": version(app), "sha256": sha(app)},
        "extension": {"path": str(extension.relative_to(REPO)), "version": version(extension),
                      "sha256": sha(extension)},
        "assets": asset_records,
        "camera_specification": spec["camera"],
        "environment_record_sha256": hashes["environment.json"],
        "renderer_settings": read("environment.json")["renderer_settings"],
        "seeds": {"scene_and_split": spec["splits"]["seed"],
                  "detector": spec["training"]["seed"],
                  "paired_bootstrap": analysis["paired_scene_bootstrap"]["seed"]},
        "hardware": {**m7["hardware"], "driver_version": "595.91.07"},
        "dependencies": {"torch": m7["torch_version"],
                         "torchvision": m7["torchvision_version"],
                         "matplotlib_for_m8_plots": "3.11.2",
                         "lock": "ml/requirements-cu126.lock"},
        "file_sha256": hashes,
        "best_checkpoint": {"path": m7["best_checkpoint_ignored_artifact"],
                            "sha256": m7["best_checkpoint_sha256"],
                            "tracked_in_git": False},
        "historical_milestone_manifests": {
            str(n): sha(EXP / f"qa/milestone_{n}_manifest.json") for n in range(1, 8)},
        "unresolved_external_material_dependencies":
            spec["provenance"]["runtime_external_material_dependencies"],
    }
    target = EXP / "qa/m8_provenance.json"
    target.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "hashed_key_files": len(hashes),
                      "asset_dependencies": sum(len(a["asset_dependencies"]) for a in asset_records.values()),
                      "runtime_source_diff_bytes": len(source_diff)}, indent=2))


if __name__ == "__main__":
    main()
