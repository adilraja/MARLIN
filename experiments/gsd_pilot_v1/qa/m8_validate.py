"""Validate final figures, provenance, uncertainty and live completion evidence."""

import hashlib
import json
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
REPO = EXP.parents[1]


def read(name):
    return json.loads((EXP / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    from PIL import Image

    spec = read("specification.json")
    analysis = read("results/m8_gsd_analysis.json")
    test = read("results/m7_test_metrics.json")
    provenance = read("qa/m8_provenance.json")
    regressions = read("qa/m8_regression_validation.json")
    preview = read("qa/milestone_8_animation_preview.json")
    report = (EXP / "results/M8_FINAL_REPORT.md").read_text()
    assert spec["schema_version"] == "1.7.0" and spec["outstanding_gates"] == []
    assert test["test_used_for_selection"] is False
    assert analysis["selected_threshold"] == test["confidence_threshold_selected_on_validation"]
    assert len(analysis["per_species_gsd"]) == 2
    for species, gsds in analysis["per_species_gsd"].items():
        assert set(gsds) == {"0.5", "1.0", "2.0", "3.0", "4.0"}
        for gsd, value in gsds.items():
            baseline = test["metrics"]["by_species_and_gsd_cm_px"][species][gsd]
            assert value["positive_scene_groups"] == 5 and value["negative_images"] == 1
            assert value["TP"] == baseline["TP"] and value["FN"] == baseline["FN"]
            assert value["AP50"] == baseline["AP50"]
            assert value["recall"] == value["TP"] / 5
            lower, upper = value["recall_wilson_95"]
            assert 0 <= lower <= value["recall"] <= upper <= 1
            assert value["bbox_min_side_px_range"][0] <= value["bbox_min_side_px_median"] <= value["bbox_min_side_px_range"][1]
            assert len(value["bbox_min_side_px_by_scene"]) == 5
    paired = analysis["paired_scene_bootstrap"]
    assert paired["observed_delta"] == analysis["pooled_gsd"]["4.0"]["recall"] - analysis["pooled_gsd"]["0.5"]["recall"]
    assert paired["resampling_unit"] == "scene_group_with_all_paired_GSD_outcomes"
    assert paired["stratification"] == "five_draws_per_species_with_replacement"
    assert paired["replicates"] == 10000 and paired["bootstrap_percentile_95"] == [-0.9, -0.5]
    for name in ("m8_performance_vs_gsd", "m8_pixels_on_target"):
        png = EXP / f"results/{name}.png"
        svg = EXP / f"results/{name}.svg"
        with Image.open(png) as image:
            assert image.format == "PNG" and image.width >= 1200 and image.height >= 600
            image.verify()
        assert svg.is_file() and "<svg" in svg.read_text()[:1000]
        assert f"{name}.png" in report
    assert "not establish" in report and "provisional" in report.lower()
    for name, expected in provenance["file_sha256"].items():
        assert sha(EXP / name) == expected, name
    assert provenance["runtime_source_diff_bytes"] == 0
    assert len(provenance["assets"]) == 2
    assert sum(len(v["asset_dependencies"]) for v in provenance["assets"].values()) == 8
    for n in range(1, 8):
        assert provenance["historical_milestone_manifests"][str(n)] == sha(EXP / f"qa/milestone_{n}_manifest.json")
    checkpoint = REPO / provenance["best_checkpoint"]["path"]
    assert sha(checkpoint) == provenance["best_checkpoint"]["sha256"]
    assert regressions["passed"] and regressions["service_tests"] == 77
    assert regressions["reconstruction_contract_tests"] == 8
    for item in regressions["results"].values():
        assert item["return_code"] == 0
        assert sha(EXP / item["log"]) == item["log_sha256"]
    assert preview["passed"] and preview["gallery_loaded_count"] == 11
    assert preview["after"]["gallery"]["animal_count"] == 11
    assert preview["after"]["ocean"]["elapsed"] > preview["before"]["ocean"]["elapsed"]
    before = {a["name"]: a for a in preview["before"]["gallery"]["animals"]}
    assert all(a["body_animation"] and a["z"] != before[a["name"]]["z"]
               for a in preview["after"]["gallery"]["animals"])
    value = {"passed": True, "species_gsd_cells": 10,
             "positive_test_images_covered": 50, "figure_pngs_verified": 2,
             "figure_svgs_verified": 2, "provenance_hashes_verified": len(provenance["file_sha256"]),
             "historical_manifests_verified": 7, "service_regressions_passed": 77,
             "reconstruction_contract_tests_passed": 8,
             "live_preview_animals_swimming": 11,
             "live_preview_ocean_advanced": True}
    (EXP / "qa/m8_result_validation.json").write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps(value, indent=2))


if __name__ == "__main__":
    main()
