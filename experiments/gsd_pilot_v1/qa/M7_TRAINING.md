# Milestone 7: one trained detector and held-out evaluation

The single M6 TorchVision Faster R-CNN MobileNetV3-Large FPN baseline was trained
for its frozen 20 epochs on 180 images from 30 scene groups. The model kept the
M6 full-frame 1024 × 1024 input, COCO_V1 initialization, two-class head,
seed `20260929`, batch size 1, SGD at learning rate 0.001 with momentum 0.9 and
weight decay 0.0005, no scheduler, no augmentation, box NMS 0.5, RPN NMS 0.7,
and at most 100 reported boxes per image. GPU training used bfloat16 autocast
on an NVIDIA RTX A2000 with driver 595.91.07, Torch 2.9.1+cu126, and
TorchVision 0.24.1+cu126. Training and epoch-wise validation took about 291
seconds, excluding startup and final test inference. Every epoch's mean training
loss and pooled validation AP50 are in `results/m7_training_history.json`.

The first attempted step on a target-absent uniform-water frame produced a
nonfinite classification loss because the pretrained RPN returned zero
proposals at its default 0.05 proposal-score floor. The same failure occurred
in full precision, ruling out a float16-specific cause. Before any checkpoint
or test result existed, the M7 run set the RPN proposal-score floor to 0.0 so
background proposals were available for negative frames. The failing frame
then produced finite losses. This adjustment did not change the M6 frozen box
NMS, RPN NMS, model-output score floor of 0.001, image preprocessing, split,
optimizer, or checkpoint-selection rule. Bfloat16 autocast was used for the
completed run; the initial failed float16 step produced no checkpoint.

The best checkpoint was epoch **10**, chosen by pooled validation AP50
**0.8269** across all five GSDs and both targets. Pooled validation F1 selected
confidence threshold **0.9477691650**; an exact F1 tie would have selected the
higher threshold. The same threshold was applied to every species and GSD in
the held-out test, with no test-set tuning. The selected checkpoint SHA-256 was
`bc2ccc63ddf4ddab2c6523ca60fee1cd2ea5a88ae3f833a3097cb5ba01510f5d`.
The checkpoint and validation prediction records remain in ignored
`artifacts/gsd_pilot_v1_m7/`; their hashes and derived metrics are recorded
in the tracked results. Reproducing bitwise checkpoint bytes across different
hardware or driver builds is not claimed.

At IoU at least 0.5, a prediction matched at most one ground-truth box.
AP50 used 101-point interpolated precision–recall over predictions from the
fixed 0.001 score floor, while TP/FP/FN, precision and recall used the selected
0.9478 threshold. The one-class AP50 was also mAP@0.5 for this detector.

| Held-out subset | Images (+/−) | TP | FP | FN | Precision | Recall | AP50 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Both targets, all GSDs | 60 (50/10) | 32 | 2 | 18 | 0.941 | 0.640 | 0.772 |
| European storm petrel | 30 (25/5) | 10 | 0 | 15 | 1.000 | 0.400 | 0.527 |
| Harbour porpoise | 30 (25/5) | 22 | 2 | 3 | 0.917 | 0.880 | 0.976 |

| Target | GSD (cm/px) | Images (+/−) | TP | FP | FN | Precision | Recall | AP50 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Petrel | 0.5 | 6 (5/1) | 5 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| Petrel | 1 | 6 (5/1) | 5 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| Petrel | 2 | 6 (5/1) | 0 | 0 | 5 | 0.000 | 0.000 | 0.334 |
| Petrel | 3 | 6 (5/1) | 0 | 0 | 5 | 0.000 | 0.000 | 0.302 |
| Petrel | 4 | 6 (5/1) | 0 | 0 | 5 | 0.000 | 0.000 | 0.000 |
| Porpoise | 0.5 | 6 (5/1) | 5 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| Porpoise | 1 | 6 (5/1) | 5 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| Porpoise | 2 | 6 (5/1) | 5 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| Porpoise | 3 | 6 (5/1) | 4 | 1 | 1 | 0.800 | 0.800 | 0.868 |
| Porpoise | 4 | 6 (5/1) | 3 | 1 | 2 | 0.750 | 0.600 | 0.864 |

There were zero false positives on the 10 target-absent test frames (0 per
negative frame); the two false positives occurred on porpoise-positive frames.
At the selected threshold the petrel had no true positives at 2–4 cm/px.
Its nonzero AP50 at 2 and 3 cm/px came from lower-score ranked predictions,
which did not meet that one global threshold. Each species/GSD cell contained
only five positive scenes and one negative scene, so these numbers are unstable
as performance estimates and cannot establish a reliable GSD threshold.

The split protected scene, instance, sequence, and condition identities, but
shared source meshes across splits. The images, camera, and environment were
synthetic and fixed; the bird state was a spread-wing proxy and the underwater
porpoise label was a direct amodal projection without refraction. The GSD sweep
also changed camera footprint rather than merely downsampling one image.
These results did not validate deployment to real surveys, unseen animals,
other oceans or lighting, or biological detection thresholds. The M8 report
will add uncertainty and pixels-on-target analysis.

The authoritative machine-readable records are
`results/m7_training_history.json`, `results/m7_validation_selection.json`,
`results/m7_test_predictions.json`, `results/m7_test_metrics.json`, and
`qa/m7_result_validation.json`. To repeat a complete run, recreate the pinned
M6 environment and checkpoint, keep the M6 manifests unchanged, and execute
`PYTHONDONTWRITEBYTECODE=1 artifacts/gsd_pilot_v1_m6/venv/bin/python
experiments/gsd_pilot_v1/ml/train_evaluate.py` from the repository root in a
fresh result/artifact location. The script refused to overwrite a completed
held-out test report.
