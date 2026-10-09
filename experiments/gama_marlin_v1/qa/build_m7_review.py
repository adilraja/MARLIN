"""Build uncropped M7 contact sheets and a traceable engineering review index.

This reader uses retained files only. It never contacts Kit, changes source
images/labels, selects replacement states, or infers animal visibility from RGB.
Group mode creates an early review preview; campaign mode requires all accepted
captures and independent retained-USD verifications before a final index.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont, ImageStat

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
import capture_gama_dataset_v2 as client

GSDS = (.5, 1., 2., 3., 4.)
RESOLUTION = (1024, 768)
DISPLAY_RESOLUTION = (512, 384)
VERIFICATION_KINDS = {"m7_independent_retained_group_verification",
                      "m7_independent_retained_scene_verification"}
FONT_PATH = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


def read(path):
    return json.loads(client.live.safe_path(path).read_text())


def write(path, value):
    with path.open("x") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


def font(size):
    return ImageFont.truetype(str(FONT_PATH), size) if FONT_PATH.is_file() else ImageFont.load_default()


class InputPins:
    def __init__(self):
        self.values = {}

    def add(self, path, expected=None):
        path = client.live.safe_path(path)
        digest = client.live.digest(path)
        if expected is not None and digest != expected:
            raise ValueError("A retained input hash differs: " + str(path))
        before = self.values.get(str(path))
        if before is not None and before["before_sha256"] != digest:
            raise ValueError("An input changed while the review was being built")
        self.values[str(path)] = {"path": str(path), "bytes": path.stat().st_size,
                                  "before_sha256": digest}
        return path

    def finish(self):
        rows = []
        for key in sorted(self.values):
            row = dict(self.values[key])
            row["after_sha256"] = client.live.digest(Path(key))
            row["unchanged"] = row["after_sha256"] == row["before_sha256"]
            rows.append(row)
        if not all(row["unchanged"] for row in rows):
            raise ValueError("A retained source file changed during review generation")
        return rows


def retained_group(path):
    path = client.live.safe_path(path)
    if (path / "group" / "manifest.json").is_file():
        path /= "group"
    if not (path / "manifest.json").is_file():
        raise ValueError("Expected a retained group or completed step directory")
    return path


def declaration_for_group(group):
    for parent in group.parents:
        candidate = parent / "declaration.json"
        if candidate.is_file():
            return candidate
    raise ValueError("The retained group has no campaign declaration")


def verification_files(inputs):
    """Read only explicitly supplied JSON evidence; ignore execution wrappers."""
    for supplied in inputs:
        path = client.live.safe_path(supplied)
        if path.is_file():
            if path.suffix != ".json":
                raise ValueError("Scene verification evidence must be JSON")
            yield path
        elif path.is_dir():
            for parent, directories, names in os.walk(path, followlinks=False):
                if client.live.FORBIDDEN_PARTS.intersection(directories):
                    raise ValueError("A verification directory contains prohibited generated content")
                for name in directories:
                    if (Path(parent) / name).is_symlink():
                        raise ValueError("Verification directory symlinks are unsupported")
                for name in sorted(names):
                    if name.endswith(".json"):
                        yield client.live.safe_path(Path(parent) / name)
        else:
            raise ValueError("Scene verification input does not exist")


def load_verifications(inputs, pins):
    records = {}
    for path in verification_files(inputs):
        # Pin before parsing so the accepted contents cannot be bound later
        # to different bytes if a verification file changes during loading.
        result = read(pins.add(path))
        if result.get("kind") not in VERIFICATION_KINDS:
            continue
        group = retained_group(result["group"])
        if str(group) in records:
            raise ValueError("Duplicate independent verification for one retained group")
        records[str(group)] = (path, result)
    return records


def check_verification(group, manifest, entry, pins):
    path, result = entry
    pins.add(path)
    checks = result.get("checks", {})
    required = {"present_identity_exact", "absent_identity_exact", "present_background_exact",
                "absent_background_exact", "present_zero_time_samples", "absent_zero_time_samples",
                "only_owned_target_root_removed", "removal_record_exact", "positive_actual_gama_pose",
                "five_exact_camera_condition_pairs", "only_camera_y_varied",
                "all_ten_actual_annotations_and_images", "retained_private_sources_unchanged"}
    if (result.get("passed") is not True or not required.issubset(checks)
            or any(value is not True for value in checks.values())
            or len(result.get("captures", [])) != 10
            or any(item.get("passed") is not True for item in result["captures"])):
        raise ValueError("Independent retained-USD verification did not pass")
    verifier = Path(__file__).with_name("verify_m7_group.py")
    if result["verifier_sha256"] != client.live.digest(verifier):
        raise ValueError("Independent verification used different verifier source bytes")
    inputs = result["inputs"]
    if inputs["manifest_sha256"] != client.live.digest(group / "manifest.json"):
        raise ValueError("Scene verification is bound to another group manifest")
    for variant in ("present", "absent"):
        if inputs[variant + "_scene_sha256"] != manifest["variant_scene_files"][variant]["sha256"]:
            raise ValueError("Verified retained USD hash differs from the group")
    for measured, item in zip(result["captures"], manifest["captures"]):
        for key in ("variant", "target_present", "gsd_cm_px", "resolved_scene_state_hash",
                    "background_scene_hash", "rgb_sha256", "annotation_sha256", "yolo_sha256"):
            if measured[key] != item[key]:
                raise ValueError("Independent scene verification differs from a capture")
        if measured["camera_condition_hash"] != item["camera_condition"]["camera_condition_hash"]:
            raise ValueError("Verified camera identity differs from the capture")
    return {"path": str(path), "sha256": client.live.digest(path), "passed": True,
            "captures_verified": 10, "kind": result["kind"]}


def load_group(group, declaration, pins, verifications, require_verification):
    group = retained_group(group)
    result_path = group.parent / "group_result.json"
    result = read(pins.add(result_path))
    manifest = read(pins.add(group / "manifest.json"))
    if result.get("passed") is not True or result.get("held_state") is not True:
        raise ValueError("The completed client group did not pass its source-state checks")
    if not all(result.get("coexistence_checks", {"missing": False}).values()):
        raise ValueError("The original demonstration did not pass group coexistence checks")
    runs = [run for run in declaration["runs"] if run["run_id"] == result["run_id"]]
    if len(runs) != 1:
        raise ValueError("A captured group is outside the prior declared runs")
    run = runs[0]
    states = [state for state in run["selected_states"] if state["step_index"] == result["step_index"]]
    if (len(states) != 1 or result["source_state"] != states[0]
            or result["split"] != run["split"] or result["encounter_group_id"] != run["encounter_group_id"]):
        raise ValueError("Capture selection or trajectory/encounter split differs from declaration")
    state = states[0]
    checks = client.validate_group(group, state, result["capture_response"])
    if checks != result["group_checks"]:
        raise ValueError("Repeated client validation differs from its retained accepted result")
    scene_check = None
    if str(group) in verifications:
        scene_check = check_verification(group, manifest, verifications[str(group)], pins)
    elif require_verification:
        raise ValueError("A final contact sheet lacks independent retained-USD verification")
    return {"group": group, "manifest": manifest, "result": result, "run": run,
            "state": state, "scene_verification": scene_check}


def image_view(entry, item, pins):
    group = entry["group"]
    paths = {name: pins.add(client.live.group_file(group, item[name], item[name.replace("_file", "_sha256")]))
             for name in ("rgb_file", "annotation_file", "yolo_file")}
    annotation = read(paths["annotation_file"])
    if item["variant"] == "absent" and (annotation["amodal_bbox_xyxy_px"] is not None
            or paths["yolo_file"].read_bytes() != b""):
        raise ValueError("A removed-target review view has a target box or label")
    with Image.open(paths["rgb_file"]) as source:
        source.load()
        if source.size != RESOLUTION or source.mode not in ("RGB", "RGBA"):
            raise ValueError("Retained full-frame RGB has unexpected dimensions or channels")
        mode = source.mode
        rgb = source.convert("RGB")
        extrema = rgb.getextrema()
        deviation = ImageStat.Stat(rgb).stddev
        spatially_nonconstant = any(low != high for low, high in extrema)
        display = rgb.resize(DISPLAY_RESOLUTION, Image.Resampling.LANCZOS)
    box = annotation["amodal_bbox_xyxy_px"] if item["target_present"] else None
    if box is not None:
        ImageDraw.Draw(display).rectangle(tuple(value * .5 for value in box), outline=(255, 190, 35), width=2)
    state, run = entry["state"], entry["run"]
    record = {"image_id": f"{run['run_id']}__step_{state['step_index']:03d}__{item['variant']}__gsd_{item['gsd_cm_px']:g}",
              "run_id": run["run_id"], "seed": run["seed"], "step_index": state["step_index"],
              "simulation_time_s": state["simulation_time_s"], "split": run["split"],
              "encounter_group_id": run["encounter_group_id"], "related_run_ids": run["related_run_ids"],
              "source_canonical_state_sha256": run["canonical_state_sha256"],
              "variant": item["variant"], "target_present": item["target_present"], "gsd_cm_px": item["gsd_cm_px"],
              "behavioural_state": state["agents"][0]["behavioural_state"],
              "original_gama_depth_m": state["agents"][0]["depth_m"],
              "rgb_file": str(paths["rgb_file"]), "rgb_sha256": item["rgb_sha256"],
              "annotation_file": str(paths["annotation_file"]), "annotation_sha256": item["annotation_sha256"],
              "yolo_file": str(paths["yolo_file"]), "yolo_sha256": item["yolo_sha256"],
              "source_resolution_px": list(RESOLUTION), "source_rgb_mode": mode,
              "display_resolution_px": list(DISPLAY_RESOLUTION), "display_scale": .5, "cropped": False,
              "rgb_channel_extrema": extrema, "rgb_channel_standard_deviation": deviation,
              "spatially_nonconstant": spatially_nonconstant,
              "uniform_rgb_requires_manual_review": not spatially_nonconstant,
              "spatial_variation_is_an_acceptance_gate": False,
              "camera_condition_hash": item["camera_condition"]["camera_condition_hash"],
              "variant_scene_hash": item["resolved_scene_state_hash"], "parent_scene_hash": item["parent_scene_hash"],
              "background_scene_hash": item["background_scene_hash"],
              "annotation_semantics": annotation["annotation_semantics"],
              "annotation_status": annotation["annotation_status"], "rendered_visibility": "unknown",
              "amodal_bbox_xyxy_px": box, "amodal_rectangle_overlay_drawn": box is not None,
              "overlay_is_exact_visible_or_refracted_outline": False, "biological_approval": False}
    return display, record


def sheet(entry, output, pins):
    margin, title_height, caption_height, footer_height = 12, 100, 32, 86
    tile_width, tile_height = DISPLAY_RESOLUTION
    width = 5 * tile_width + 6 * margin
    height = title_height + 2 * (caption_height + tile_height) + 3 * margin + footer_height
    canvas = Image.new("RGB", (width, height), (18, 25, 34))
    draw = ImageDraw.Draw(canvas)
    state, run = entry["state"], entry["run"]
    title = f"{run['run_id']} | seed {run['seed']} | step {state['step_index']:03d} | {run['split']}"
    draw.text((margin, 12), title, fill=(241, 245, 249), font=font(26))
    draw.text((margin, 51), f"t={state['simulation_time_s']:g} s | {state['agents'][0]['behavioural_state']} | root depth {state['agents'][0]['depth_m']:g} m | full frames at 50%; no crop",
              fill=(180, 203, 224), font=font(20))
    captures = entry["manifest"]["captures"]
    records = []
    for index, item in enumerate(captures):
        row, column = divmod(index, 5)
        if item["variant"] != ("present" if row == 0 else "absent") or item["gsd_cm_px"] != GSDS[column]:
            raise ValueError("A contact sheet lacks its ordered five-GSD positive/negative pair")
        display, record = image_view(entry, item, pins)
        left = margin + column * (tile_width + margin)
        top = title_height + margin + row * (caption_height + tile_height + margin)
        caption = f"{item['gsd_cm_px']:g} cm/px | " + ("present; amodal box" if row == 0 else "removed; no target label")
        draw.text((left, top), caption, fill=(255, 202, 90) if row == 0 else (161, 226, 200), font=font(17))
        canvas.paste(display, (left, top + caption_height))
        record.update(sheet_row=row, sheet_column=column, display_origin_px=[left, top + caption_height])
        records.append(record)
    footer_y = height - footer_height + 8
    draw.text((margin, footer_y), "Gold rectangles: direct amodal mesh boxes; no exact visible/refracted outline. Physical presence is independent of rendered visibility.",
              fill=(213, 223, 235), font=font(18))
    draw.text((margin, footer_y + 29), "Engineering review only | Visibility remains unknown until inspected | Static pose proxy; biological suitability remains provisional.",
              fill=(164, 185, 206), font=font(18))
    name = f"{run['run_id']}__step_{state['step_index']:03d}.png"
    path = output / name
    with path.open("xb") as stream:
        canvas.save(stream, format="PNG")
    for record in records:
        record["contact_sheet"] = str(path)
    return {"file": str(path), "sha256": client.live.digest(path), "resolution_px": [width, height],
            "run_id": run["run_id"], "seed": run["seed"], "step_index": state["step_index"],
            "split": run["split"], "group_manifest": str(entry["group"] / "manifest.json"),
            "group_manifest_sha256": client.live.digest(entry["group"] / "manifest.json"),
            "parent_scene_hash": entry["manifest"]["parent_scene_hash"],
            "background_scene_hash": entry["manifest"]["background_scene_hash"],
            "scene_verification": entry["scene_verification"], "images": records}


def check_campaign(campaign, pins):
    report = read(pins.add(campaign / "results.json"))
    if (report.get("passed") is not True or report.get("preflight_only") is not False
            or report.get("runtime_code_unchanged") is not True or report.get("declaration_unchanged") is not True
            or report.get("capture_counts") != {"target_present": 75, "target_absent": 75, "groups": 15}
            or report.get("biological_approval") is not False):
        raise ValueError("The completed 150-view campaign did not pass")
    declaration_path = pins.add(campaign / "declaration.json", report["declaration"]["sha256"])
    declaration = client.validate_declaration(declaration_path)
    split_path = pins.add(campaign / "trajectory_split_manifest.json", report["trajectory_split_manifest"]["sha256"])
    split = read(split_path)
    images = split["images"]
    if (len(images) != 150 or images != report["traceable_images"]
            or split["target_present_captures"] != 75 or split["target_absent_captures"] != 75
            or split.get("related_trajectories_cross_splits") is not False
            or split.get("biological_approval") is not False or split.get("rendered_visibility") != "unknown"
            or split["declaration"] != report["declaration"]):
        raise ValueError("The trajectory split manifest does not bind all accepted campaign images")
    assignments = {}
    expected_assignments = []
    expected_ids = set()
    for run in declaration["runs"]:
        expected_assignments.append({key: run[key] for key in ("run_id", "related_run_ids", "encounter_group_id", "split")})
        for related in run["related_run_ids"]:
            if related in assignments and assignments[related] != run["split"]:
                raise ValueError("Related trajectories crossed dataset splits")
            assignments[related] = run["split"]
        for state in run["selected_states"]:
            for variant in ("present", "absent"):
                for gsd in GSDS:
                    expected_ids.add(f"{run['run_id']}__step_{state['step_index']:03d}__{variant}__gsd_{gsd:g}")
    if (split["trajectory_assignments"] != expected_assignments or split["related_run_split_assignments"] != assignments
            or len({image["image_id"] for image in images}) != 150
            or {image["image_id"] for image in images} != expected_ids):
        raise ValueError("Missing, duplicate or leaked trajectory/step/GSD/presence views")
    for image in images:
        run = next(run for run in declaration["runs"] if run["run_id"] == image["run_id"])
        if (image["split"] != run["split"] or image["seed"] != run["seed"]
                or image["encounter_group_id"] != run["encounter_group_id"]
                or image["related_run_ids"] != run["related_run_ids"]):
            raise ValueError("An image crosses its declared trajectory/encounter split")
    groups = []
    if len(report["runs"]) != 5:
        raise ValueError("Expected exactly five accepted actual GAMA runs")
    for run in report["runs"]:
        if run.get("passed") is not True or len(run["groups"]) != 3:
            raise ValueError("A declared run did not complete all three selected snapshots")
        for result in run["groups"]:
            if result.get("passed") is not True:
                raise ValueError("A captured snapshot group did not pass")
            groups.append(campaign / "captures" / result["run_id"] / f"step_{result['step_index']:03d}" / "group")
    return declaration, images, groups


def markdown(index):
    text = ["# M7 retained capture review", "",
            f"{len(index['contact_sheets'])} sheets, {len(index['images'])} full-frame views at 50% scale; no crops.", "",
            "Gold overlays are direct amodal mesh rectangles. They are not exact visible or refracted underwater outlines. Negative counterparts physically removed the owned target and have empty labels.", "",
            "This is an engineering review index. Rendered animal visibility has not been inferred from pixels; biological suitability remains provisional.", ""]
    for observation in index["engineering_observations"]:
        text.append("- " + observation)
    text.append("")
    for item in index["contact_sheets"]:
        text.extend((f"## {item['run_id']} — step {item['step_index']:03d}", "",
                     f"Seed {item['seed']}; split **{item['split']}**. Top row: target present. Bottom row: target physically removed. Columns: 0.5, 1, 2, 3, 4 cm/px.", "",
                     f"![Full-frame paired contact sheet](<{item['file']}>)", "",
                     f"[Accepted group manifest](<{item['group_manifest']}>)", ""))
    return "\n".join(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--group", type=Path, help="Completed retained group or step directory")
    mode.add_argument("--campaign", type=Path, help="Completed accepted 150-image campaign")
    parser.add_argument("--scene-verifications", nargs="+", type=Path, default=[], help="Independent verification JSON files/directories")
    parser.add_argument("--output", required=True, type=Path, help="Fresh exclusive review directory")
    parser.add_argument("--observation", action="append", default=[], help="Explicit engineering free-text observation; never biological approval")
    args = parser.parse_args()
    output = client.live.safe_path(args.output)
    if output.exists():
        raise ValueError("Review output already exists; preserve it and choose a fresh directory")
    pins = InputPins()
    verifications = load_verifications(args.scene_verifications, pins)
    if args.campaign:
        campaign = client.live.safe_path(args.campaign)
        declaration, campaign_images, groups = check_campaign(campaign, pins)
        require_verification = True
    else:
        group = retained_group(args.group)
        declaration_path = pins.add(declaration_for_group(group))
        declaration = client.validate_declaration(declaration_path)
        groups, campaign_images, require_verification = [group], None, False
    if any(output.is_relative_to(group) for group in groups):
        raise ValueError("Review outputs must be outside retained capture groups")
    entries = [load_group(group, declaration, pins, verifications, require_verification) for group in groups]
    if args.campaign and (len(entries) != 15 or len({str(entry['group']) for entry in entries}) != 15):
        raise ValueError("Expected 15 distinct independently verified captured snapshots")
    output.mkdir(parents=True, exist_ok=False)
    try:
        sheets = [sheet(entry, output, pins) for entry in entries]
        images = [image for item in sheets for image in item["images"]]
        if campaign_images is not None:
            recorded = {image["image_id"]: image for image in campaign_images}
            if len(recorded) != len(images):
                raise ValueError("The review index does not cover the exact accepted campaign")
            for image in images:
                row = recorded[image["image_id"]]
                for key in ("run_id", "seed", "step_index", "simulation_time_s", "split", "variant", "target_present",
                            "gsd_cm_px", "rgb_sha256", "annotation_sha256", "yolo_sha256", "camera_condition_hash",
                            "variant_scene_hash", "parent_scene_hash", "background_scene_hash"):
                    if image[key] != row[key]:
                        raise ValueError("A review view differs from its accepted split-manifest row")
                for key in ("rgb_file", "annotation_file", "yolo_file"):
                    if Path(image[key]) != client.live.safe_path(campaign / row[key]):
                        raise ValueError("A review view references a different retained source file")
        preserved = pins.finish()
        index = {"kind": "m7_capture_visual_index", "milestone": 7, "passed": True,
                 "mode": "accepted_campaign" if args.campaign else "completed_group_preview",
                 "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
                 "generator_sha256": client.live.digest(Path(__file__).resolve()),
                 "font": {"path": str(FONT_PATH), "sha256": client.live.digest(FONT_PATH)} if FONT_PATH.is_file() else {"path": "Pillow default"},
                 "contact_sheets": sheets, "images": images, "source_hashes_before_after": preserved,
                 "all_pinned_review_inputs_unchanged": True,
                 "preservation_scope": "Before/after hashes cover the explicitly listed review inputs: declarations, accepted results, split/group manifests, RGB images, annotations, YOLO labels and independent verification JSON. USD scenes, probes, sidecars and local dependencies are validated by the client/independent scene checks; their broader preservation is covered by the campaign and milestone preservation reports.",
                 "full_frames_uncropped": True,
                 "display_scale": .5, "all_rgb_1024x768_decodable": True,
                 "all_frames_spatially_nonconstant": all(image["spatially_nonconstant"] for image in images),
                 "uniform_frames_for_manual_review": [image["image_id"] for image in images if not image["spatially_nonconstant"]],
                 "spatial_variation_is_an_acceptance_gate": False,
                 "independent_scene_verifications_passed": sum(item["scene_verification"] is not None for item in sheets),
                 "label_semantics": "Direct amodal evaluated mesh rectangle; no exact visible/refracted outline",
                 "rendered_visibility": "unknown", "automatic_animal_visibility_threshold_used": False,
                 "visual_inspection_completed": False, "biological_approval": False,
                 "engineering_observations": args.observation or ["Contact sheets are ready for visual inspection; generation alone did not classify animal visibility."],
                 "live_calls_made": False}
        write(output / "visual_index.json", index)
        with (output / "index.md").open("x") as stream:
            stream.write(markdown(index))
        write(output / "review_artifacts.json", {"passed": True, "files": [
            {"path": str(path), "bytes": path.stat().st_size, "sha256": client.live.digest(path)}
            for path in [*(Path(item["file"]) for item in sheets), output / "visual_index.json", output / "index.md"]]})
        print(json.dumps({"passed": True, "sheets": len(sheets), "views": len(images),
                          "scene_verifications": index["independent_scene_verifications_passed"],
                          "index": str(output / "visual_index.json")}, indent=2))
    except BaseException as error:
        write(output / "build_failed.json", {"passed": False, "error": f"{type(error).__name__}: {error}",
                                             "recorded_at_utc": datetime.now(timezone.utc).isoformat()})
        raise


if __name__ == "__main__":
    main()
