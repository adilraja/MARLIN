"""Audit the M7 training/selection/test boundary and grouped metrics."""

import hashlib
import json
from pathlib import Path
import sys

EXP = Path(__file__).resolve().parents[1]
REPO = EXP.parents[1]
sys.path.insert(0, str(EXP / "ml"))
from metrics import ap50, select_threshold, summarize


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    history = read(EXP / "results/m7_training_history.json")
    selection = read(EXP / "results/m7_validation_selection.json")
    test_report = read(EXP / "results/m7_test_metrics.json")
    test_frames = read(EXP / "results/m7_test_predictions.json")
    lock = read(EXP / "ml/detector_lock.json")
    val_frames = read(REPO / "artifacts/gsd_pilot_v1_m7/best_validation_predictions.json")
    groups = read(EXP / "splits/image_assignments.json")["images"]
    by_id = {item["image_id"]: item for item in groups}
    assert len(by_id) == 300 and len(val_frames) == len(test_frames) == 60
    assert len(history["epochs"]) == lock["training"]["epochs"] == 20
    assert [item["epoch"] for item in history["epochs"]] == list(range(1, 21))
    top = max(history["epochs"], key=lambda item: item["pooled_validation_AP50"])
    assert top["epoch"] == history["best_epoch"] == selection["best_epoch"]
    assert top["pooled_validation_AP50"] == history["best_pooled_validation_AP50"]
    assert ap50(val_frames) == top["pooled_validation_AP50"]
    threshold = select_threshold(val_frames)
    assert threshold == selection["selected_confidence_threshold"]
    assert threshold == test_report["confidence_threshold_selected_on_validation"]
    assert test_report["best_epoch_selected_on_validation"] == top["epoch"]
    assert not test_report["test_used_for_selection"]
    assert test_report["m6_manifest_sha256"] == sha(EXP / "qa/milestone_6_manifest.json")
    checkpoint = REPO / test_report["best_checkpoint_ignored_artifact"]
    assert checkpoint.is_file() and sha(checkpoint) == test_report["best_checkpoint_sha256"]
    for split, frames in (("validation", val_frames), ("test", test_frames)):
        assert len({f["image_id"] for f in frames}) == 60
        for frame in frames:
            source = by_id[frame["image_id"]]
            assert source["split"] == split
            assert source["scene_id"] == frame["scene_id"]
            assert source["species"] == frame["species"]
            assert source["requested_gsd_cm_px"] == frame["requested_gsd_cm_px"]
            assert (frame["gt_box_xyxy_px"] is None) == (source["intervention"] == "target_absent")
            assert all(0.001 <= p["score"] <= 1 for p in frame["predictions"])
        for species in ("european_storm_petrel", "harbour_porpoise"):
            for gsd in (0.5, 1.0, 2.0, 3.0, 4.0):
                subset = [f for f in frames if f["species"] == species and f["requested_gsd_cm_px"] == gsd]
                assert len(subset) == 6
                assert sum(f["gt_box_xyxy_px"] is not None for f in subset) == 5
                assert sum(f["gt_box_xyxy_px"] is None for f in subset) == 1
                reported = (selection if split == "validation" else test_report)["metrics"]["by_species_and_gsd_cm_px"][species][str(gsd)]
                assert summarize(subset, threshold) == reported
    assert summarize(test_frames, threshold) == test_report["metrics"]["overall"]
    assert test_report["metrics"]["overall"]["TP"] + test_report["metrics"]["overall"]["FN"] == 50
    result = {"passed": True, "epochs": 20, "validation_images": 60,
              "test_images": 60, "test_groups_per_species_gsd": 6,
              "test_positives_per_species_gsd": 5, "test_negatives_per_species_gsd": 1,
              "best_epoch": top["epoch"], "selected_threshold": threshold,
              "test_used_for_selection": False,
              "checkpoint_sha256_verified": test_report["best_checkpoint_sha256"],
              "all_grouped_metrics_recomputed": True}
    (EXP / "qa/m7_result_validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
