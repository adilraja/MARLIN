# GSD pilot protocol v1

## Question and scope

Measure how a single baseline detector behaves across 0.5, 1, 2, 3 and 4 cm/px
when biological scenes are paired. Use one bird asset and one cetacean asset,
one fixed environment and a small synthetic dataset. This is an engineering
pilot with provisional scientific interpretation. Results apply to the selected
assets, permitted poses, renderer and preprocessing pipeline.

## Imaging decision

Reuse the existing generic ideal-pinhole `CalibrationConfig` and USD camera
builder. Keep the HiDef and Sony profiles unchanged. Both profiles enforce
fixed physical parameters; their previews alone do not implement this sweep.
This decision reuses the existing engineering camera, rather than inventing a
new hardware model. Integrating it with frozen marine capture is M4 work.

Freeze output at 1024 x 768 pixels, focal length 50 mm, effective pixel pitch
5 micrometres, nadir, centred principal point and zero distortion. These are
engineering configuration choices from the existing calibration fixture, not
measurements of a survey camera. Change only camera Y within a biological pair.
Camera X/Z, intrinsics, resolution and orientation stay fixed.

For each scene, record a horizontal target-reference plane at the animal root
Y after calibrated placement. Compute camera-to-plane separation as
`H = (GSD_cm_px / 100) * focal_length_mm / pixel_pitch_mm`.
The five separations are 50, 100, 200, 300 and 400 metres. Add the recorded
plane elevation to obtain camera world Y. Record sea-plane GSD separately;
neither plane describes the entire three-dimensional animal or underwater
refraction. Record direct geometric local sampling at the target centroid and
the range across evaluated geometry where meaningful.

This is an altitude-conditioned GSD experiment. Field of view in metres and
viewing rays through off-centre geometry change with height. Do not describe it
as a pure raster-downsampling experiment or change focal length to compensate.
World positions are sampled once and checked against the narrowest footprint
before any rendering. Frame coordinates at other GSDs are outcomes, not new
placement commands. This intentionally does not hold normalized image position
constant while changing the camera height.

M4 must validate actual image dimensions, captured camera matrices and planar
metric targets through the same marine capture path at all five GSD levels.
Existing fixture tests are supporting evidence, not certification of that new
combination. Preserve the current projection tolerance of 0.001 px and existing
raster-probe checks of 2 px bounding-box error and 0.95 polygon IoU. These are
engineering fixture tolerances, not visibility or biological thresholds.

## Targets and environment

M2 selects one sufficiently supported avian and one cetacean. Current leading
candidates are the European storm petrel working asset and the harbour porpoise
static candidate. This is a shortlist, not a calibration approval. Do not copy
display scales into physical records. Document species-identity uncertainty,
licence, model hashes, measurement landmarks, origin, axis correction, stage
unit conversion and every physical value's source.

Use only reviewed static visual states. One valid state per target is enough
for the first pilot; do not add unsupported on-water or breathing poses merely
to fill categories. Pose controls are not proof of biological validity.
State-conditioned depth/altitude and orientation ranges are resolved in M2,
before scene generation. Unknown values remain null with a status and reason.

M3 derives `gsd_baseline_v1` from the existing flat, diffuse
`survey_fixed_v1` appearance preset. Freeze material, lighting, exposure,
renderer, sampling, denoising and colour-management settings explicitly.
This is a controlled appearance preset, not calibrated ocean optics. Preserve
Y-up and the runtime's centimetre convention; fail closed on an unexpected
stage unit scale. Keep metadata positions in metres with explicit conversions.

## Deterministic scene generation

Use master seed 20260929 and the existing `condition_seed(master_seed, scene_id)`
helper. GSD never enters the biological seed. Store every sampled value and the
sampler version. Use state-conditioned, bounded engineering variations;
do not claim sampled frequencies are natural population distributions.

Generate 25 accepted scenes per target. Select the initial IDs deterministically
before capture. Validate geometry at every GSD before admitting a scene. Store
rejected attempts and reasons; deterministic replacement IDs must follow a
recorded ordering. Never regenerate a poor-looking but valid scene or modify
the camera/animal after inspecting detector performance.

Freeze each biological scene once. Save evaluated ocean mesh and animation
state, source time, transforms, light/material state, dependencies and a
canonical biological-manifest hash. Derive all five images from that snapshot.
Camera changes are excluded from the biological hash but included in each
render manifest. Pausing only the USD timeline is insufficient: application
update callbacks must be gated through the existing capture mechanism.

Require identical scene identity and evaluated geometry across the pair, with
only declared camera changes. Renderer stochastic settings have their own
metadata namespace; do not imply that one biological seed controls RTX noise.
Measure replay RGB variability; do not promise bitwise identical RGB.

## Annotations and visibility

Required geometry labels are the projected envelope of evaluated animal mesh
geometry, including parent transforms and skeletal pose, with explicit clipping.
Do not call the current projected world AABB an exact animal box. Record both
unclipped and clipped boxes, projected centroid definition, root world position,
heading, state, altitude/depth, actual GSD and image dimensions.

Use COCO pixel-edge `x,y,width,height` boxes with origin at the upper-left.
Separate full projected animal extent (amodal geometric box) from a visible RGB
extent. A visibility attribute alone does not establish visibility through water.
Actor-on/off comparisons can support presence checks but are not segmentation
ground truth. Shadows, reflections, refraction and renderer noise need explicit
treatment in that check.

