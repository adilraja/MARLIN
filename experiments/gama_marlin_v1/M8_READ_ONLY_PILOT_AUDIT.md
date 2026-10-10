# M8 read-only Pilot v1 audit

The three Pilot audit items were documented and checked on 9 October 2026:
the full detector input path, AP aggregation, and the meaning of the amodal
boxes. The checks used preserved Pilot code and data plus the currently
installed, version-matched PyTorch/TorchVision sources. No detector was trained,
no checkpoint was loaded, no detector inference or live MARLIN call was made,
and no Pilot output was written. This audit completes the read-only audit task;
it does not declare the GAMA sprint or Milestone 8 complete.

The executed evidence is [m8_pilot_audit_02.json](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m8_pilot_audit_02.json),
with the exact [command and execution record](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m8_pilot_audit_02_execution.json)
and actual [stdout/stderr log](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m8_pilot_audit_02.log).
The run returned 0 in 10.39 seconds. The evidence records every input/source
hash, installed source wheel-RECORD checks, observations and limitations.

## Audit gaps identified before this check

The [retained Pilot final report](/home/madil/kit-app-template/experiments/gsd_pilot_v1/results/M8_FINAL_REPORT.md:66)
already described 1024 × 768 to 1024 × 1024 padding, a single detector and
direct amodal boxes. The [detector lock](/home/madil/kit-app-template/experiments/gsd_pilot_v1/ml/detector_lock.json:13)
recorded `model_internal_rescale: false`; the
[training report](/home/madil/kit-app-template/experiments/gsd_pilot_v1/qa/M7_TRAINING.md:37)
recorded 101-point AP50. Those summaries left the following details to verify.

| Audit item | Detail resolved here | Remaining limit |
|---|---|---|
| Complete input path | Alpha/RGB conversion, padding, tensor scale, normalization, installed interpolation call, stride padding and prediction-coordinate return path | The historical GPU run was not repeated; current installed source bytes were not historically pinned by Pilot |
| AP aggregation | One foreground class, one IoU, score floor, deterministic matching/order, 101 recall levels, image pooling and subset definitions | This custom AP50 is not full COCO evaluation or an estimate of real-survey performance |
| Amodal interpretation | Frozen evaluated mesh vertices, direct projection, box extrema, COCO area and padded coordinates | Visible/refraction-corrected outlines, silhouette area and visible target area remain unknown |

## Complete detector input and output-coordinate path

The retained model was **TorchVision Faster R-CNN MobileNetV3-Large FPN**,
initialized with `COCO_V1` weights and a replacement two-output-class head.
It used PyTorch `2.9.1+cu126` and TorchVision `0.24.1+cu126`. The current retained
environment matches both versions; its Pillow is `12.3.0` and NumPy is `2.5.2`.
The training constructor supplies `min_size=1024`, `max_size=1024`,
`box_score_thresh=0.001`, `box_nms_thresh=0.5`, `rpn_score_thresh=0.0`, and
`box_detections_per_img=100`.
See [setup_model](/home/madil/kit-app-template/experiments/gsd_pilot_v1/ml/train_evaluate.py:31)
and the [version assertions](/home/madil/kit-app-template/experiments/gsd_pilot_v1/ml/train_evaluate.py:111).

