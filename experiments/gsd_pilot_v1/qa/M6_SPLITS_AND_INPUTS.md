# Milestone 6: frozen splits and model inputs

The accepted M5 dataset was divided by scene group before expanding the five
GSD conditions. For each species, a SHA-256 rank using seed `20260929` assigned
the five predefined negative-parent groups as 3/1/1 and the other 20 groups as
12/4/4 to train/validation/test. The resulting splits contained 30/10/10 scene
groups and 180/60/60 images. Each image carries its scene, asset-instance,
sequence and condition IDs in `splits/image_assignments.json`. The existing
`survey_spec.validate_split_records` accepted all 300 records with no protected
ID crossing a split. Every positive GSD series and target-absent counterpart
stayed with its parent scene. The same source mesh is used across splits, so the
test set does **not** measure unseen individuals or mesh generalization.

The loader decoded and SHA-checked all 300 source PNGs. They were 1024 × 768
RGBA images with opaque alpha, converted explicitly to RGB. Full frames were
padded by 128 pixels above and below with constant RGB `(114,114,114)` to give
1024 × 1024 model input. There is no crop, resize, tile or augmentation. The
original-to-model affine is `[[1,0,0],[0,1,128],[0,0,1]]`. All 250 direct
amodal boxes translated and inverted within tolerance; widths and heights in
pixels stayed the same. The unknown visible target area and silhouette area
remained unknown. Empty target lists for 50 negative frames were verified. The
Torch adapter returned float32 CHW values in [0,1] and class 1 `wildlife`, with
class 0 reserved for background. The detector's internal transform was checked
to leave the 1024 × 1024 dimensions and boxes unchanged.

One baseline was locked: TorchVision Faster R-CNN MobileNetV3-Large FPN with
COCO_V1 pretrained weights, a new two-class predictor, Torch 2.9.1+cu126 and
TorchVision 0.24.1+cu126. The downloaded checkpoint's complete SHA-256 is in
`ml/detector_lock.json`; the checkpoint itself is an ignored artifact and is
not copied into Git. `ml/requirements-cu126.lock` records all installed
dependencies. The model uses batch size 1, SGD learning rate 0.001, momentum
0.9, weight decay 0.0005, 20 epochs, no learning-rate scheduler or augmentation,
0.5 box NMS, 0.7 RPN NMS, and 100 maximum detections per image. Raw scores down
to 0.001 are retained for validation-only F1 threshold selection. The best
checkpoint will be selected by pooled validation AP50; the test split is not
used for tuning. M7 will train and measure performance; no detector result was
observed in M6.

The model package and weights came from the [official PyTorch version matrix](https://pytorch.org/get-started/previous-versions/)
and [TorchVision model documentation](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.detection.fasterrcnn_mobilenet_v3_large_fpn.html).
The local Kit session occupied most of the 6 GiB GPU when checked (about 1.2 GiB
free). M6 only exercised the CPU preprocessing transform. M7 should measure
training memory at batch 1 before choosing whether to pause the Kit session for
GPU training or use a CPU fallback. This does not alter the frozen input or
optimizer settings.

To verify M6 from the repository root with the locked environment installed:

```bash
PYTHONDONTWRITEBYTECODE=1 artifacts/gsd_pilot_v1_m6/venv/bin/python experiments/gsd_pilot_v1/ml/verify_loader.py
PYTHONDONTWRITEBYTECODE=1 artifacts/gsd_pilot_v1_m6/venv/bin/python experiments/gsd_pilot_v1/ml/lock_detector.py
```

The one-time environment was created under ignored `artifacts/gsd_pilot_v1_m6`
and installed from the CUDA 12.6 PyTorch wheel index. The downloaded checkpoint
is in that same ignored directory. `ml/m6_freeze.py` reconstructs and verifies
the split manifests from frozen M5 inputs; it is intended as an audit of the
locked assignment, not a way to resample after seeing results.
