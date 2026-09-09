# Controlled survey readiness review — 2026-09-09

Scope: repository/configuration audit against Ger's revised instructions. No live scene changes, asset edits, calibration claims or research captures were made during this review. The petrel flight work is deferred. Availability below means a referenced USD exists on disk, not that its identity, dimensions or pose are scientifically verified.

## Outcome

The project is ready to build a **geometry-only engineering capture test**, but not a calibrated wildlife GSD observation. Keep those two deliverables distinct. Missing species and final ML thresholds need not block a one-target engineering test; unknown physical scale and camera geometry do block claiming a calibrated animal observation.

## Assets

| Paper species | Available USD | Current evidence / outstanding work |
| --- | --- | --- |
| Common tern | Yes | Working copy and native bounds exist; folded-wing specimen pose; no verified water/flight state or metric dimensions. |
| Guillemot | Yes | Cleaned v4 with retained foot and material correction; native bounds exist; standing pose and hidden contact anatomy remain unverified. |
| Northern gannet | Yes | Cleaned working copy and native bounds exist; standing specimen is not a validated floating or flying pose. |
| European storm petrel | Yes | Cleaned and rigged copies; skeletal motion tested, but metric scale and scientific states remain unverified. Deferred by user. |
| Harbour porpoise | Yes | Calibration pending; manifest specifically flags armature/helper geometry for inspection before body measurement. |
| Common dolphin | Yes | Calibration pending; identity, orientation, anatomical measurements and surfacing state need verification. |
| Manx shearwater, kittiwake, razorbill | No | Missing paper assets; can remain explicitly excluded from the initial single-target test. |
| Risso's dolphin, minke whale | No | Missing paper assets; can remain explicitly excluded from the initial single-target test. |

There are six available models among eleven paper categories, and zero marked calibrated. The broader eleven-model marine-mammal library is separate from this paper inventory and remains retained. Do not confuse category count, available asset count and live instance count.

All six available paper manifests have `species_identity_verified: false`, calibration `status: pending`, null physical dimensions/scale/orientation, and empty `verified_states`. Four bird working copies supply measured native mesh extents. Those extents are not anatomical length or wingspan, and their units are explicitly uncalibrated. Source inspection flags describe the original scans; they must not erase the newer working-copy evidence, nor should cleanup automatically mark a pose scientifically verified.

For one selected animal, record a matching anatomical landmark measurement (not maximum XYZ extent), source geometry version, intended metric dimension and evidence, unit conversion, correction transform and reviewed survey pose. Preserve the original asset. A literature range alone does not establish the scanned individual's true dimensions; if using a synthetic representative size, label that assumption explicitly.

## Camera and units

`survey_v1.json` leaves `meters_per_scene_unit` null. Current display scales must not be interpreted as measured metres, and a USD unit metadata value alone would not establish biological size. Choose and document a survey unit convention without rescaling the existing demonstration scene; convert camera positions and USD optical attributes consistently.

| Camera | Recorded reference configuration | Missing calibration inputs |
| --- | --- | --- |
| HiDef / Prosilica GT6600C | 6576 × 2192, 150 mm, 549 m, pitch 30°, roll 7.77° / 23.17° | Pixel pitch; active sensor/ROI/crop/binning interpretation; axis definitions, angle signs and rotation order; lens model/distortion assumptions. |
| Sony ILX-LR1 | 85 mm, 150 m, nominal 0.663 cm/px, approximately 63 m swath | Active image dimensions/mode, pixel pitch, pitch/roll and pose convention; lens model/distortion assumptions. |

The existing `CameraConfig.readiness_gaps()` reports null schema fields; filling them is necessary but is **not** optical calibration. The reference numbers come from Ger, not an independent hardware verification. Do not derive an assumed pixel pitch from a nominal GSD and then use that same nominal GSD as independent validation.

The mathematical helpers currently implement ideal **nadir** GSD and altitude inversion, including target-plane height. They do not implement the required oblique HiDef projection. Preserve that configuration: an engineering nadir test must have a separate identity, never be presented as the HiDef replica. HiDef acceptance needs across-frame directional local GSD from ray/plane geometry under explicit conventions.

## What is already implemented

- Five GSD levels: 0.5, 1, 2, 3, 4 cm/px; eleven paper categories and six avian groups.
- Versioned draft specification, camera schema, deterministic condition seeds and split-leakage checks.
- Fixed environment endpoint `/scene/survey/environment` and `survey_environment_v1.json`: flat water, zero wave speed/amplitude/choppiness, diffuse lighting, no directional sun and disabled underwater cue. Appearance QA remains pending.
- Native measurements and support-cleaned bird copies, without deleting primary assets.
- Existing reference spawning, chase-camera controls and diagnostic viewport capture.

The fixed-environment endpoint does **not** freeze animal controllers or establish a survey camera. A stopped timeline does not pause the independent petrel controller. A viewport screenshot is not a fixed-resolution annotated render product. Extra scene lights, the grid overlay, camera exposure and unrelated review models must be excluded/controlled in survey captures.

## Remaining implementation gates

1. **Geometry-only test:** use a known-size planar calibration target and explicit test units, intrinsics, resolution and camera pose. Keep it isolated from the existing demonstration. Measure image-space target extent against projection; save declared units and settings. No animal-size or HiDef-validation claim.
2. **One calibrated wildlife frame:** select a non-petrel available target, verify the asset's physical assumptions and pose, complete one camera configuration, apply fixed conditions and explicitly freeze all relevant motion. Capture a renderer-produced instance mask/bounding box plus metadata, not inferred labels from RGB.
3. **Reproducibility check:** reconstruct the frame from recorded parameters/seed and compare camera, placement, masks and GSD within declared tolerances. Do not assume bitwise RGB determinism from a stochastic renderer.
4. **Five-level paired sweep:** only after the first-frame geometry and metadata pass, hold nuisance conditions paired across GSD. Decide sweep method and target-height treatment explicitly.
5. **Research dataset/evaluation:** approve sample counts, strata, split ratios, classification thresholds, detection IoU/confidence selection and asset-diversity limitations. These decisions need not delay the geometry-only test.

The required COCO and per-frame metadata formats currently exist as contracts, not an implemented survey exporter. A capture needs at least actual output dimensions, camera intrinsics/extrinsics, units, target transform/identity/state, local directional GSD, mask area, bounding box convention, asset version/hash, condition identifiers, seed and specification version.

## Next bounded implementation

Build the isolated planar-target geometry test and fail validation on missing units or intrinsics. In parallel with later calibration work, obtain the PI's HiDef pose/ROI conventions and Sony trial mode. Then choose one available non-petrel animal for the first wildlife frame. Do not mark the full protocol ready because the engineering capture succeeds.

Review checks: all seven existing survey-spec tests pass, including inventory/provenance, GSD calculations, paired seeds, camera validation and protected split identifiers. These are schema/math tests, not rendered-camera calibration tests.
