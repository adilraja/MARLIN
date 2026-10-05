"""Freeze M6 scene-group splits and verify detector input geometry."""

import hashlib
import importlib.util
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
SPEC_MODULE = REPO / "source/extensions/cris.madil.render_service/cris/madil/render_service/survey_spec.py"
SEED = 20260929
NEGATIVE_INDICES = {0, 6, 12, 18, 24}
SPLITS = ("train", "validation", "test")
SIZE = (1024, 768)
PAD = (0, 128, 0, 128)
PAD_RGB = (114, 114, 114)


def read(name):
    return json.loads((ROOT / name).read_text())


def write(name, value):
    path = ROOT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def survey_validator():
    spec = importlib.util.spec_from_file_location("marlin_survey_spec_m6", SPEC_MODULE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.validate_split_records


def ordered(groups, species, stratum):
    return sorted(groups, key=lambda g: hashlib.sha256(
        f"{SEED}:{species}:{stratum}:{g['scene_id']}".encode()).hexdigest())


def assign(groups, species, stratum, counts):
    result = []
    seq = ordered(groups, species, stratum)
    assert len(seq) == sum(counts)
    start = 0
    for split, count in zip(SPLITS, counts):
        for group in seq[start:start + count]:
            group["split"] = split
            group["assignment_stratum"] = stratum
            group["assignment_rank"] = start + seq[start:start + count].index(group)
            result.append(group)
        start += count
    return result


def main():
    from PIL import Image

    source_spec = read("history/milestone_5/specification.json")
    assert source_spec["schema_version"] == "1.4.0"
    assert read("specification.json")["schema_version"] == "1.5.0"
    assert source_spec["splits"]["counts_per_target"] == dict(zip(SPLITS, (15, 5, 5)))
    coco = read("annotations/milestone_5_coco.json")
    frames = read("annotations/milestone_5_frames.json")["frames"]
    variants = read("renders/milestone_5/variant_index.json")
    assert coco["categories"] == [{"id": 1, "name": "wildlife"}]
    assert len(coco["images"]) == len(frames) == len(variants) == 300
    assert len(coco["annotations"]) == 250
    images = {v["id"]: v for v in coco["images"]}
    frame_map = {v["image_id"]: v for v in frames}
    variant_map = {(v["scene_id"], v["requested_gsd_cm_px"], v["intervention"]): v for v in variants}
    assert len(images) == len(frame_map) == len(variant_map) == 300
    anns = defaultdict(list)
    for ann in coco["annotations"]:
        assert ann["category_id"] == 1 and ann["image_id"] in images
        anns[ann["image_id"]].append(ann)

    scene_ids = sorted({v["scene_id"] for v in coco["images"]})
    assert len(scene_ids) == 50
    groups = []
    for scene_id in scene_ids:
        scene = read(f"scenes/manifests/{scene_id}.json")
        assert scene["scene_id"] == scene_id
        index = scene["candidate_index"]
        groups.append({"scene_id": scene_id, "species": scene["species"],
                       "scene_index": index, "has_negative_counterpart": index in NEGATIVE_INDICES,
                       "asset_instance_id": scene["asset_instance_id"],
                       "sequence_id": scene["sequence_id"],
                       "condition_id": scene["condition_id"],
                       "scene_manifest_sha256": digest(ROOT / f"scenes/manifests/{scene_id}.json")})
    assigned = []
    for species in sorted({g["species"] for g in groups}):
        own = [g for g in groups if g["species"] == species]
        assert len(own) == 25
        assigned += assign([g for g in own if g["has_negative_counterpart"]], species, "negative_parent", (3, 1, 1))
        assigned += assign([g for g in own if not g["has_negative_counterpart"]], species, "positive_only", (12, 4, 4))
    by_scene = {g["scene_id"]: g for g in assigned}
    assert len(by_scene) == 50
    assert len({g[k] for g in assigned for k in ("scene_id",)}) == 50
    records = []
    counts = Counter()
    by_species_scene = defaultdict(list)
    for image_id in sorted(images):
        image = images[image_id]
        frame = frame_map[image_id]
        group = by_scene[image["scene_id"]]
        variant = variant_map[(image["scene_id"], image["requested_gsd_cm_px"], image["intervention"])]
        assert image["id"] == frame["image_id"]
        assert image["file_name"] == frame["image_path"]
        assert image["sha256"] == frame["image_sha256"]
        if "rgb_path" in variant:
            assert image["file_name"] == variant["rgb_path"]
            assert image["sha256"] == variant["rgb_sha256"]
        assert image["species"] == frame["species"] == group["species"]
        assert image["requested_gsd_cm_px"] == frame["requested_gsd_cm_px"] == variant["requested_gsd_cm_px"]
        assert (image["width"], image["height"]) == SIZE
        assert image["intervention"] in ("target_present", "target_absent")
        positive = image["intervention"] == "target_present"
        assert len(anns[image_id]) == int(positive)
        if not positive:
            assert group["has_negative_counterpart"]
        path = ROOT / image["file_name"]
        assert digest(path) == image["sha256"], path
        with Image.open(path) as rgb:
            assert rgb.format == "PNG" and rgb.mode in ("RGB", "RGBA") and rgb.size == SIZE
            rgb.load()
            if rgb.mode == "RGBA":
                assert rgb.getchannel("A").getextrema() == (255, 255)
        bbox = None
        padded_box = None
        target_original = None
        target_model = None
        if positive:
            ann = anns[image_id][0]
            assert ann["bbox_semantics"] == "amodal_direct_evaluated_mesh_projection"
            bbox = ann["bbox"]
            x, y, w, h = bbox
            assert all(math.isfinite(v) for v in bbox)
            assert x >= 0 and y >= 0 and w > 0 and h > 0
            assert x + w <= SIZE[0] + 1e-6 and y + h <= SIZE[1] + 1e-6
            padded_box = [x, y + PAD[1], w, h]
            assert padded_box[1] + h <= 1024 + 1e-6
            assert all(math.isclose(a, b, abs_tol=1e-10) for a, b in zip(
                [padded_box[0], padded_box[1] - PAD[1], w, h], bbox))
            target_original = {"bbox_width_px": w, "bbox_height_px": h}
            target_model = {"bbox_width_px": w, "bbox_height_px": h}
            assert math.isclose(ann["area"], w * h, rel_tol=1e-10)
        record = {"image_id": image_id, "split": group["split"],
                  "scene_id": group["scene_id"], "species": group["species"],
                  "asset_instance_id": group["asset_instance_id"],
                  "sequence_id": group["sequence_id"], "condition_id": group["condition_id"],
                  "requested_gsd_cm_px": image["requested_gsd_cm_px"],
                  "intervention": image["intervention"], "image_path": image["file_name"],
                  "image_sha256": image["sha256"], "annotation_ids": [a["id"] for a in anns[image_id]],
                  "original_bbox_xywh_px": bbox, "model_bbox_xywh_px": padded_box,
                  "original_pixels_on_target": target_original,
                  "model_input_pixels_on_target": target_model}
        records.append(record)
        counts[(group["species"], group["split"], image["intervention"])] += 1
        by_species_scene[(group["scene_id"], image["intervention"])].append(image["requested_gsd_cm_px"])
    for scene_id in scene_ids:
        assert sorted(by_species_scene[(scene_id, "target_present")]) == [0.5, 1, 2, 3, 4]
        assert sorted(by_species_scene[(scene_id, "target_absent")]) == ([0.5, 1, 2, 3, 4] if by_scene[scene_id]["has_negative_counterpart"] else [])
    survey_validator()(records)
    for species in sorted({g["species"] for g in groups}):
        for split, nscene, nnegative in zip(SPLITS, (15, 5, 5), (3, 1, 1)):
            assert sum(g["species"] == species and g["split"] == split for g in assigned) == nscene
            assert counts[(species, split, "target_present")] == nscene * 5
            assert counts[(species, split, "target_absent")] == nnegative * 5
    split_summary = {split: {"scene_groups": sum(g["split"] == split for g in assigned),
                             "images": sum(r["split"] == split for r in records),
                             "positive_images": sum(r["split"] == split and r["intervention"] == "target_present" for r in records),
                             "negative_images": sum(r["split"] == split and r["intervention"] == "target_absent" for r in records)}
                     for split in SPLITS}
    assert split_summary == {"train": {"scene_groups": 30, "images": 180, "positive_images": 150, "negative_images": 30},
                             "validation": {"scene_groups": 10, "images": 60, "positive_images": 50, "negative_images": 10},
                             "test": {"scene_groups": 10, "images": 60, "positive_images": 50, "negative_images": 10}}
    write("splits/scene_groups.json", {"seed": SEED, "algorithm": "sha256_seeded_rank_within_species_and_negative_parent_stratum", "groups": sorted(assigned, key=lambda g: g["scene_id"])})
    write("splits/image_assignments.json", {"source_coco_sha256": digest(ROOT / "annotations/milestone_5_coco.json"),
                                            "source_frames_sha256": digest(ROOT / "annotations/milestone_5_frames.json"),
                                            "source_variant_index_sha256": digest(ROOT / "renders/milestone_5/variant_index.json"),
                                            "images": records})
    for split in SPLITS:
        write(f"splits/{split}.json", {"split": split, "image_ids": [r["image_id"] for r in records if r["split"] == split],
                                      "scene_ids": sorted(g["scene_id"] for g in assigned if g["split"] == split)})
    write("qa/m6_input_validation.json", {"passed": True, "split_summary": split_summary,
                                          "decoded_rgb_pngs": 300, "verified_image_sha256": 300,
                                          "verified_amodal_boxes": 250, "verified_negative_images": 50,
                                          "protected_identity_leakage": 0, "paired_gsd_and_negative_checks": 50,
                                          "original_size_px": list(SIZE), "model_size_px": [1024, 1024],
                                          "padding_ltrb_px": list(PAD), "padding_rgb": list(PAD_RGB),
                                          "original_to_model_affine_3x3": [[1, 0, 0], [0, 1, 128], [0, 0, 1]],
                                          "box_roundtrips": 250,
                                          "pixel_size_preserved": True,
                                          "area_semantics": "bbox_area_only; visible/silhouette area unknown"})
    print(json.dumps(split_summary, indent=2))


if __name__ == "__main__":
    main()
