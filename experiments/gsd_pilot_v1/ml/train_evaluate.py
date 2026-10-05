"""Train the sole frozen M7 detector and evaluate untouched held-out scenes."""

import hashlib
import json
import os
from pathlib import Path
import random
import time

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
ART = REPO / "artifacts/gsd_pilot_v1_m7"
TORCH_HOME = REPO / "artifacts/gsd_pilot_v1_m6/torch_home"
os.environ["TORCH_HOME"] = str(TORCH_HOME)

from dataset import DetectionDataset
from metrics import ap50, select_threshold, summarize


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    os.replace(temp, path)


def setup_model(torch, device, lock):
    from torchvision.models.detection import (
        FasterRCNN_MobileNet_V3_Large_FPN_Weights,
        fasterrcnn_mobilenet_v3_large_fpn,
    )
    from torchvision.models.detection.faster_rcnn import FastRCNNPredictor

    weights = FasterRCNN_MobileNet_V3_Large_FPN_Weights.COCO_V1
    assert weights.url == lock["weights_url"]
    path = TORCH_HOME / "hub/checkpoints" / weights.url.rsplit("/", 1)[-1]
    assert sha(path) == lock["weights_sha256"]
    torch.manual_seed(lock["head_initialization_seed"])
    model = fasterrcnn_mobilenet_v3_large_fpn(
        weights=weights, min_size=1024, max_size=1024,
        box_score_thresh=0.001, box_nms_thresh=0.5,
        rpn_score_thresh=0.0,
        box_detections_per_img=100,
    )
    nfeatures = model.roi_heads.box_predictor.cls_score.in_features
    model.roi_heads.box_predictor = FastRCNNPredictor(nfeatures, 2)
    return model.to(device)


def predict(model, dataset, device, torch, amp_dtype, label):
    model.eval()
    frames = []
    start = time.monotonic()
    with torch.inference_mode():
        for n in range(len(dataset)):
            image, target = dataset[n]
            image = image.to(device)
            with torch.autocast(device_type="cuda", dtype=amp_dtype or torch.bfloat16,
                                enabled=amp_dtype is not None):
                result = model([image])[0]
            result = {k: v.detach().cpu() for k, v in result.items()}
            record = dataset.items[n]
            boxes = target["boxes"].tolist()
            predictions = []
            for box, score, cls in zip(result["boxes"].tolist(),
                                       result["scores"].tolist(), result["labels"].tolist()):
                assert cls == 1
                predictions.append({"box_xyxy_px": box, "score": score})
            frames.append({"image_id": record["image_id"], "scene_id": record["scene_id"],
                           "species": record["species"],
                           "requested_gsd_cm_px": record["requested_gsd_cm_px"],
                           "intervention": record["intervention"],
                           "gt_box_xyxy_px": boxes[0] if boxes else None,
                           "predictions": predictions})
            if (n + 1) % 20 == 0 or n + 1 == len(dataset):
                print(f"{label}: {n + 1}/{len(dataset)} images in {time.monotonic() - start:.1f}s", flush=True)
    return frames


def by_gsd_and_species(frames, threshold):
    species = sorted({f["species"] for f in frames})
    gsds = sorted({f["requested_gsd_cm_px"] for f in frames})
    result = {"overall": summarize(frames, threshold),
              "by_species": {s: summarize([f for f in frames if f["species"] == s], threshold)
                             for s in species},
              "by_gsd_cm_px": {str(g): summarize([f for f in frames if f["requested_gsd_cm_px"] == g], threshold)
                                   for g in gsds},
              "by_species_and_gsd_cm_px": {
                  s: {str(g): summarize([f for f in frames if f["species"] == s and
                                         f["requested_gsd_cm_px"] == g], threshold)
                      for g in gsds} for s in species}}
    return result


