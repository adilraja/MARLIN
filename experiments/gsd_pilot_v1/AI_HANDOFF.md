# MARLIN GSD pilot — AI handoff

**Status:** All eight milestones of the first end-to-end GSD sprint were completed and committed (`94f2886`). The result was a **provisional synthetic-to-synthetic object-detection experiment**, not an operational wildlife-survey threshold.

## What was built

MARLIN remained an NVIDIA Omniverse Kit application with HTTP services; the runtime source stayed under `source/apps/` and `source/extensions/`. The sprint audited and froze a protocol, calibrated a European storm petrel and harbour porpoise, generated paired marine scenes at **0.5, 1, 2, 3 and 4 cm/px**, captured images and direct amodal bounding boxes, assigned scene-group splits, trained one detector, and packaged the results with plots, provenance and regression evidence.

The dataset contained **300 images**: 250 target-present images with one box each and 50 target-absent images with no box. Train/validation/test contained **180/60/60 images**. All five GSD views and negative counterparts of a scene stayed in the same split; scene, asset-instance, sequence and condition IDs did not cross splits. The same source mesh for each species *was* shared across splits.

The detector was TorchVision Faster R-CNN MobileNetV3-Large FPN with COCO_V1 initialization. It trained for 20 epochs on padded 1024 × 1024 inputs. Validation selected epoch **10** and confidence threshold **0.947769**. On the untouched 60-image test set it produced **32 TP, 2 FP, 18 FN**, precision **0.941**, recall **0.640**, and AP50 **0.772**. Petrel recall was 10/25; porpoise recall was 22/25. Each species/GSD test cell had only five positive scenes and one negative scene.

## Where to look

- Final interpretation and plots: `results/M8_FINAL_REPORT.md`
- Performance and pixel-size plots: `results/m8_performance_vs_gsd.png`, `results/m8_pixels_on_target.png`
- Image paths and split IDs: `splits/image_assignments.json`
- COCO labels: `annotations/milestone_5_coco.json`
- Per-image detector outputs: `results/m7_test_predictions.json`
- Test metrics by species and GSD: `results/m7_test_metrics.json`
- Training settings and checkpoint hash: `ml/detector_lock.json`, `results/m7_training_history.json`, `qa/m8_provenance.json`
- Trained checkpoint: repository-root `artifacts/gsd_pilot_v1_m7/best.pt` (**local and Git-ignored**)
- Final QA and preserved-output hashes: `qa/m8_result_validation.json`, `qa/milestone_8_manifest.json`

All paths above, except the checkpoint, are relative to this file's directory (`experiments/gsd_pilot_v1/`). The final Blender/USD-capable MARLIN suite passed **77 tests**, reconstruction contracts passed **8 tests**, and milestone output hashes remained intact. The live completion preview restored moving water and all **11 default animals swimming with body animation**.

## Interpretation limits

The camera was an engineering pinhole profile, the environment and biological states were constrained, and GSD changes also changed camera footprint. Porpoise labels were direct **amodal** mesh projections, not refracted visible outlines. Visible silhouette area and exact visible target pixels were not measured. The small synthetic test set and shared source meshes did not establish performance on unseen animals, real survey imagery, other conditions, or a deployable GSD threshold. Read `results/M8_FINAL_REPORT.md` before extrapolating the curves.