| Stage | Actual operation and dimensions | Local source |
|---|---|---|
| Read capture | Require 1024 × 768 RGB or RGBA. Require opaque alpha when RGBA, then explicitly convert to RGB | [dataset.prepare](/home/madil/kit-app-template/experiments/gsd_pilot_v1/ml/dataset.py:18) |
| Pad full frame | Add `(left, top, right, bottom) = (0,128,0,128)` pixels, constant RGB `(114,114,114)`, producing 1024 × 1024. Paste source pixels without cropping or resizing | [dataset constants](/home/madil/kit-app-template/experiments/gsd_pilot_v1/ml/dataset.py:7), installed [Pillow expand](/home/madil/kit-app-template/artifacts/gsd_pilot_v1_m6/venv/lib/python3.12/site-packages/PIL/ImageOps.py:487) |
| Translate labels | COCO `[x,y,w,h]` becomes `[x,y+128,w,h]`, then `[x,y+128,x+w,(y+128)+h]`. Width and height are unchanged | [split/input freeze](/home/madil/kit-app-template/experiments/gsd_pilot_v1/ml/m6_freeze.py:141), [adapter box conversion](/home/madil/kit-app-template/experiments/gsd_pilot_v1/ml/dataset.py:31) |
| Tensor conversion | RGB uint8 HWC → copied tensor CHW → float32 divided by 255, shape `3×1024×1024`, values in `[0,1]`; GT boxes float32, foreground labels int64 `1` | [DetectionDataset.__getitem__](/home/madil/kit-app-template/experiments/gsd_pilot_v1/ml/dataset.py:46) |
| Model normalization | Per-channel `(pixel/255 − mean)/std`, RGB mean `[.485,.456,.406]`, std `[.229,.224,.225]` | [FasterRCNN defaults](/home/madil/kit-app-template/artifacts/gsd_pilot_v1_m6/venv/lib/python3.12/site-packages/torchvision/models/detection/faster_rcnn.py:277), [normalize](/home/madil/kit-app-template/artifacts/gsd_pilot_v1_m6/venv/lib/python3.12/site-packages/torchvision/models/detection/transform.py:160) |
| Internal resize call | The installed transform calls bilinear interpolation, `scale_factor=1.0`, `size=None`, `align_corners=False`, `recompute_scale_factor=True`; `antialias` is omitted and its PyTorch default is false. Dimensions remain 1024 × 1024 | [resize calculation/call](/home/madil/kit-app-template/artifacts/gsd_pilot_v1_m6/venv/lib/python3.12/site-packages/torchvision/models/detection/transform.py:25), [resize train/eval path](/home/madil/kit-app-template/artifacts/gsd_pilot_v1_m6/venv/lib/python3.12/site-packages/torchvision/models/detection/transform.py:179), [interpolate signature](/home/madil/kit-app-template/artifacts/gsd_pilot_v1_m6/venv/lib/python3.12/site-packages/torch/nn/functional.py:4528) |
| Internal batch padding | Round H/W up to the default `size_divisible=32`, initialize batch padding with normalized-space zero, then copy each image. Since 1024 is divisible by 32, no additional pixels are added; batch size one gives `1×3×1024×1024` | [transform defaults](/home/madil/kit-app-template/artifacts/gsd_pilot_v1_m6/venv/lib/python3.12/site-packages/torchvision/models/detection/transform.py:98), [batch_images](/home/madil/kit-app-template/artifacts/gsd_pilot_v1_m6/venv/lib/python3.12/site-packages/torchvision/models/detection/transform.py:237) |
| Prediction coordinates | The model stores its incoming 1024 × 1024 size before transform and maps detections back to that size after its backbone, RPN and ROI heads. Box scaling ratios are one here | [GeneralizedRCNN forward](/home/madil/kit-app-template/artifacts/gsd_pilot_v1_m6/venv/lib/python3.12/site-packages/torchvision/models/detection/generalized_rcnn.py:87), [postprocess](/home/madil/kit-app-template/artifacts/gsd_pilot_v1_m6/venv/lib/python3.12/site-packages/torchvision/models/detection/transform.py:257), [resize_boxes](/home/madil/kit-app-template/artifacts/gsd_pilot_v1_m6/venv/lib/python3.12/site-packages/torchvision/models/detection/transform.py:306) |

The locked “no internal rescale” statement therefore describes **unit geometric
scale**, rather than bypassing the installed resize function. The new CPU
observations confirmed 12 actual transform calls: train and evaluation mode,
target-present and target-absent examples, in each of the three splits. Every
normalized output tensor was exactly equal to direct normalization of the input
tensor at unit scale; boxes remained unchanged. This is current CPU transform
evidence, not a claim of historical GPU bitwise equivalence.

