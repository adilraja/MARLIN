# Sony ILX-LR1 provisional trial camera

The Sony camera reuses the HiDef frozen-scene capture, USD camera authoring,
directional ray maps, GPU preflight, capture lock, replay and viewport restoration.
It does **not** inherit HiDef pitch, roll, ROI or camera identity. Existing water,
lighting, animals and the active survey specification are not changed by capture.

## Inputs and evidence

| Parameter | Value | Evidence status |
|---|---|---|
| Camera | Sony ILX-LR1 | Published trial parameter, supplied by user |
| Focal length | 85 mm | Published trial parameter; exact lens unresolved |
| Flight altitude | 150 m | Published trial parameter; height reference unresolved |
| Sensor | 35.7 × 23.8 mm | Manufacturer specification |
| Large 3:2 image | 9504 × 6336 px | Manufacturer-supported mode; trial selection unresolved |
| Simulation height | 150 m above flat reference sea plane | Explicit assumption |
| Pose | Nadir, image right +X, image down +Z; Y vertical | Explicit assumption; mounting angles unresolved |
| Principal point | Centred; square pixels | Ideal-pinhole assumption, not calibration |
| Distortion | Zero | Assumption, not measured |

Manufacturer sources: [Sony specifications](https://helpguide.sony.net/ilc/2390/v1/en/contents/221h_specifications.html)
and [JPEG/HEIF image sizes](https://helpguide.sony.net/ilc/2390/v1/en/contents/0404M_jpeg_image_size.html).
Published trial reference: Bartlett et al. (2025), *Ecological Informatics* 90,
103242. Reported 0.6629 cm/px and 63 m swath are comparison targets, not fitting inputs.

Independent calculation: `150 * 35.7 / 85 = 63 m` swath;
`63 / 9504 * 100 = 0.6628787879 cm/px`. Vertical footprint is 42 m.
Derived effective sample pitch is 3.756313 µm—not calibrated hardware pitch.
The initial preview divides both image dimensions by eight, retaining the full
field of view: **1188 × 792 px, 5.3030303 cm/preview pixel**.
Native geometry is supported for calculation; native rendering is deliberately
not exposed yet. Do not label a preview as 0.663 cm/px data.

## Capture and replay

With Kit running and the existing marine scene loaded, from the project root:

```bash
python3 tools/capture_sony_marine.py
python3 tools/capture_sony_marine.py --target-x 0 --target-z 10
python3 tools/capture_sony_marine.py --replay sony_CAPTURE_ID
```

Use the actual returned capture ID. HTTP endpoints:
`POST /scene/camera/sony/marine/capture` with `{}` or target coordinates in metres;
`POST /scene/camera/sony/marine/{capture_id}/replay`.
Unsupported fields (including HiDef roll/pitch) are rejected.

Outputs in `artifacts/sony_marine/sony_*/`: frozen `scene.usdc`, `rgb.png`,
`metadata.json`, compressed directional GSD/anisotropy/pixel-area maps and PNG
diagnostics. Metadata records assumptions, renderer state, dependencies/hashes,
camera geometry and restoration checks. Scene snapshots reference external
textures/runtime materials; these dependencies must remain available for replay.

The live camera/scene is restored after capture. The screenshot is not intended
to permanently replace the demonstration viewport. Animals outside the fixed
63 × 42 m footprint are not moved or resized to fit.

Review original/replay using `tools/review_hidef_marine.py ORIGINAL_DIR REPLAY_DIR`
with a Python environment containing NumPy and Pillow; despite its legacy name,
the reviewer supports both cameras and preserves their image aspect ratios.

## Limits and tests

### Sony-specific image/GSD validation — 2026-09-14

The version-2 capture path has now been checked with nine 8 × 8 m targets at
15%, 50% and 85% of image width and height. These targets are added only to a
frozen diagnostic copy; camera geometry and live animals are unchanged.

Probe: `artifacts/sony_marine/sony_39sl5rol`. All nine targets passed the existing
2-pixel bounding-box / 0.95 polygon-IoU thresholds at three contrast thresholds.
Maximum bbox error: **1.142857 px**. Minimum IoU: **0.986453**.
Expected target dimensions: 150.857143 × 150.857143 pixels; thresholded raster
boxes were 151 or 152 pixels wide/high. Integer raster measurements do not imply
subpixel physical calibration.

Both directional maps range from 5.303030303029743 to 5.303030303030454 cm/px;
anisotropy is 1 within numerical precision; effective pixel area is approximately
28.1221304 cm² per preview pixel. The missing forward-neighbour boundaries remain
NaN. Capture-matrix reprojection error was **0.000012684 px**, well below the
0.001-pixel numerical check. Sampled GSD maps matched the independent scalar rays.

Normal marine capture: `sony_e9yl1vk9`; replay: `sony_60p_93va`. Their scene,
camera and maps matched; mean absolute RGB difference was **0.007048/255**.
All restoration checks passed. The normal image was visually inspected: one
animal near the centre, with most swimmers outside this fixed footprint at
capture time. Animals were not repositioned or rescaled to fill the image.

Machine-readable evidence is in each folder's `projection_validation.json`,
the probe's `validation.json`, and the original marine folder's `verification.json`.
The probe's `review.png` shows predicted outlines over the measured image.
Six Sony tests, four projection tests and seven shared HiDef regression tests
passed (17 total). Eleven swimmers and ocean animation remained active afterward.
Kit was not restarted; controllers were resumed after extension hot-reload.

**Conclusion:** the tested 1188 × 792 Sony preview is geometrically validated
against its flat-plane GSD maps through the marine capture path. This validates
the simulation, not the trial's actual mounting, acquisition mode, lens or
intrinsics. Native rendering and biological detectability remain deferred.

To reproduce the diagnostic (normal capture commands above remain unchanged):

```bash
curl -s -X POST http://localhost:8011/scene/camera/sony/marine/capture \
  -H 'Content-Type: application/json' -d '{"projection_probe":true}'
# With NumPy/Pillow available, use the returned directory:
python3 tools/capture_calibration_target.py --measure-existing CAPTURE_DIRECTORY
python3 tools/verify_capture_projection.py CAPTURE_DIRECTORY
```

### Earlier implementation verification

Verified in running Kit on 2026-09-14: original `sony_32g5ti12`, replay
`sony_4ek_ada7`, framed at X=0 m, Z=-30 m. Both passed all seven viewport/state
restoration checks. Frozen scene and numerical maps were identical on replay;
mean absolute RGB difference was 0.057784/255 (engineering threshold 2/255).
The original folder contains `verification.json` and `review.png`. Visual
inspection confirmed visible animals, including an animal clipped at the upper
edge. The captured water looks mostly uniform from nadir; no water/material
changes were made to improve that appearance. The restored live overview was
also inspected, and eleven swimmers remained running.

Five Sony geometry/USD tests and seven shared HiDef regression tests passed.
Live API validation rejected both a HiDef roll field and native-resolution
render requests. These checks validate this provisional implementation, not
the unresolved trial configuration.

Mode, crop, image format, exact lens, focus/aperture, distortion correction,
intrinsics, mounting attitude, altitude reference, shutter/readout, exposure,
flight speed and trigger timing remain trial-specific unknowns. No downloads
or Sony SDK are required to create this ideal USD camera.

The maps describe a flat reference sea plane, not waves, animal surfaces or
refracted underwater rays. Uniform nadir directional maps are expected.
Saved demonstration lighting/water are not certified controlled survey conditions.
No biological detectability, calibrated radiometry or flight readiness is claimed.

```bash
/home/madil/opt/blender-5.0.1-linux-x64/blender --background --factory-startup --python-exit-code 1 --python tools/test_sony_camera.py
/home/madil/opt/blender-5.0.1-linux-x64/blender --background --factory-startup --python-exit-code 1 --python tools/test_hidef_marine.py
```