def save_torch(torch, path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    torch.save(state, temp)
    os.replace(temp, path)


def main():
    import numpy as np
    import torch
    import torchvision

    lock = json.loads((ROOT / "ml/detector_lock.json").read_text())
    assert torch.__version__ == lock["torch_version"]
    assert torchvision.__version__ == lock["torchvision_version"]
    config = lock["training"]
    assert config["epochs"] == 20 and config["batch_size"] == 1
    assert config["augmentations"] == [] and not config["test_set_tuning"]
    sealed = json.loads((ROOT / "qa/milestone_6_manifest.json").read_text())
    frozen = {r["path"]: r["sha256"] for r in sealed["outputs"]}
    for relative in ("splits/scene_groups.json", "splits/image_assignments.json",
                     "ml/detector_lock.json", "ml/requirements-cu126.lock"):
        assert sha(ROOT / relative) == frozen[relative], relative
    ART.mkdir(parents=True, exist_ok=True)
    if (ROOT / "results/m7_test_metrics.json").exists():
        raise RuntimeError("M7 test results already exist; preserve the held-out evaluation")
    seed = config["shuffle_seed"]
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    amp_dtype = torch.bfloat16 if device.type == "cuda" and torch.cuda.is_bf16_supported() else None
    amp = amp_dtype is not None
    if device.type == "cuda":
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
        gpu = torch.cuda.get_device_properties(device)
        hardware = {"device": str(device), "name": gpu.name,
                    "total_memory_bytes": gpu.total_memory,
                    "autocast_dtype": str(amp_dtype) if amp else None}
    else:
        hardware = {"device": str(device), "autocast_dtype": None}
    print("M7 hardware:", hardware, flush=True)
    train = DetectionDataset("train")
    validation = DetectionDataset("validation")
    test = DetectionDataset("test")
    assert (len(train), len(validation), len(test)) == (180, 60, 60)
    model = setup_model(torch, device, lock)
    optimizer = torch.optim.SGD(model.parameters(), lr=config["learning_rate"],
                                momentum=config["momentum"], weight_decay=config["weight_decay"])
    scaler = torch.amp.GradScaler("cuda", enabled=False)
    latest = ART / "latest.pt"
    best_path = ART / "best.pt"
    history = []
    best_ap = -1.0
    best_epoch = None
    first_epoch = 1
    if latest.exists():
        checkpoint = torch.load(latest, map_location=device, weights_only=False)
        assert checkpoint["m6_manifest_sha256"] == sha(ROOT / "qa/milestone_6_manifest.json")
        model.load_state_dict(checkpoint["model"])
        optimizer.load_state_dict(checkpoint["optimizer"])
        scaler.load_state_dict(checkpoint["scaler"])
        history = checkpoint["history"]
        best_ap = checkpoint["best_ap"]
        best_epoch = checkpoint["best_epoch"]
        first_epoch = checkpoint["epoch"] + 1
        torch.set_rng_state(checkpoint["torch_rng"])
        np.random.set_state(checkpoint["numpy_rng"])
        random.setstate(checkpoint["python_rng"])
        if amp:
            torch.cuda.set_rng_state_all(checkpoint["cuda_rng"])
        print(f"Resumed after epoch {checkpoint['epoch']}", flush=True)
    for epoch in range(first_epoch, config["epochs"] + 1):
        model.train()
        order = torch.randperm(len(train), generator=torch.Generator().manual_seed(seed + epoch)).tolist()
        epoch_loss = 0.0
        start = time.monotonic()
        for n, index in enumerate(order):
            image, target = train[index]
            image = image.to(device)
            target = {key: value.to(device) for key, value in target.items()}
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type="cuda", dtype=amp_dtype or torch.bfloat16,
                                enabled=amp):
                losses = model([image], [target])
                loss = sum(losses.values())
            if not torch.isfinite(loss):
                raise ValueError(f"Nonfinite loss at epoch {epoch}, image {index}: "
                                 + str({key: value.detach().item() for key, value in losses.items()}))
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            epoch_loss += loss.detach().item()
            if (n + 1) % 30 == 0 or n + 1 == len(order):
                print(f"epoch {epoch}/{config['epochs']} train {n + 1}/{len(order)} "
                      f"mean_loss={epoch_loss / (n + 1):.5f} elapsed={time.monotonic() - start:.1f}s", flush=True)
        val_frames = predict(model, validation, device, torch, amp_dtype, f"epoch {epoch} validation")
        pooled_ap = ap50(val_frames)
        assert pooled_ap is not None
        history.append({"epoch": epoch, "train_mean_loss": epoch_loss / len(order),
                        "pooled_validation_AP50": pooled_ap,
                        "elapsed_seconds": time.monotonic() - start})
        if pooled_ap > best_ap:
            best_ap, best_epoch = pooled_ap, epoch
            save_torch(torch, best_path, {"model": model.state_dict(), "epoch": epoch,
                                         "validation_AP50": pooled_ap,
                                         "m6_manifest_sha256": sha(ROOT / "qa/milestone_6_manifest.json")})
            write_json(ART / "best_validation_predictions.json", val_frames)
        save_torch(torch, latest, {"model": model.state_dict(), "optimizer": optimizer.state_dict(),
                                   "scaler": scaler.state_dict(), "epoch": epoch,
                                   "history": history, "best_ap": best_ap, "best_epoch": best_epoch,
                                   "m6_manifest_sha256": sha(ROOT / "qa/milestone_6_manifest.json"),
                                   "torch_rng": torch.get_rng_state(), "numpy_rng": np.random.get_state(),
                                   "python_rng": random.getstate(),
                                   "cuda_rng": torch.cuda.get_rng_state_all() if amp else None})
        write_json(ROOT / "results/m7_training_history.json",
                   {"training_epochs_completed": epoch, "best_epoch": best_epoch,
                    "best_pooled_validation_AP50": best_ap, "epochs": history})
        print(f"epoch {epoch} complete: validation AP50={pooled_ap:.5f}, best={best_ap:.5f} at {best_epoch}", flush=True)
    best = torch.load(best_path, map_location=device, weights_only=False)
    assert best["epoch"] == best_epoch and best["validation_AP50"] == best_ap
    model.load_state_dict(best["model"])
    val_frames = json.loads((ART / "best_validation_predictions.json").read_text())
    assert len(val_frames) == 60 and ap50(val_frames) == best_ap
    threshold = select_threshold(val_frames)
    validation_report = by_gsd_and_species(val_frames, threshold)
    write_json(ROOT / "results/m7_validation_selection.json",
               {"best_epoch": best_epoch, "pooled_validation_AP50": best_ap,
                "selected_confidence_threshold": threshold,
                "threshold_rule": config["threshold_selection"],
                "metrics": validation_report})
    test_frames = predict(model, test, device, torch, amp_dtype, "held-out test")
    assert len(test_frames) == 60
    write_json(ROOT / "results/m7_test_predictions.json", test_frames)
    best_sha = sha(best_path)
    write_json(ROOT / "results/m7_test_metrics.json",
               {"test_used_for_selection": False,
                "best_epoch_selected_on_validation": best_epoch,
                "confidence_threshold_selected_on_validation": threshold,
                "best_checkpoint_sha256": best_sha,
                "best_checkpoint_ignored_artifact": str(best_path.relative_to(REPO)),
                "m6_manifest_sha256": sha(ROOT / "qa/milestone_6_manifest.json"),
                "hardware": hardware, "torch_version": torch.__version__,
                "torchvision_version": torchvision.__version__,
                "iou_threshold": 0.5, "AP50_definition": "101_point_interpolated_precision_recall",
                "metrics": by_gsd_and_species(test_frames, threshold)})
    print("M7 held-out test complete:", json.dumps(by_gsd_and_species(test_frames, threshold)["overall"]), flush=True)


if __name__ == "__main__":
    main()