There is no YOLO auto-letterbox, dynamic aspect-ratio resize or extra
weight-enum preprocessing call in this Pilot path. Its full-frame square padding
is fixed. The learned backbone and ROI feature sampling occur after this input
transform; those feature operations do not define an aerial-survey GSD. The
original padding also undergoes normalization, yielding approximately
`[-0.16568205, -0.03991595, 0.18248373]`, rather than normalized-space zero.

Predicted boxes are clipped to the **padded** image in the ROI heads; there is no
later subtraction of 128 or clipping to the original 768-pixel height before
the saved evaluation. GT and predictions both use the padded coordinate frame.
The saved GT values reflect float32 conversion of the translated double-precision
annotations; the audit reproduced that conversion for all 60 test records.
See [ROI output filtering](/home/madil/kit-app-template/artifacts/gsd_pilot_v1_m6/venv/lib/python3.12/site-packages/torchvision/models/detection/roi_heads.py:671)
and [prediction serialization](/home/madil/kit-app-template/experiments/gsd_pilot_v1/ml/train_evaluate.py:54).

All 300 images were decoded, hashed and checked again. Their unpadded RGB pixels
exactly matched the middle 1024 × 768 region of the padded result; all padding
pixels were 114. There were 150 positive/30 negative training images,
50 positive/10 negative validation images and 50 positive/10 negative test
images. The 250 boxes preserved their geometric dimensions through padding.
The GSD sweep changed camera height and world footprint while retaining capture
resolution; these image conditions were not generated by detector preprocessing
or downsampling one fixed-footprint frame.
See the retained [camera limitation](/home/madil/kit-app-template/experiments/gsd_pilot_v1/results/M8_FINAL_REPORT.md:86).

## AP50, matching, selection and aggregation

There was **one foreground detection category, `wildlife` (class 1)**, with
background class 0. Petrel and porpoise were recorded as source metadata, not
separate detector classes. The prediction serializer asserts class 1 for every
returned prediction. A per-species metric consequently evaluates wildlife
detections on that species' subset; it does not measure species classification.
See [dataset labels](/home/madil/kit-app-template/experiments/gsd_pilot_v1/ml/dataset.py:36),
[head replacement](/home/madil/kit-app-template/experiments/gsd_pilot_v1/ml/train_evaluate.py:49)
and [prediction class assertion](/home/madil/kit-app-template/experiments/gsd_pilot_v1/ml/train_evaluate.py:69).

The exact custom metric convention was:

1. Each image has zero or one GT box. Continuous edge-coordinate rectangle IoU
   uses width/height differences without an inclusive-pixel `+1`. A TP requires
   IoU **≥ 0.5** against that image's sole GT box.
2. For the selected set of images, collect predictions with score **≥ the
   supplied threshold**. Sort globally by decreasing score; exact ties are
   ordered by image ID and then lexicographic box coordinates.
3. The first eligible prediction for an unmatched positive image becomes TP;
   further predictions on the same matched image are FP. An earlier wrong box
   does not consume the match, so a later eligible box may become TP. Every
   prediction on a GT-empty image is FP. Each unmatched GT contributes one FN.
4. AP50 always uses the fixed metric score floor **0.001**, independent of the
   validation-selected operational confidence threshold. Cumulative TP/FP yield
   recall and precision points. At each of **101 recall levels `0, .01, …, 1`**,
   take the maximum observed precision at any equal-or-higher recall; use zero
   when no point reaches that level. AP50 is their arithmetic mean. There is no
   trapezoidal area calculation or interpolation between individual rank points.
5. With no GT, AP50 and recall return null. With no thresholded predictions,
   precision returns zero. F1 is `2TP/(2TP+FP+FN)` when that denominator is nonzero.
   False positives per negative frame count FP detections divided by the number
   of GT-empty frames, not the fraction of negative frames containing any FP.

