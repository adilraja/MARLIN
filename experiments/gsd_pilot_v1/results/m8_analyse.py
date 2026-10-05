"""Create M8 descriptive GSD curves and scene-group-aware uncertainty."""

import json
import math
import os
from pathlib import Path
import random
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(REPO / "artifacts/gsd_pilot_v1_m8/matplotlib"))
sys.path.insert(0, str(ROOT / "ml"))
from metrics import ranked_events

SPECIES = ("european_storm_petrel", "harbour_porpoise")
GSDS = (0.5, 1.0, 2.0, 3.0, 4.0)
THRESHOLD_EPS = 1e-12


def read(name):
    return json.loads((ROOT / name).read_text())


def write(name, value):
    path = ROOT / name
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def wilson(k, n, z=1.959963984540054):
    assert 0 <= k <= n and n > 0
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z / denom * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [max(0.0, center - margin), min(1.0, center + margin)]


def quantile(values, fraction):
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def detected(frame, threshold):
    return any(event["tp"] for event in ranked_events([frame], threshold))


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    test = read("results/m7_test_metrics.json")
    predictions = read("results/m7_test_predictions.json")
    assignments = read("splits/image_assignments.json")["images"]
    by_image = {item["image_id"]: item for item in assignments}
    threshold = test["confidence_threshold_selected_on_validation"]
    assert len(predictions) == 60 and len(by_image) == 300
    positives = [frame for frame in predictions if frame["gt_box_xyxy_px"] is not None]
    assert len(positives) == 50
    hit = {}
    rows = {}
    for frame in positives:
        source = by_image[frame["image_id"]]
        assert source["split"] == "test"
        assert source["scene_id"] == frame["scene_id"]
        assert source["species"] == frame["species"]
        assert source["requested_gsd_cm_px"] == frame["requested_gsd_cm_px"]
        width = source["original_pixels_on_target"]["bbox_width_px"]
        height = source["original_pixels_on_target"]["bbox_height_px"]
        model_pixels = source["model_input_pixels_on_target"]
        assert model_pixels == source["original_pixels_on_target"]
        found = detected(frame, threshold)
        key = (frame["scene_id"], frame["requested_gsd_cm_px"])
        assert key not in hit
        hit[key] = int(found)
        rows[key] = {"image_id": frame["image_id"], "bbox_width_px": width,
                     "bbox_height_px": height, "bbox_min_side_px": min(width, height),
                     "detected_at_selected_threshold": found}
    assert len(hit) == 50

    cells = {}
    for species in SPECIES:
        cells[species] = {}
        for gsd in GSDS:
            group = [frame for frame in positives if frame["species"] == species and
                     frame["requested_gsd_cm_px"] == gsd]
            assert len(group) == 5 and len({f["scene_id"] for f in group}) == 5
            hits = sum(hit[(f["scene_id"], gsd)] for f in group)
            reported = test["metrics"]["by_species_and_gsd_cm_px"][species][str(gsd)]
            assert hits == reported["TP"] and reported["positive_images"] == 5
            widths = [rows[(f["scene_id"], gsd)]["bbox_width_px"] for f in group]
            heights = [rows[(f["scene_id"], gsd)]["bbox_height_px"] for f in group]
            min_sides = [min(a, b) for a, b in zip(widths, heights)]
            cells[species][str(gsd)] = {
                "positive_scene_groups": 5, "negative_images": reported["negative_images"],
                "TP": hits, "FP": reported["FP"], "FN": reported["FN"],
                "recall": hits / 5, "recall_wilson_95": wilson(hits, 5),
                "AP50": reported["AP50"],
                "bbox_width_px_median": statistics.median(widths),
                "bbox_height_px_median": statistics.median(heights),
                "bbox_min_side_px_median": statistics.median(min_sides),
                "bbox_min_side_px_range": [min(min_sides), max(min_sides)],
                "bbox_min_side_px_by_scene": {f["scene_id"]: rows[(f["scene_id"], gsd)]["bbox_min_side_px"]
                                               for f in group},
            }
    pooled = {}
    for gsd in GSDS:
        group = [frame for frame in positives if frame["requested_gsd_cm_px"] == gsd]
        assert len(group) == 10
        hits = sum(hit[(f["scene_id"], gsd)] for f in group)
        pooled[str(gsd)] = {"positive_scene_groups": 10, "TP": hits,
                            "recall": hits / 10, "recall_wilson_95": wilson(hits, 10)}
    # Every bootstrap draw is a scene ID, carrying its paired GSD outcomes.
    # Species stratification retains five petrel and five porpoise draws.
    scene_ids = {species: sorted({f["scene_id"] for f in positives if f["species"] == species})
                 for species in SPECIES}
    assert all(len(values) == 5 for values in scene_ids.values())
    rng = random.Random(20260929)
    bootstrap = []
    for _ in range(10000):
        draws = [rng.choice(scene_ids[species]) for species in SPECIES for _ in range(5)]
        delta = sum(hit[(scene_id, 4.0)] - hit[(scene_id, 0.5)] for scene_id in draws) / 10
        bootstrap.append(delta)
    observed_delta = pooled["4.0"]["recall"] - pooled["0.5"]["recall"]
    paired = {"comparison": "pooled_recall_4p0_minus_0p5_cm_px",
              "observed_delta": observed_delta,
              "bootstrap_percentile_95": [quantile(bootstrap, 0.025), quantile(bootstrap, 0.975)],
              "seed": 20260929, "replicates": 10000,
              "resampling_unit": "scene_group_with_all_paired_GSD_outcomes",
              "stratification": "five_draws_per_species_with_replacement",
              "interpretation_limit": "conditional_on_ten_observed_test_scene_groups; not a population or real-survey confidence interval"}
    analysis = {"source_test_metrics": "results/m7_test_metrics.json",
                "source_test_predictions": "results/m7_test_predictions.json",
                "selected_threshold": threshold, "iou_threshold": 0.5,
                "target_pixel_semantics": "direct_amodal_bbox_width_height_and_minimum_side; not visible silhouette area",
                "per_species_gsd": cells, "pooled_gsd": pooled,
                "paired_scene_bootstrap": paired,
                "uncertainty_policy": "Wilson_95_for_each_binomial_recall; paired_scene_bootstrap_for_cross_GSD_difference"}
    write("results/m8_gsd_analysis.json", analysis)

    colours = {SPECIES[0]: "#1769aa", SPECIES[1]: "#c05a27"}
    labels = {SPECIES[0]: "European storm petrel", SPECIES[1]: "Harbour porpoise"}
    fig, axes = plt.subplots(1, 2, figsize=(11.6, 4.5), sharey=True, layout="constrained")
    for ax, species in zip(axes, SPECIES):
        records = [cells[species][str(g)] for g in GSDS]
        recall = [r["recall"] for r in records]
        lower = [r["recall"] - r["recall_wilson_95"][0] for r in records]
        upper = [r["recall_wilson_95"][1] - r["recall"] for r in records]
        ap = [r["AP50"] for r in records]
        ax.errorbar(GSDS, recall, yerr=[lower, upper], color=colours[species],
                    marker="o", capsize=4, linewidth=2, label="Recall at selected threshold")
        ax.plot(GSDS, ap, color=colours[species], linestyle="--", marker="s",
                alpha=0.75, label="AP50 (score ranked)")
        ax.set_title(labels[species])
        ax.set_xlabel("Requested GSD (cm/px)")
        ax.set_xticks(GSDS)
        ax.set_ylim(-0.06, 1.1)
        ax.grid(alpha=0.25)
    axes[0].set_ylabel("Recall or AP50")
    axes[1].legend(loc="lower left", fontsize=8)
    fig.suptitle("MARLIN synthetic held-out detection by GSD\n"
                 "5 positive and 1 negative scene per target/GSD", fontsize=13)
    for ext in ("png", "svg"):
        fig.savefig(ROOT / f"results/m8_performance_vs_gsd.{ext}", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11.6, 4.5), sharey=False, layout="constrained")
    for ax, species in zip(axes, SPECIES):
        medians = [cells[species][str(g)]["bbox_min_side_px_median"] for g in GSDS]
        ax.plot(GSDS, medians, color=colours[species], linewidth=2,
                marker="o", label="Median minimum box side")
        for gsd in GSDS:
            group = [f for f in positives if f["species"] == species and f["requested_gsd_cm_px"] == gsd]
            for offset, frame in enumerate(sorted(group, key=lambda f: f["scene_id"])):
                row = rows[(frame["scene_id"], gsd)]
                ax.scatter(gsd + (offset - 2) * 0.045, row["bbox_min_side_px"],
                           marker="o" if row["detected_at_selected_threshold"] else "x",
                           color="#26834a" if row["detected_at_selected_threshold"] else "#b22d2d",
                           s=30, linewidths=1.4)
        ax.set_title(labels[species])
        ax.set_xlabel("Requested GSD (cm/px)")
        ax.set_xticks(GSDS)
        ax.set_ylabel("Minimum amodal box side (pixels)")
        ax.grid(alpha=0.25)
        ax.text(0.98, 0.96, "Green circle: hit   Red ×: miss",
                transform=ax.transAxes, ha="right", va="top", fontsize=8, color="#444444")
    fig.suptitle("Projected target extent and detection at the selected threshold", fontsize=13)
    for ext in ("png", "svg"):
        fig.savefig(ROOT / f"results/m8_pixels_on_target.{ext}", dpi=180)
    plt.close(fig)
    print(json.dumps({"passed": True, "test_positive_frames": len(positives),
                      "paired_bootstrap": paired}, indent=2))


if __name__ == "__main__":
    main()
