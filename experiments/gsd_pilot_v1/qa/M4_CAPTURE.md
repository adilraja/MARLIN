# Milestone 4: paired capture and annotation check

Milestone 4 produced one complete five-GSD set for each provisional pilot
target: European storm petrel and harbour porpoise. Each of the ten positive
scenes has a target-absent counterpart made by an explicit visibility
intervention. Only the camera Y position changes across each positive set;
the animal geometry and biological manifest hash remain fixed. All 20 images
are 1024 × 768 PNGs from the existing Kit viewport API. They are an
engineering pilot, not survey-hardware calibration.

The first 0.5 cm/px petrel pair exposed a renderer settling problem: its
positive image had a dark background while its negative image was pale. That
pair is preserved in `renders/milestone_4/rejected_initial_pair/` and excluded
from accepted annotations. Each accepted scene was then restored, allowed to
settle, and captured repeatedly until consecutive full-image mean absolute
RGB change was below 1/255. All accepted captures met that threshold by the
third probe. Their probes and hashes are recorded in `capture_progress.json`.
This is a frame-settling check, not a measured RTX sample count or proof of
bitwise replay identity.

The direct amodal boxes came from *every evaluated `UsdGeom.Mesh` vertex*
under the animal root after parent world transforms and the frozen pose were
applied. The USD camera frustum, camera position, 1024 × 768 aperture aspect,
stage units and bounds were checked for every variant. No world-space AABB was
used as an image label. The COCO boxes use pixel-edge `xywh` coordinates; its
`area` field explicitly means bbox area for detection. Projected silhouette
area and exact visible target area remain null because those quantities were
not established by the direct projection or paired image difference. For the
porpoise, refraction can shift the apparent silhouette away from the direct
amodal box.

The paired RGB difference detected both targets at every tested GSD. The
petrel's direct box shrank from roughly 37 × 44 px at 0.5 cm/px to 5 × 6 px
at 4 cm/px; the porpoise's from roughly 321 × 90 px to 40 × 11 px. At the
coarsest GSD, 20 petrel pixels and 278 porpoise pixels inside their direct
boxes changed by more than the recorded background-drift threshold. These
counts measure paired image change, not segmentation area. Detailed per-pair
thresholds, background maxima and image hashes are in
`qa/m4_capture_validation.json`.

One bounded HiDef native tiled capture on the current RTX A2000 passed its
technical checks: 6576 × 2192 complete image, 8 × 8 tile grid, 210 overlap
checks under the 2/255 mean-error limit (worst 0.806/255), and restoration of
the original viewport and renderer settings. Its GPU preflight had 1964 MiB
free against a 768 MiB minimum. The resulting oblique image was nearly uniform
grey and did not visibly establish bird or porpoise content. It therefore did
not certify native pilot imagery. The validated 1024 × 768 generic top-down
capture is the selected pilot path. The native capture metadata and full image
are retained locally under `artifacts/hidef_marine/oblique_y6p0npos/`, with a
small evidence summary at `qa/m4_native_validation.json`.

The scene checkpoint metadata requested a 1/24-second timeline position,
while the actual Kit checkpoints recorded 1/60 second. All captured animal
attributes were frozen with zero remaining time samples, so this mismatch did
not change scene geometry; it remains recorded rather than silently erased.

To inspect or reproduce the existing captures, see
`renders/milestone_4/variant_index.json`,
`renders/milestone_4/capture_progress.json`,
`annotations/milestone_4_geometry.json`, and
`annotations/milestone_4_coco.json`. The preparation script registers
content-addressed snapshots once and refuses to overwrite an existing index.
The capture script resumes only missing entries. Run it against an active
MARLIN Kit service; use the bundled Python runtime with Pillow for capture
and validation, and the installed Blender runtime for `m4_geometry.py`.

Milestone 5 dataset generation has not begun. The 20 M4 images are a bounded
method check, not the required 300-image pilot dataset.