These statements follow the preserved [IoU and ranking implementation](/home/madil/kit-app-template/experiments/gsd_pilot_v1/ml/metrics.py:4),
[AP implementation](/home/madil/kit-app-template/experiments/gsd_pilot_v1/ml/metrics.py:34)
and [summary implementation](/home/madil/kit-app-template/experiments/gsd_pilot_v1/ml/metrics.py:48).

The detector applies a strictly greater-than-0.001 foreground score filter,
class-aware NMS at IoU 0.5, a 0.01-pixel minimum box side and at most 100 retained
detections per image before serialization. The custom metric's inclusive
0.001 floor is therefore applied to an already-filtered prediction list.
The 60 saved test records contain 611 predictions; their lowest score is
`0.0010005044750869274`, so the floor-boundary distinction does not alter these
retained results. The RPN proposal floor is separately 0.0 in the completed
training source; RPN NMS is 0.7. Neither is the evaluation IoU threshold.
See [training constructor](/home/madil/kit-app-template/experiments/gsd_pilot_v1/ml/train_evaluate.py:43)
and [installed ROI filtering](/home/madil/kit-app-template/artifacts/gsd_pilot_v1_m6/venv/lib/python3.12/site-packages/torchvision/models/detection/roi_heads.py:709).

The **overall AP50 pools all retained predictions across all 60 test images**
against all 50 positive GT boxes. It is not a mean of per-image AP, per-scene AP,
species AP or five GSD APs. Each grouped result repeats the same calculation
after filtering its input images: 2 species subsets, 5 GSD subsets and
10 species × GSD subsets, in addition to overall. There are 18 summaries total.
Each species/GSD cell has five positive images and one negative image. A GSD
subset has ten positive and two negative images. The single-class AP50 may be
called one-class mAP@0.5, but it is **not COCO AP@[.50:.95]**, a two-species mAP,
or an area/crowd-stratified official COCO evaluation. No IoUs other than 0.5 are
aggregated in this metric.
See [grouping function](/home/madil/kit-app-template/experiments/gsd_pilot_v1/ml/train_evaluate.py:84).

Whole scene, instance, sequence and condition groups were kept within one split,
including their five GSD versions and available negative counterparts. Those
five image detections still contribute separately to pooled AP. Grouped
splitting does not make them independent observations. The later plot analysis
used Wilson intervals for recall cells and a species-stratified, whole-scene
bootstrap for the 4-versus-0.5 cm/px recall difference; it did not provide an AP
interval. See [split construction](/home/madil/kit-app-template/experiments/gsd_pilot_v1/ml/m6_freeze.py:89)
and [scene bootstrap](/home/madil/kit-app-template/experiments/gsd_pilot_v1/results/m8_analyse.py:118).

The checkpoint was selected by highest pooled validation AP50 over 20 epochs;
the strict improvement comparison retains the earliest epoch on an exact tie.
Confidence was selected on validation by maximum pooled F1 across observed
prediction scores plus 0.001 and 1.0; an exact F1 tie selects the higher
confidence. Retained selection was epoch 10 and threshold
`0.9477691650390625`, applied unchanged to every test subgroup.
See [checkpoint selection](/home/madil/kit-app-template/experiments/gsd_pilot_v1/ml/train_evaluate.py:197),
[threshold selection](/home/madil/kit-app-template/experiments/gsd_pilot_v1/ml/metrics.py:68)
and [held-out evaluation](/home/madil/kit-app-template/experiments/gsd_pilot_v1/ml/train_evaluate.py:223).

Recomputing all 18 saved summaries from the saved predictions and locked
threshold produced exact equality with the preserved result. Overall was
**32 TP, 2 FP, 18 FN; precision 0.9411764705882353; recall 0.64;
F1 0.7619047619047619; AP50 0.7716031777998319**. None of the ten negative frames
had a thresholded FP. This reuses retained predictions and does not demonstrate
a new detector execution or new trained-checkpoint accuracy.

