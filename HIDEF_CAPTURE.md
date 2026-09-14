# HiDef marine capture — reproducible preview milestone

## Scope

One frozen marine scene, one oblique HiDef camera, RGB, camera metadata and
directional ground-sampling maps. No biological detectability experiments,
species calibration, ocean redesign or Sony camera work.

Use `python3 tools/capture_hidef_marine.py` with MARLIN running. Replay with
`python3 tools/capture_hidef_marine.py --replay CAPTURE_ID`.

## Camera and sampling

- Prosilica GT6600C remains inferred from metadata, not certified deployed hardware.
- 549 m camera-to-reference-plane separation; 150 mm ideal pinhole lens.
- 30° pitch from nadir; default 7.77° inferred cross-track roll.
- Pose convention: Y-up; `Rx(pitch) Rz(roll) R_nadir`.
- Paper-effective aperture: 36 × 12 mm. ROI/binning and deployed ROI offset remain unresolved.
- Centred principal point and zero distortion are reconstruction assumptions.
- 6576 × 2192 reference geometry, rendered at 1644 × 548 (4× divisor in each dimension).
- Default optical-axis intersection: X=-3 m, Z=0 m on Y=0. Translation only;
  no height, focal length or angle adjustment to match validation targets.
- Camera position for that default: approximately (-89.49956, 549, 316.96530) m.
- Native nominal nadir GSD: 2.00365 cm/px. This is NOT the preview's actual GSD.
- Preview directional GSD: width 8.92133–9.98735 cm/px; height 10.14304–11.59849 cm/px.

The original finite ocean is retained, not extended. Animals may intersect image
edges. Bounds in metadata are projected world AABBs, not segmentation or proof
of visibility through the water.

## Output package

Every successful run creates `artifacts/hidef_marine/oblique_…/`:

| File | Meaning |
| --- | --- |
| `scene.usdc` | Flattened marine scene with animated attributes frozen at one recorded time, plus the HiDef camera |
| `snapshot_inputs.json` | Inputs written before rendering; exists even if rendering fails |
| `rgb.png` | Actual Kit capture, with editor icons temporarily hidden |
| `warmup.png` | Discarded warm-up capture, retained for diagnostics |
| `metadata.json` | Camera, transforms, resolution, renderer settings, asset dependency hashes, restoration checks, GSD definitions and ranges |
| `directional_gsd.npz` | Float64 per-preview-pixel width GSD, height GSD, height/width ratio and pixel area |
| `gsd_width_cm_px.png` / `gsd_height_cm_px.png` | Diagnostic maps, separately scaled blue-to-yellow |
| `anisotropy_height_over_width.png` | Height-direction / width-direction spacing |
| `effective_pixel_area_cm2.png` | Ground-plane pixel footprint area, not simply width × height |

Pixel coordinates start at the top-left image edge; centres are `(column+.5,
row+.5)`. GSD uses distances to the next centre along each image axis. The last
width column and last height row are NaN; the ratio is invalid on both edges.
Area uses all four projected pixel corners. All these values refer to flat Y=0,
not the actual wave geometry, body surface or refraction beneath water.

## What repeatable means

Replay uses the saved scene, not the live clock or current swimmer positions.
Procedural mesh points are copied; USD time-sampled transforms and skeletal
animation attributes are sampled and reduced to constant values. No new random
placements are generated. Replay checks the saved scene hash, local texture
hashes and tracked renderer settings before rendering.

External/runtime MDL dependencies are recorded but not copied or inspected;
their transitive dependencies are not content-addressed. The package therefore
requires the same compatible Kit runtime and local texture paths. It is not a
fully portable bundle. RGB is not promised bitwise identical across frames,
drivers or machines. Geometry and GSD maps should be identical.

## Runtime safety and restoration

Two simultaneous marine RTX scenes exhausted the 6 GB GPU during development.
Manually releasing its active Hydra renderer also proved unstable. Neither
approach is used in the final marine capture path.

