"""Read-only Pilot v1 input, metric and annotation audit; no model inference.

Run in the retained Pilot Python environment with CUDA_VISIBLE_DEVICES empty.
Only the requested, new GAMA-sprint JSON evidence file is written. The original
Pilot scripts' main functions are never called.
"""
import argparse
import ast
import base64
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import inspect
import json
import math
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
PILOT = ROOT / "experiments/gsd_pilot_v1"
QA = Path(__file__).resolve().parent
FORBIDDEN = frozenset(("_build", "extscache", "__pycache__", ".cache"))


def safe(path):
    path = Path(path)
    if FORBIDDEN.intersection(path.parts) or path.suffix == ".pyc":
        raise ValueError("Refusing generated input")
    path = path.resolve()
    if not path.is_relative_to(ROOT) or FORBIDDEN.intersection(path.parts):
        raise ValueError("Input escaped the repository or resolved into generated files")
    return path


def sha(path):
    value = hashlib.sha256()
    with safe(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def pin(path):
    path = safe(path)
    return {"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": sha(path)}


def read(path):
    return json.loads(safe(path).read_text())


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, safe(path))
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def grouping_function():
    # Extract the pure aggregation function without importing the training file,
    # which sets TORCH_HOME and exposes write/training entry points.
    tree = ast.parse((PILOT / "ml/train_evaluate.py").read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "by_gsd_and_species")
    namespace = {"summarize": module("_m8_pilot_metrics", PILOT / "ml/metrics.py").summarize}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(PILOT / "ml/train_evaluate.py"), "exec"), namespace)
    return namespace["by_gsd_and_species"]


def wheel_record_checks(site, filenames):
    result = []
    for distribution, prefix in (("torchvision", "torchvision/"), ("torch", "torch/"), ("pillow", "PIL/")):
        records = list(site.glob(distribution + "-*.dist-info/RECORD"))
        if len(records) != 1:
            raise ValueError("Expected one installed distribution RECORD: " + distribution)
        record = records[0]
        with record.open(newline="") as stream:
            rows = {row[0]: row for row in csv.reader(stream)}
        for path in filenames:
            relative = str(path.relative_to(site))
            if not relative.startswith(prefix):
                continue
            expected = rows[relative][1]
            assert expected.startswith("sha256=")
            actual = "sha256=" + base64.urlsafe_b64encode(bytes.fromhex(sha(path))).decode().rstrip("=")
            assert actual == expected, relative + " differs from installed wheel RECORD"
            result.append({"source": pin(path), "distribution_record": pin(record), "record_entry_hash": expected, "passed": True})
    return result