## What the amodal labels mean

Pilot scene construction flattened a private USD stage, baked skinning, and
replaced authored animation samples with values at the chosen static pose time.
Projection collected **all `UsdGeom.Mesh` vertices under
`/World/Cetaceans/PilotTarget`**, applied complete parent/world transforms and
the recorded 0.01 metres per scene unit, and projected them through the fixed
nadir engineering camera. The box is the minimum/maximum image X/Y over those
vertices. It is neither a projection of just eight world-AABB corners nor a box
fitted to an image segmentation mask.
See [private skinning/freeze](/home/madil/kit-app-template/experiments/gsd_pilot_v1/scenes/build_scenes.py:89),
[vertex projection](/home/madil/kit-app-template/experiments/gsd_pilot_v1/qa/m4_geometry.py:28)
and [M5 geometry collection](/home/madil/kit-app-template/experiments/gsd_pilot_v1/qa/m5_geometry.py:19).

The direct projection uses optical depth and the calibrated ideal pinhole
relation (`fx≈10000` pixels; centre `(512,384)` in the 1024 × 768 frame).
Behind-camera vertices and boxes extending outside the original image were
rejected in the Pilot. The code does not perform a refractive ray trace through
the water or an occlusion/visibility test before choosing box extrema.
The audit checked all 250 retained boxes for exact agreement among projected
geometry records, COCO annotations and the model-input assignments.

The COCO label category is wildlife ID 1, `iscrowd=0`, and its `area` is
**rectangle width × height** with `area_semantics: bbox_area_for_detection_only`.
Both projected silhouette area and visible target area are explicitly null in
all 250 geometry records. Width, height and minimum box side are geometric box
extents; they are not visible-animal pixel counts or silhouette area.
See [geometry limitations](/home/madil/kit-app-template/experiments/gsd_pilot_v1/qa/m4_geometry.py:79)
and [COCO label construction](/home/madil/kit-app-template/experiments/gsd_pilot_v1/qa/m5_validate_dataset.py:124).

Pilot's `visibility_validated` flag came from separate local contrast checks
inside the box against a 12-pixel surround. Negative-pair QA additionally
required changed pixels within the box. Those checks established usable target
appearance for the accepted Pilot frames; they did not extract a visible animal
mask, attribute every contrast pixel to the animal, or determine refracted
underwater outlines. AP50 therefore measures agreement with **direct amodal
boxes**, including porpoise frames whose underwater rendered appearance can
differ from the geometry's projected extent.
See [local visibility method](/home/madil/kit-app-template/experiments/gsd_pilot_v1/qa/m5_validate_dataset.py:26)
and [pair checks/limitations](/home/madil/kit-app-template/experiments/gsd_pilot_v1/qa/m5_validate_dataset.py:138).

## Preservation, evidence pins and unresolved limits

All 32 audited Pilot source/data files matched the preserved baseline pins.
All 300 image hashes and all audited source hashes remained unchanged after
the audit. Eight installed `.py` source files matched the corresponding
installed distribution `RECORD` entries. Their complete hashes, the distribution
RECORD hashes, every source/data pin and all image pins are retained in the
[audit evidence](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m8_pilot_audit_02.json).
Key source pins are reproduced here for review.

