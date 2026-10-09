"""Retained M6 RGB comparison and uncropped contact sheet; no Kit/API calls.

Reproduce into a NEW directory with /usr/bin/python3 -B analyze_m6_pixels.py
--output-dir <new-directory> --visibility-note '<honest inspection note>'.
The accepted originals are opened read-only. Metrics have no pass threshold.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat, __version__ as pillow_version

QA = Path(__file__).resolve().parent
ROOT = QA.parents[2]
ORDERS = [[.5, 1., 2., 3., 4.], [4., 3., 2., 1., .5]]
FORBIDDEN = {"_build", "extscache", "__pycache__", ".cache"}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def allowed(path):
    path = Path(path)
    if FORBIDDEN.intersection(path.parts) or path.suffix == ".pyc":
        raise ValueError("Generated paths are prohibited")
    resolved = path.resolve()
    if FORBIDDEN.intersection(resolved.parts) or resolved.suffix == ".pyc":
        raise ValueError("Generated paths are prohibited")
    return resolved


def label_path(path):
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def font(size):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default(size=size)


def compare(a, b):
    difference = ImageChops.difference(a, b)
    extrema = difference.getextrema()
    any_channel = ImageChops.lighter(ImageChops.lighter(*difference.split()[:2]), difference.split()[2])
    total = a.width * a.height
    different = total - any_channel.histogram()[0]
    mean = sum(ImageStat.Stat(difference).mean) / 3
    return {"decoded_rgb_pixels_equal": different == 0,
            "mean_absolute_rgb_difference_0_to_255": mean,
            "fraction_differing_pixels": different / total,
            "differing_pixel_count": different, "total_pixel_count": total,
            "maximum_absolute_channel_difference_0_to_255": max(hi for _, hi in extrema)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", type=Path, default=QA / "m6_live_03/group")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--visibility-note", default="Visual inspection pending; nonblank pixels alone do not establish animal visibility.")
    args = parser.parse_args()
    group, output = allowed(args.group), allowed(args.output_dir)
    if output == group or output.is_relative_to(group):
        raise ValueError("Outputs must be outside the retained input group")
    output.mkdir(parents=True, exist_ok=True)
    result_path = output / "m6_pixel_repeat_analysis.json"
    sheet_path = output / "m6_paired_contact_sheet.png"
    if result_path.exists() or sheet_path.exists():
        raise FileExistsError("Analysis outputs must be new; existing evidence is never replaced")
    manifest_path, results_path = group / "manifest.json", group.parent / "results.json"
    source_hashes = {manifest_path: sha256(manifest_path), results_path: sha256(results_path)}
    manifest = json.loads(manifest_path.read_text())
    results = json.loads(results_path.read_text())
    if (manifest.get("passed") is not True or manifest.get("status") != "passed"
            or results.get("passed") is not True or manifest.get("orders") != ORDERS
            or manifest.get("recovery_required") is not False
            or len(manifest.get("captures", [])) != 10):
        raise ValueError("An accepted, safely restored ten-image M6 group is required")
    images, records, paired = [], [], {}
    for index, item in enumerate(manifest["captures"]):
        order, condition = divmod(index, 5)
        if (item["order_index"] != order or item["condition_index"] != condition
                or item["gsd_cm_px"] != ORDERS[order][condition]):
            raise ValueError("Capture order differs from the accepted workload")
        relative = Path(item["rgb_file"])
        path = allowed(group / relative)
        if relative.is_absolute() or not path.is_relative_to(group):
            raise ValueError("Capture path escaped the retained group")
        source_hashes[path] = sha256(path)
        if source_hashes[path] != item["rgb_sha256"]:
            raise ValueError("Retained original PNG differs from the capture manifest")
        with Image.open(path) as source:
            source.load()
            if source.format != "PNG" or source.size != (1024, 768):
                raise ValueError("All original captures must be 1024 x 768 PNGs")
            original_mode = source.mode
            image = source.convert("RGB")
        extrema = image.getextrema()
        nonblank = any(lo != hi for lo, hi in extrema)
        if not nonblank:
            raise ValueError("An accepted capture is spatially constant/blank")
        record = {"order_index": order, "condition_index": condition,
                  "gsd_cm_px": item["gsd_cm_px"], "source_png": label_path(path),
                  "png_sha256": source_hashes[path],
                  "decoded_rgb_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
                  "original_mode": original_mode, "analysis_mode": "RGB",
                  "dimensions_px": list(image.size), "spatially_nonconstant": nonblank,
                  "rgb_channel_ranges_0_to_255": [list(bounds) for bounds in extrema],
                  "rgb_channel_means_0_to_255": ImageStat.Stat(image).mean,
                  "resolved_scene_state_hash": item["resolved_scene_state_hash"],
                  "camera_condition_hash": item["camera_condition"]["camera_condition_hash"]}
        images.append(image)
        records.append(record)
        paired[(item["gsd_cm_px"], order)] = (image, record)
    pairs = []
    for gsd in ORDERS[0]:
        a, ra = paired[(gsd, 0)]
        b, rb = paired[(gsd, 1)]
        pairs.append({"gsd_cm_px": gsd, "first_source_png": ra["source_png"],
                      "second_source_png": rb["source_png"],
                      "first_png_sha256": ra["png_sha256"], "second_png_sha256": rb["png_sha256"],
                      "png_files_byte_identical": ra["png_sha256"] == rb["png_sha256"],
                      "camera_condition_hashes_equal": ra["camera_condition_hash"] == rb["camera_condition_hash"],
                      **compare(a, b)})
    # Every complete frame is resized at the same 1:2 scale, never cropped.
    thumb_width, thumb_height, gutter, label_height = 512, 384, 14, 52
    width = 5 * thumb_width + 6 * gutter
    header_height, footer_height = 78, 66
    height = header_height + 2 * (thumb_height + label_height + gutter) + footer_height
    sheet = Image.new("RGB", (width, height), "#f5f7fa")
    draw = ImageDraw.Draw(sheet)
    draw.text((gutter, 10), "M6: accepted actual GAMA step 8, t=4 s; seed 184729", font=font(25), fill="#101925")
    draw.text((gutter, 43), "Ten complete 1024 x 768 frames shown at 50% scale; original capture order retained", font=font(19), fill="#28374b")
    for index, (image, record) in enumerate(zip(images, records)):
        row, column = divmod(index, 5)
        x = gutter + column * (thumb_width + gutter)
        y = header_height + row * (thumb_height + label_height + gutter)
        direction = "ascending" if record["order_index"] == 0 else "descending, 2 s delay"
        draw.text((x, y), f"Order {record['order_index'] + 1}, capture {record['condition_index'] + 1} ({direction})", font=font(17), fill="#101925")
        draw.text((x, y + 23), f"GSD {record['gsd_cm_px']:g} cm/px at root plane", font=font(19), fill="#101925")
        sheet.paste(image.resize((thumb_width, thumb_height), Image.Resampling.LANCZOS), (x, y + label_height))
    draw.text((gutter, height - 53), "Frozen scene identity and repeated RGB equality are separate measurements. No pixel-repeatability threshold was imposed.", font=font(18), fill="#28374b")
    draw.text((gutter, height - 28), "Overview only: full-frame variation does not prove animal visibility, optical calibration or anatomical detail at every GSD.", font=font(18), fill="#28374b")
    with sheet_path.open("xb") as stream:
        sheet.save(stream, format="PNG")
    preserved = all(sha256(path) == original for path, original in source_hashes.items())
    if not preserved:
        raise ValueError("An input changed during analysis; retain this failed output for inspection")
    scene_hashes = {record["resolved_scene_state_hash"] for record in records}
    if scene_hashes != {manifest["resolved_scene_state_hash"]}:
        raise ValueError("Capture identities differ from the accepted group manifest")
    report = {"schema_version": "1.0", "milestone": 6,
              "generated_at_utc": datetime.now(timezone.utc).isoformat(),
              "analysis_completed": True, "input_group_accepted": True,
              "input_manifest": label_path(manifest_path), "input_manifest_sha256": source_hashes[manifest_path],
              "input_results": label_path(results_path), "input_results_sha256": source_hashes[results_path],
              "source_state": manifest["source_state"], "orders": manifest["orders"],
              "artificial_delay_s": manifest["artificial_delay_s"],
              "image_count": len(records), "all_images_1024_by_768_and_spatially_nonconstant": True,
              "nonblank_definition": "At least one decoded RGB channel has a spatial range greater than zero; this does not test animal visibility.",
              "all_original_input_hashes_unchanged_after_analysis": preserved,
              "resolved_scene_identity": {"all_ten_equal": len(scene_hashes) == 1,
                                          "sha256": manifest["resolved_scene_state_hash"],
                                          "manifest_state_checks": len(manifest["state_checks"]),
                                          "scope": "Frozen resolved biological/environmental content; camera and RGB identities are separate."},
              "pixel_analysis": {"comparison": "same GSD across ascending and delayed descending orders",
                                 "rgb_conversion": "Pillow convert('RGB'), encoded 8-bit channels; no linear-light/colorimetric calibration",
                                 "mean_absolute_difference_equation": "sum(abs(A[x,y,c]-B[x,y,c])) / (width*height*3), raw 0..255",
                                 "fraction_differing_pixels_equation": "count(pixels with any unequal RGB channel) / (width*height)",
                                 "maximum_difference_equation": "max(abs(A[x,y,c]-B[x,y,c])) over all pixels/channels",
                                 "new_pixel_acceptance_threshold": None,
                                 "all_five_pairs_decoded_rgb_equal": all(pair["decoded_rgb_pixels_equal"] for pair in pairs),
                                 "all_five_pairs_png_byte_identical": all(pair["png_files_byte_identical"] for pair in pairs),
                                 "interpretation": "Observed pixel differences are reported descriptively; matching frozen scene hashes do not imply matching RGB.",
                                 "pairs": pairs},
              "images": records,
              "contact_sheet": {"path": label_path(sheet_path), "sha256": sha256(sheet_path),
                                "dimensions_px": list(sheet.size), "all_ten_full_frames_in_actual_order": True,
                                "crop_applied": False, "display_scale": .5},
              "visibility_review": {"note": args.visibility_note,
                                    "animal_visibility_tested_automatically": False,
                                    "anatomical_pose_validated": False,
                                    "biological_approval": False},
              "reproduction": {"script": label_path(Path(__file__).resolve()), "script_sha256": sha256(Path(__file__).resolve()),
                               "python_executable_used": "/usr/bin/python3", "pillow_version": pillow_version,
                               "command": "/usr/bin/python3 -B experiments/gama_marlin_v1/qa/analyze_m6_pixels.py --output-dir <new-directory> --visibility-note '<inspection note>'"}}
    with result_path.open("x") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"analysis": str(result_path), "sheet": str(sheet_path), "pairs": pairs}, indent=2))


if __name__ == "__main__":
    main()
