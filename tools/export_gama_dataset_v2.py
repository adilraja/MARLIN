"""Export the accepted M7 engineering images/labels into trajectory split folders.

This copies already verified artifacts. It does not render, select replacement
states, train a detector or modify any source capture. An exclusive destination
and all fifteen independent retained-USD verification results are required.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

import capture_gama_dataset_v2 as capture

live = capture.live


def child(base, relative):
    path = live.safe_path(base / relative)
    if not path.is_relative_to(base):
        raise ValueError("An artifact path escaped its evidence directory")
    return path


def export(campaign, verification_dir, destination, visual_review):
    campaign, verification_dir, destination, visual_review = map(
        live.safe_path, (campaign, verification_dir, destination, visual_review))
    if destination.is_relative_to(campaign) or campaign.is_relative_to(destination):
        raise ValueError("Export and campaign directories must be separate")
    if destination.exists():
        raise ValueError("Choose a new export directory; existing evidence is preserved")
    result_pin = capture.pin(campaign / "results.json")
    result = json.loads((campaign / "results.json").read_text())
    split_path = campaign / "trajectory_split_manifest.json"
    split_pin = capture.pin(split_path)
    split = json.loads(split_path.read_text())
    if (result.get("passed") is not True or result.get("preflight_only") is not False
            or result.get("capture_counts") != {"target_present": 75, "target_absent": 75, "groups": 15}
            or live.digest(split_path) != result["trajectory_split_manifest"]["sha256"]
            or split.get("related_trajectories_cross_splits") is not False
            or split.get("annotation_semantics") != "amodal_direct_evaluated_mesh_projection"
            or split.get("biological_approval") is not False
            or capture.pin(campaign / "results.json") != result_pin
            or capture.pin(split_path) != split_pin):
        raise ValueError("A successful declared M7 campaign and honest split manifest are required")
    images = split["images"]
    if len(images) != 150 or len({image["image_id"] for image in images}) != 150:
        raise ValueError("Expected exactly 150 unique declared engineering images")
    review_pin = capture.pin(visual_review)
    review = json.loads(visual_review.read_text())
    observations = review.get("observations", [])
    if (review.get("biological_approval") is not False or len(observations) != 150
            or len({view.get("image_id") for view in observations}) != 150
            or capture.pin(visual_review) != review_pin):
        raise ValueError("A stable, provisional per-view review of all 150 images is required")
    reviews = {view["image_id"]: view for view in observations}
    if set(reviews) != {image["image_id"] for image in images}:
        raise ValueError("Manual review IDs do not match the declared engineering images")
    group_paths = {child(campaign, image["group_manifest"]).parent for image in images}
    verified, verification_files = {}, {}
    for path in sorted(verification_dir.glob("*.json")):
        verification_pin = capture.pin(path)
        record = json.loads(path.read_text())
        if capture.pin(path) != verification_pin:
            raise ValueError("An independent verification changed while being read")
        if record.get("kind") != "m7_independent_retained_group_verification":
            continue
        group = live.safe_path(record["group"])
        if group not in group_paths:
            continue
        if group in verified or record.get("passed") is not True or len(record.get("captures", [])) != 10:
            raise ValueError("A group lacks a unique successful independent USD verification")
        if record["inputs"]["manifest_sha256"] != live.digest(group / "manifest.json"):
            raise ValueError("Independent verification refers to a changed group manifest")
        verified[group] = verification_pin
        verification_files[path] = verification_pin
    if len(group_paths) != 15 or set(verified) != group_paths:
        raise ValueError("All fifteen captured groups require independent retained-USD verification")
    families, related_assignments, group_conditions = {}, {}, {}
    source_pins = {visual_review: review_pin, campaign / "results.json": result_pin,
                   split_path: split_pin, **verification_files}
    for image in images:
        name, partition = image["image_id"], image["split"]
        if not name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-" for c in name):
            raise ValueError("Image ID is not a safe filename")
        if partition not in {"train", "validation", "test"}:
            raise ValueError("Unknown dataset split")
        family = image["encounter_group_id"]
        if families.setdefault(family, partition) != partition:
            raise ValueError("A trajectory family crossed dataset splits")
        for related in image["related_run_ids"]:
            if related_assignments.setdefault(related, partition) != partition:
                raise ValueError("Related GAMA runs crossed dataset splits")
        key = (image["run_id"], image["step_index"])
        conditions = group_conditions.setdefault(key, set())
        condition = (image["target_present"], image["gsd_cm_px"])
        if condition in conditions:
            raise ValueError("A snapshot repeats a presence/GSD condition")
        conditions.add(condition)
        view = reviews[name]
        if (view.get("physically_present") is not image["target_present"]
                or view.get("rendered_visibility") != "unknown"
                or view.get("manual_observation_is_machine_visibility_label") is not False
                or view.get("biological_approval") is not False
                or not isinstance(view.get("manual_contact_sheet_observation"), str)
                or not view["manual_contact_sheet_observation"].strip()
                or any(view.get(key) != image[key] for key in
                       ("run_id", "seed", "step_index", "gsd_cm_px", "variant"))):
            raise ValueError("Manual observations changed source/presence or certified visibility/biology")
        for filename, hash_key in (("rgb_file", "rgb_sha256"), ("annotation_file", "annotation_sha256"),
                                   ("yolo_file", "yolo_sha256"), ("group_manifest", "group_manifest_sha256")):
            path = child(campaign, image[filename])
            if live.digest(path) != image[hash_key]:
                raise ValueError("A source artifact changed before export")
            if filename != "group_manifest" and (live.safe_path(view[filename]) != path
                                                    or view[hash_key] != image[hash_key]):
                raise ValueError("A manual observation refers to another image or label")
            source_pins[path] = capture.pin(path)
            if source_pins[path]["sha256"] != image[hash_key]:
                raise ValueError("A source artifact changed while being pinned")
        sheet = live.safe_path(view["contact_sheet"])
        if live.digest(sheet) != view["contact_sheet_sha256"]:
            raise ValueError("A reviewed contact sheet changed before export")
        source_pins[sheet] = capture.pin(sheet)
    expected = {(present, gsd) for present in (True, False) for gsd in capture.GSDS}
    if len(families) != 5 or len(group_conditions) != 15 or any(values != expected for values in group_conditions.values()):
        raise ValueError("The export would lose complete trajectory/snapshot pairing")
    destination.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(visual_review, destination / "visual_review.json")
    if live.digest(destination / "visual_review.json") != review_pin["sha256"]:
        raise ValueError("Copied per-view review metadata differs from its original")
    exported = []
    for image in images:
        row = dict(image)
        for source_key, folder, suffix, hash_key in (
                ("rgb_file", "images", ".png", "rgb_sha256"),
                ("yolo_file", "labels", ".txt", "yolo_sha256"),
                ("annotation_file", "annotations", ".json", "annotation_sha256")):
            target = destination / folder / image["split"] / (image["image_id"] + suffix)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(child(campaign, image[source_key]), target)
            if live.digest(target) != image[hash_key]:
                raise ValueError("An exported artifact differs from its verified original")
            row["source_" + source_key] = str(child(campaign, image[source_key]).relative_to(live.ROOT))
            row[source_key] = str(target.relative_to(destination))
        exported.append(row)
    (destination / "data.yaml").write_text(
        "# Provisional M7 engineering test set; direct amodal boxes, no visible/refraction masks.\n"
        "path: " + json.dumps(str(destination)) + "\n"
        "train: images/train\nval: images/validation\ntest: images/test\n"
        "names:\n  0: harbour_porpoise\n")
    (destination / "README.md").write_text(
        "# M7 harbour porpoise engineering test set\n\n"
        "This export contains 75 physically present and 75 explicitly target-removed images. "
        "Whole trajectories, all snapshots/GSDs and related runs stay in one split.\n\n"
        "Class 0 labels only the bridge-owned harbour porpoise. Other demonstration animals "
        "remain unlabelled background; target removal does not mean all wildlife was absent. "
        "Boxes use direct evaluated mesh projection and are amodal. They are not exact visible "
        "or refracted underwater outlines. Rendered visibility remains unknown in metadata. "
        "The static-pose behavioural model and biology remain provisional for engineering use.\n\n"
        "Visual review found brightness and texture-detail differences in some preserved "
        "background animals between target-present and removed rows. Their cause was not "
        "established. Matching physical scene and camera identities do not establish "
        "pixel-identical or photometrically equivalent RGB backgrounds.\n\n"
        "The train/validation/test folders describe the declared grouping demonstration. "
        "No detector was trained or statistical generalization established. "
        "data.yaml records this export's absolute root and relative split directories. "
        "Update the root when moving the export. It is a dataset descriptor, not a training command.\n\n"
        "manifest.json maps every copied PNG, label and annotation to its retained capture, "
        "actual GAMA source state, paired scene/camera identities and output hashes. "
        "visual_review.json retains descriptive contact-sheet observations for every image, "
        "including physically present targets that could not be separately distinguished. "
        "These observations do not replace unknown machine visibility or amodal labels.\n")
    unchanged = all(capture.pin(path) == pin for path, pin in source_pins.items())
    if not unchanged:
        raise ValueError("Original evidence changed during export")
    report = {"milestone": 7, "kind": "m7_engineering_dataset_export", "passed": True,
              "created_at_utc": datetime.now(timezone.utc).isoformat(),
              "campaign_result": result_pin, "source_split_manifest": split_pin,
              "exporter": capture.pin(Path(__file__).resolve()),
              "source_visual_review": review_pin,
              "visual_review_file": "visual_review.json",
              "manual_observations_are_machine_visibility_labels": False,
              "independent_group_verifications": list(verified.values()),
              "image_count": len(exported), "target_present": 75, "target_absent": 75,
              "split_image_counts": dict(Counter(image["split"] for image in exported)),
              "trajectory_families_cross_splits": False, "related_runs_cross_splits": False,
              "source_files_unchanged": unchanged, "biological_approval": False,
              "annotation_semantics": "amodal_direct_evaluated_mesh_projection", "rendered_visibility": "unknown",
              "images": exported,
              "outputs": [{"path": str(path.relative_to(destination)), "bytes": path.stat().st_size,
                           "sha256": live.digest(path)} for path in sorted(destination.rglob("*")) if path.is_file()]}
    live.write_json(destination / "manifest.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", required=True, type=Path)
    parser.add_argument("--scene-verifications", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--visual-review", required=True, type=Path)
    args = parser.parse_args()
    result = export(args.campaign, args.scene_verifications, args.output, args.visual_review)
    print(json.dumps({"passed": result["passed"], "images": result["image_count"],
                      "split_image_counts": result["split_image_counts"], "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