The endpoint gates MARLIN's ocean, swimming, chase-camera and petrel update
callbacks, pauses the timeline, retains the live stage in a separate USD
StageCache, and temporarily attaches the frozen stage to the existing viewport.
The live stage is restored in `finally`, along with camera, resolution, fill mode,
selection, display options, timeline time/play state and controller updates.

Kit automatically reapplies rendering defaults on stage attachment. The capture
reapplies its recorded renderer values after each attachment to prevent fog or
exposure changes. This is restoration of saved values, not application of a new
preset. Seven restoration checks are written to metadata. Float comparison
allows only USD float32 roundoff (relative 1e-7, absolute 1e-9).

At least 768 MiB of free GPU memory is required before a preview is attempted;
this is a conservative preflight check, not a guarantee against driver failure.
Full resolution remains opt-in and unverified. Do not change the scene or issue
other scene-mutating API requests during capture. Calibration and marine capture
share a busy gate, but other endpoint families do not yet use a global transaction lock.

Relevant NVIDIA APIs: [UsdContext stage attachment](https://docs.omniverse.nvidia.com/kit/docs/omni.usd/latest/omni.usd/omni.usd.UsdContext.html)
and [Kit render-setting persistence](https://docs.omniverse.nvidia.com/kit/docs/omni.kit.usd_docs/latest/USD%20in%20Kit.html).

## Verification

Verified pair (2026-09-14):

- Original: `artifacts/hidef_marine/oblique_6h25133y/`
- Replay: `artifacts/hidef_marine/oblique_g6chcza_/`
- `verification.json`: passed; camera and frozen scene file identical;
  all four numerical maps exactly identical, including NaN edge masks.
- Mean RGB absolute replay difference: 0.894745 / 255; maximum channel
  difference 55. RTX output is consequently not bitwise identical.
- Seven capture regression tests passed in Blender; five existing HiDef
  camera tests passed. Existing calibration tests: three passed, two USD-dependent
  tests skipped in system Python (the new USD tests ran in Blender).
- Ocean and all 11 gallery swimmers were confirmed running after replay.

The original package contains `review.png` (RGB plus labelled directional maps)
and `verification.json`. Some specimens are clipped by the frame; the package
does not claim complete coverage of each animal. `config.target_width_m` and
`target_height_m` are unused fields inherited from the calibration-fixture
configuration, not marine-animal dimensions; no metric targets are rendered.

Run CPU/USD regression checks using Blender's bundled USD and NumPy:

```bash
/home/madil/opt/blender-5.0.1-linux-x64/blender --background --factory-startup \
  --python tools/test_hidef_marine.py
```

For a capture/replay pair, `tools/review_hidef_marine.py ORIGINAL_DIR REPLAY_DIR`
requires NumPy and Pillow. It writes a labelled `review.png` and a machine-readable
`verification.json` into the original directory. Checks include image dimensions,
artifact hashes, non-blank output, camera/scene equality, exact GSD map equality
and mean RGB replay error ≤2 on the 0–255 scale. This last threshold is an
engineering replay check, not a biological detection threshold.

The environment is a snapshot of the demonstration scene, not a validated EIA
controlled-survey preset. Animal sizes, poses, helpers/materials and visibility
remain provisional. A visually non-blank image does not resolve those issues.
# Follow-up audit — 2026-09-14

**Resolved for new captures:** [projection fix and raster verification](CAPTURE_PROJECTION_FIX.md).
Version-2 metadata separates capture-image matrices from UI matrices. The
warning below continues to apply to historical version-1 artifacts.

See [HIDEF_REVIEW.md](HIDEF_REVIEW.md). Authored USD cameras agree with the ray
model, but saved `actual_projection_matrix` values do not describe that same
image mapping. Prior replay success does not validate those matrices as RGB
intrinsics. Capture-product versus display-viewport projection remains open;
do not treat the existing metadata field as independently verified calibration.
