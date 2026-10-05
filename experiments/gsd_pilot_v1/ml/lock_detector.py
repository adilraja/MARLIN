"""Materialize and smoke-check the sole M7 detector baseline before training."""

import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
ARTIFACTS = REPO / "artifacts/gsd_pilot_v1_m6"
os.environ["TORCH_HOME"] = str(ARTIFACTS / "torch_home")


def main():
    import torch
    import torchvision
    from torchvision.models.detection import (
        FasterRCNN_MobileNet_V3_Large_FPN_Weights,
        fasterrcnn_mobilenet_v3_large_fpn,
    )
    from torchvision.models.detection.faster_rcnn import FastRCNNPredictor

    weights = FasterRCNN_MobileNet_V3_Large_FPN_Weights.COCO_V1
    torch.manual_seed(20260929)
    model = fasterrcnn_mobilenet_v3_large_fpn(
        weights=weights,
        min_size=1024,
        max_size=1024,
        box_score_thresh=0.001,
        box_nms_thresh=0.5,
        box_detections_per_img=100,
    )
    original_features = model.roi_heads.box_predictor.cls_score.in_features
    model.roi_heads.box_predictor = FastRCNNPredictor(original_features, 2)
    checkpoint = ARTIFACTS / "torch_home/hub/checkpoints" / weights.url.rsplit("/", 1)[-1]
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    checkpoint_hash = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    assert model.transform.min_size == (1024,)
    assert model.transform.max_size == 1024
    assert model.roi_heads.nms_thresh == 0.5
    assert model.roi_heads.score_thresh == 0.001
    assert model.roi_heads.detections_per_img == 100
    from dataset import DetectionDataset
    sample, target = DetectionDataset("validation")[0]
    assert tuple(sample.shape) == (3, 1024, 1024)
    model.train()
    with torch.no_grad():
        transformed, transformed_targets = model.transform([sample], [target])
    assert transformed.image_sizes == [(1024, 1024)]
    assert tuple(transformed.tensors.shape[-2:]) == (1024, 1024)
    assert torch.allclose(transformed_targets[0]["boxes"], target["boxes"])
    lock = {
        "architecture": "torchvision.models.detection.fasterrcnn_mobilenet_v3_large_fpn",
        "pretrained_weights": "FasterRCNN_MobileNet_V3_Large_FPN_Weights.COCO_V1",
        "weights_url": weights.url,
        "weights_sha256": checkpoint_hash,
        "weights_bytes": checkpoint.stat().st_size,
        "local_weights_path": str(checkpoint.relative_to(REPO)),
        "torch_version": torch.__version__,
        "torchvision_version": torchvision.__version__,
        "cuda_build": torch.version.cuda,
        "number_of_classes_including_background": 2,
        "head_initialization_seed": 20260929,
        "model_min_size": 1024,
        "model_max_size": 1024,
        "model_transform_output_size": list(transformed.image_sizes[0]),
        "model_internal_rescale": False,
        "box_score_threshold_before_validation_selection": 0.001,
        "box_nms_threshold": 0.5,
        "box_detections_per_image": 100,
        "rpn_nms_threshold": model.rpn.nms_thresh,
        "normalization_mean_rgb": list(model.transform.image_mean),
        "normalization_std_rgb": list(model.transform.image_std),
        "training": {
            "epochs": 20,
            "batch_size": 1,
            "gradient_accumulation_steps": 1,
            "optimizer": "SGD",
            "learning_rate": 0.001,
            "momentum": 0.9,
            "weight_decay": 0.0005,
            "scheduler": "none",
            "augmentations": [],
            "shuffle_seed": 20260929,
            "checkpoint_selection": "best_pooled_validation_AP50",
            "threshold_selection": "max_pooled_validation_F1_tie_choose_higher_confidence",
            "test_set_tuning": False,
        },
    }
    (ROOT / "ml/detector_lock.json").write_text(json.dumps(lock, indent=2) + "\n")
    print(json.dumps(lock, indent=2))


if __name__ == "__main__":
    main()