M4 must demonstrate that the selected label convention corresponds to the
visible target for each admitted state at all five GSDs. If water refraction or
occlusion prevents that, record the state as unsupported for the initial label
policy, or establish a validated visible-box method before admitting it.
Do not silently export misleading underwater labels. Record truly invisible
targets separately from render failures and deliberate empty scenes. Retain
their paired records; do not cherry-pick GSD variants with easier visibility.

Report bounding-box width/height, projected silhouette area if reliably
computed, and visible area only if a validated method exists. Bounding-box area
must never be substituted for silhouette or visible animal area. Missing mask
area is null with an explanation. Segmentation delivery is optional.

## Dataset, splits and negative examples

The minimum positive set is 2 targets x 25 scenes x 5 GSDs = 250 images.
Assign 15/5/5 scene groups per target to train/validation/test using a fixed,
seeded permutation, before expanding GSD variants. Record the permutation
algorithm and generated IDs. Stratify reviewed states if multiple states are
used; fail if a promised stratum has no evaluation support.

Use the existing split validator for scene, condition, asset-instance and
sequence IDs. Give each newly generated scene its own instance and sequence
identity; all variants and derived samples keep their parent identity. A source
asset hash is shared across scenes and splits by design. This is not evaluation
on unseen animal meshes or individuals; state that limitation prominently.

Select five parent scenes per target (3 train, 1 validation, 1 test) by a seeded
ordering before rendering. Render an additional target-absent counterpart at
all five GSDs, preserving the parent split and frozen background. This adds
50 intentional negative images, for 300 minimum images including controls.
Do not relabel positive images with missing annotations as negative. Record
the target-presence intervention separately from the five positive GSD variants.

## Model inputs and baseline

Train one detector on the pooled GSD training split with a single `wildlife`
detection category. Keep species in scene metadata and report metrics separately
for each target. This is detection, not a test of species classification.

Keep the captured 1024 x 768 raster at scale 1. Pad to 1024 x 1024 at the model
boundary with a fixed documented value and offset. Disable automatic resize,
random scale, mosaic and random crops. Record the complete image-to-model
affine transform and verify with a known box. Keep original and model-input
pixels-on-target; they should differ only by location under padding.

No detector package was found in the three audited Python runtimes. Resolve
and lock one standard detector, dependency versions, pretrained checkpoint
hash/source/licence, optimizer, learning rate, batch size and hardware in M6.
Do not silently substitute an unrelated algorithm or pretend an installed
baseline exists. A single conventional pretrained detector is the intended
baseline; no architecture comparison or hyperparameter search is in scope.

Freeze training seed 20260929 and a 20-epoch pilot budget. Select the saved
checkpoint using pooled validation AP50 only. Set the operating confidence
threshold once, using the pooled validation precision-recall curve to maximize
F1 (choose the higher confidence in a tie); apply that single threshold to all
targets and GSDs. Do not select per-GSD thresholds. Lock detector NMS settings
with the model configuration. No test-set tuning is permitted.

## Evaluation and interpretation

Match predictions and ground truth one-to-one at IoU >= 0.5. Report TP, FP,
FN, precision and recall at the fixed operating threshold, and AP50 from the
confidence-ranked predictions. Since there is one detection category, label
its value AP50; if a library names it mAP50, explain the single-class case.
For species-specific reports, use that target's positive frames and its
preassigned negative controls. Report false positives per negative frame too.

Use identical held-out scene groups at every GSD. Show scene counts and raw
numerators/denominators alongside curves. Provide binomial uncertainty for
single-GSD recall, and preserve scene pairing in any cross-GSD bootstrap or
comparison. Never treat five versions of a scene as independent replicates.
With only five held-out positive scenes per target, recall advances in steps
of 0.2. The curves establish pipeline operation, not a stable GSD threshold.

## Native capture and preservation

M4 performs one bounded native marine validation after its resource preflight.
Use the existing <=2/255 overlap mean-error tolerance and full-image geometry,
dimensions and restoration checks. A focused tile pair passing is not a full
native image certificate. Stop on resource or capture failure, retain evidence,
and distinguish radiometric inconsistency from a demonstrated memory limitation.
Do not infer required VRAM from a failed run; report measured and unknown values.

Proceed with a validated reduced-resolution generic capture if native remains
unavailable. Sony native rendering and GAMA behaviour are not prerequisites.
Do not alter the existing ocean, swimmers or live camera for audit convenience.
Capture uses bounded temporary ownership and restoration, not a parallel web
server or renderer. Avoid Kit restarts and preserve an existing scene first
whenever a later change genuinely requires one.

## Provenance and changes

Record the source commit plus dirty diff, relevant untracked source, app and
extension versions, exact config and asset hashes, source documents, seeds,
renderer state, GPU/driver and dependency versions. Content-address images,
annotations, splits and checkpoints. Never hash or publish credentials.

Any protocol change before data generation needs a reason and version update.
After dataset freeze, preserve the old version and create a new experiment
revision rather than silently replacing evidence. M8 ends this sprint before
species expansion, biological modelling or operational threshold claims.