def audit():
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        raise ValueError("Run this CPU-only audit with CUDA_VISIBLE_DEVICES empty")
    import numpy as np
    import PIL
    from PIL import Image, ImageChops
    import torch
    import torchvision
    from torchvision.models.detection.transform import GeneralizedRCNNTransform

    torch.set_num_threads(1)
    lock = read(PILOT / "ml/detector_lock.json")
    assert torch.__version__ == lock["torch_version"]
    assert torchvision.__version__ == lock["torchvision_version"]
    site = safe(Path(torchvision.__file__).parent.parent)
    source_names = ["ml/dataset.py", "ml/metrics.py", "ml/train_evaluate.py", "ml/lock_detector.py",
        "ml/detector_lock.json", "ml/requirements-cu126.lock", "ml/m6_freeze.py", "ml/verify_loader.py",
        "results/M8_FINAL_REPORT.md", "results/m7_test_predictions.json", "results/m7_test_metrics.json",
        "results/m7_validation_selection.json", "results/m7_training_history.json", "results/m8_analyse.py",
        "results/m8_gsd_analysis.json", "splits/image_assignments.json", "splits/scene_groups.json",
        "splits/train.json", "splits/validation.json", "splits/test.json", "specification.json",
        "annotations/milestone_5_coco.json", "annotations/milestone_5_geometry.json", "annotations/milestone_5_frames.json",
        "qa/m6_input_validation.json", "qa/m6_loader_validation.json", "qa/m7_result_validation.json",
        "qa/m5_dataset_validation.json", "qa/m4_geometry.py", "qa/m5_geometry.py", "qa/m5_validate_dataset.py",
        "scenes/build_scenes.py"]
    sources = [PILOT / name for name in source_names]
    libraries = [site / name for name in ("torchvision/models/detection/transform.py",
        "torchvision/models/detection/generalized_rcnn.py", "torchvision/models/detection/faster_rcnn.py",
        "torchvision/models/detection/roi_heads.py", "torchvision/models/detection/rpn.py",
        "torchvision/ops/boxes.py", "torch/nn/functional.py", "PIL/ImageOps.py")]
    sources += libraries + [Path(__file__)]
    initial_pins = [pin(path) for path in sources]
    wheel_checks = wheel_record_checks(site, libraries)
    baseline = read(QA / "preserved_output_manifest.json")
    sealed = {row["path"]: row for row in baseline["files"]}
    historical_checks = []
    for current in initial_pins:
        if current["path"] in sealed:
            assert current == sealed[current["path"]], current["path"] + " changed from the preserved Pilot"
            historical_checks.append(current)
    dataset = module("_m8_pilot_dataset", PILOT / "ml/dataset.py")
    assignments = read(PILOT / "splits/image_assignments.json")["images"]
    assert len(assignments) == 300 and len({r["image_id"] for r in assignments}) == 300
    images = []
    counts = Counter()
    for record in assignments:
        path = PILOT / record["image_path"]
        image_pin = pin(path)
        assert image_pin["sha256"] == record["image_sha256"]
        padded, boxes = dataset.prepare(record)
        with Image.open(safe(path)) as original:
            original.load()
            assert original.size == (1024, 768)
            if original.mode == "RGBA":
                assert original.getchannel("A").getextrema() == (255, 255)
            rgb = original.convert("RGB")
            assert ImageChops.difference(rgb, padded.crop((0, 128, 1024, 896))).getbbox() is None
        pixels = np.asarray(padded)
        assert padded.size == (1024, 1024) and padded.mode == "RGB"
        assert np.all(pixels[:128] == 114) and np.all(pixels[896:] == 114)
        positive = record["intervention"] == "target_present"
        assert len(boxes) == int(positive)
        if positive:
            x, y, w, h = record["original_bbox_xywh_px"]
            assert record["model_bbox_xywh_px"] == [x, y + 128, w, h]
            # Follow the retained adapter's actual addition order. Floating-point
            # addition is not associative when translating a subpixel box.
            assert boxes == [[x, y + 128, x + w, (y + 128) + h]]
            assert record["original_pixels_on_target"] == record["model_input_pixels_on_target"]
        else:
            assert record["original_bbox_xywh_px"] is None and record["model_bbox_xywh_px"] is None
        counts[(record["split"], record["intervention"])] += 1
        images.append(image_pin)
    transform = GeneralizedRCNNTransform(lock["model_min_size"], lock["model_max_size"],
                                         lock["normalization_mean_rgb"], lock["normalization_std_rgb"])
    assert transform.size_divisible == 32 and transform.fixed_size is None and transform._skip_resize is False
    actual_interpolate = torch.nn.functional.interpolate
    interpolation_calls = []

    def observe(image, *args, **kwargs):
        interpolation_calls.append({"input_shape": list(image.shape), "arguments": kwargs,
            "antialias_default": inspect.signature(actual_interpolate).parameters["antialias"].default})
        return actual_interpolate(image, *args, **kwargs)

    transform_checks = []
    for split in ("train", "validation", "test"):
        loaded = dataset.DetectionDataset(split)
        for presence in ("target_present", "target_absent"):
            index = next(i for i, r in enumerate(loaded.items) if r["intervention"] == presence)
            tensor, target = loaded[index]
            assert list(tensor.shape) == [3, 1024, 1024] and tensor.dtype == torch.float32
            expected = (tensor - torch.tensor(transform.image_mean)[:, None, None]) / torch.tensor(transform.image_std)[:, None, None]
            for training in (True, False):
                transform.train(training)
                before = target["boxes"].clone()
                with torch.no_grad(), patch("torch.nn.functional.interpolate", side_effect=observe):
                    processed, targets = transform([tensor], [target])
                assert processed.image_sizes == [(1024, 1024)]
                assert list(processed.tensors.shape) == [1, 3, 1024, 1024]
                assert torch.equal(processed.tensors[0], expected)
                assert torch.equal(targets[0]["boxes"], before) and torch.equal(target["boxes"], before)
                transform_checks.append({"image_id": loaded.items[index]["image_id"], "split": split,
                    "intervention": presence, "training_mode": training, "batch_shape_nchw": list(processed.tensors.shape),
                    "normalized_tensor_equal_at_unit_scale": True, "boxes_unchanged": True})
    assert len(interpolation_calls) == 12
    assert all(call["arguments"] == {"size": None, "scale_factor": 1.0, "mode": "bilinear", "recompute_scale_factor": True, "align_corners": False}
               and call["antialias_default"] is False for call in interpolation_calls)
    metrics = read(PILOT / "results/m7_test_metrics.json")
    frames = read(PILOT / "results/m7_test_predictions.json")
    threshold = metrics["confidence_threshold_selected_on_validation"]
    assert grouping_function()(frames, threshold) == metrics["metrics"]
    assignment_map = {r["image_id"]: r for r in assignments}
    assert len(frames) == 60 and len({f["image_id"] for f in frames}) == 60
    for frame in frames:
        record = assignment_map[frame["image_id"]]
        assert record["split"] == "test"
        for key in ("scene_id", "species", "requested_gsd_cm_px", "intervention"):
            assert record[key] == frame[key]
        box = record["model_bbox_xywh_px"]
        expected = None if box is None else torch.tensor([box[0], box[1], box[0]+box[2], box[1]+box[3]], dtype=torch.float32).tolist()
        assert frame["gt_box_xyxy_px"] == expected
    coco = read(PILOT / "annotations/milestone_5_coco.json")
    geometry = read(PILOT / "annotations/milestone_5_geometry.json")["records"]
    geometry_map = {(g["scene_id"], g["gsd_cm_px_requested"]): g for g in geometry}
    assert len(coco["annotations"]) == len(geometry_map) == 250
    assert coco["categories"] == [{"id": 1, "name": "wildlife"}]
    for annotation in coco["annotations"]:
        record = assignment_map[annotation["image_id"]]
        evaluated = geometry_map[(record["scene_id"], record["requested_gsd_cm_px"])]
        assert annotation["bbox"] == record["original_bbox_xywh_px"] == evaluated["amodal_bbox_coco_xywh_px"]
        assert annotation["category_id"] == 1 and annotation["iscrowd"] == 0
        assert annotation["bbox_semantics"] == "amodal_direct_evaluated_mesh_projection"
        assert annotation["area_semantics"] == "bbox_area_for_detection_only"
        assert annotation["area"] == annotation["bbox"][2] * annotation["bbox"][3]
        assert evaluated["projected_silhouette_area_px"] is None and evaluated["visible_target_area_px"] is None
    # Verify preservation again after all reads and the CPU-only transform checks.
    assert initial_pins == [pin(path) for path in sources]
    assert images == [pin(ROOT / row["path"]) for row in images]
    return {"kind": "m8_read_only_pilot_audit", "passed": True,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Retained code/data and installed transform reproduction; no inference, retraining, live calls or old-output writes",
        "runtime": {"executable": sys.executable, "python_version": sys.version, "torch": torch.__version__,
                    "torchvision": torchvision.__version__, "numpy": np.__version__, "pillow": PIL.__version__,
                    "CUDA_VISIBLE_DEVICES": os.environ["CUDA_VISIBLE_DEVICES"]},
        "source_pins": initial_pins, "historical_pilot_source_pins_matched": historical_checks,
        "installed_source_wheel_record_checks": wheel_checks, "source_and_images_unchanged_after": True,
        "input_images_decoded_hashed_and_pixel_padding_checked": len(images), "image_pins": images,
        "split_presence_counts": {split: {presence: counts[(split, presence)] for presence in ("target_present", "target_absent")}
                                  for split in ("train", "validation", "test")},
        "cpu_transform_checks": transform_checks, "observed_interpolation_calls": interpolation_calls,
        "internal_padding_stride": transform.size_divisible, "internal_added_padding_px": [0, 0],
        "normalization_padding_value_rgb": ((torch.tensor([114/255]*3)-torch.tensor(transform.image_mean))/torch.tensor(transform.image_std)).tolist(),
        "retained_test_metric_summaries_exact": 18, "retained_test_frames_and_float32_gt_verified": len(frames),
        "retained_prediction_count": sum(len(f["predictions"]) for f in frames),
        "retained_lowest_prediction_score": min(p["score"] for f in frames for p in f["predictions"]),
        "test_overall": metrics["metrics"]["overall"], "selected_confidence_threshold": threshold,
        "annotation_boxes_linked_geometry_coco_assignment": 250, "unknown_visible_and_silhouette_areas": 250,
        "limitations": ["No checkpoint was loaded or detector inference rerun; historical training internals were not newly observed.",
            "Installed package source hashes and wheel RECORD entries are current-version evidence, not historical wheel-byte pins.",
            "Source matches describe the retained padded input; native detector feature-map/ROI sampling is not survey pixel sampling.",
            "Direct amodal boxes do not resolve underwater refraction, occlusion, visible masks or silhouette area.",
            "AP50 is a one-class, one-IoU custom metric; it is not full COCO AP over IoUs, classes and area ranges."],
        "biological_approval": False, "training_or_inference_performed": False, "live_calls_made": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = safe(args.output)
    if output.exists() or output.parent != QA or not output.name.startswith("m8_pilot_audit_") or output.suffix != ".json":
        raise ValueError("Use a new exclusive GAMA sprint QA m8_pilot_audit_*.json output")
    result = audit()
    with output.open("x") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": result["passed"], "output": str(output.relative_to(ROOT)),
        "images_checked": result["input_images_decoded_hashed_and_pixel_padding_checked"],
        "cpu_transform_checks": len(result["cpu_transform_checks"]), "metric_summaries": 18,
        "annotation_boxes": 250, "overall": result["test_overall"]}, indent=2))


if __name__ == "__main__":
    main()