| Source | SHA-256 |
|---|---|
| [dataset.py](/home/madil/kit-app-template/experiments/gsd_pilot_v1/ml/dataset.py) | `d4b0301d1c261484fd54ca0fb89d60893583505faa018b53df97e30ed9d5788a` |
| [train_evaluate.py](/home/madil/kit-app-template/experiments/gsd_pilot_v1/ml/train_evaluate.py) | `deff60170b452cf6f422402c86ccc6b49a43b251de7528a0fea61cd75f8d5df8` |
| [metrics.py](/home/madil/kit-app-template/experiments/gsd_pilot_v1/ml/metrics.py) | `8ddb9e602001f699eda4bfb897ce8ec6dff11dede0b7f239a47efa8a9a7dc2c9` |
| [detector_lock.json](/home/madil/kit-app-template/experiments/gsd_pilot_v1/ml/detector_lock.json) | `d9a3945da830e44bc8549dfa8e2532082dfd9430f8f4f9ded803c16c032d0b5a` |
| [installed transform.py](/home/madil/kit-app-template/artifacts/gsd_pilot_v1_m6/venv/lib/python3.12/site-packages/torchvision/models/detection/transform.py) | `8f53149cd93c3bc291cf081535686282137ae29b2362938e7329f2361325061f` |
| [installed Faster R-CNN source](/home/madil/kit-app-template/artifacts/gsd_pilot_v1_m6/venv/lib/python3.12/site-packages/torchvision/models/detection/faster_rcnn.py) | `4ba7930ab1e4588083a462208c00232dcc206ac12e6fc59852fa48c668f2b26b` |
| [installed interpolate implementation](/home/madil/kit-app-template/artifacts/gsd_pilot_v1_m6/venv/lib/python3.12/site-packages/torch/nn/functional.py) | `5e96bb0880a4c6f4c0ae34c00a894e152412e68f6ffd073d2b442907eedeb5fa` |
| [m4_geometry.py](/home/madil/kit-app-template/experiments/gsd_pilot_v1/qa/m4_geometry.py) | `912aeb92bb4052dd90afd2db96be45ad032740ef7369319896485c8f2dcb1c31` |
| [saved predictions](/home/madil/kit-app-template/experiments/gsd_pilot_v1/results/m7_test_predictions.json) | `77719a09d838b9d2aa26c15a614e2a3dbc28d05aca0140248ed4b5a0ed953e9c` |
| [saved test metrics](/home/madil/kit-app-template/experiments/gsd_pilot_v1/results/m7_test_metrics.json) | `983a032c83be3c5ea65dbbef4106164e84221446fa723c6a6d63781fa8843479` |

The first audit execution stopped on an audit-check error: its expected box
bottom used `(y+h)+128` while the retained adapter uses `(y+128)+h`, giving
small floating-point association differences. The check was corrected to follow
the actual retained operation; Pilot code/data were unchanged. The original
[failure log](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m8_pilot_audit_01.log)
and [execution record](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m8_pilot_audit_01_execution.json)
remain preserved. The successful run used a new exclusive evidence prefix.

The remaining boundaries are explicit:

- Current installed source/RECORD agreement and exact version matches do not
  establish byte-identical historical wheels or GPU arithmetic. The completed
  predictions and results remain historical retained evidence; they were not
  regenerated. The audit exercised only the input transform on CPU.
- The original locked padding/min/max configuration fully resolves input
  geometric scale for these 300 images. It does not imply no feature pooling,
  survey-camera calibration, pixel-identical RTX replay or fixed world footprint.
- AP50 remains a descriptive synthetic-to-synthetic, single-wildlife-class
  result. It does not validate unseen meshes/individuals, real surveys, a
  deployable GSD threshold or biological behaviour.
- Visible/refraction-corrected boundaries and exact visible/silhouette areas
  remain unmeasured. This audit documents that limit without inventing values.
- No generated directories were inspected. No `_build`, `extscache`,
  `__pycache__`, `.cache` or `.pyc` file was opened as an audit input. No online
  documentation was needed because the relevant installed source was available.

To reproduce this read-only check, choose a new output filename and run the
[new audit checker](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m8_pilot_audit_check.py)
from the repository root:

```bash
CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 \
  artifacts/gsd_pilot_v1_m6/venv/bin/python -B \
  experiments/gama_marlin_v1/qa/m8_pilot_audit_check.py \
  --output experiments/gama_marlin_v1/qa/m8_pilot_audit_new.json
```

The checker rejects an existing output and does not call the original Pilot
scripts' write/training entry points.
