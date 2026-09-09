# Isolated planar-target engineering test

This is a validated ideal-nadir projection fixture, **not** the HiDef oblique replica, Sony trial camera, wildlife dataset exporter or a biological scale calibration. The survey specification and animal assets are unchanged.

## Run

With Kit and `cris.madil.render_service` running, use a Python environment with Pillow and NumPy:

```bash
python3 tools/capture_calibration_target.py
```

The system `python3` on this machine currently lacks Pillow. The successful tests used the available bundled environment:

```bash
/home/madil/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B tools/capture_calibration_target.py
```

Run from the repository root. `--config PATH` accepts a complete JSON configuration. `--measure-existing DIRECTORY` rechecks an existing capture without contacting Kit. The client exits nonzero on failed validation.

POST `/scene/survey/calibration/capture` accepts the explicit fields in `calibration_target_v1.json`. Missing fields are errors; the API does not fill unknown camera intrinsics or units with guesses. It returns the artifact directory and metadata, with status `rendered_not_yet_measured`. The client separately writes `validation.json`; an HTTP `ok` alone is not a geometry pass.

## Default fixture

- Hypothetical square-pixel pinhole: 50 mm focal length, 5 µm pixel pitch, 1024 × 768 output.
- Target: 2 m across world X by 1 m along world Z; camera 100 m above it, looking along −Y.
- Scene unit: explicitly 0.01 m. The target is at Y=1000 m, away from any ground-grid overlay; the camera is at Y=1100 m. This is a numerical fixture, not a flight altitude recommendation.
- USD optical attributes use tenths of scene units, converted consistently with the stage unit metadata.
- Expected GSD: 1 cm/px. Expected box: `[412, 334, 200, 100]`, using top-left image-edge coordinates.
- White emissive target on a large black backing plane. No source assets, ocean, animal motion or stochastic placement.

The fixture is created in a unique **separate named USD context**, rendered with a temporary viewport, then closed/destroyed in cleanup. The default stage is never replaced. The endpoint does not start/stop controllers, change the default camera or set global renderer settings. Loading updated extension code can stop existing controllers through the extension's normal shutdown; that is distinct from executing the capture endpoint. The temporary test window may briefly appear while capturing.

## Validation and evidence

Initial testing caught Kit overriding the requested resolution during window layout (632 × 448 instead of 1024 × 768). The image validator rejected that output. The implementation now reapplies the resolution after layout and checks it before capture.

The corrected capture in `artifacts/calibration/nadir_osdmmnyn` measured exactly `[412,334,200,100]` at 35%, 50% and 65% of the image's observed contrast range. All coordinate/size errors were zero pixels and measured GSD was 1 cm/px along both axes. Inspect the image and `validation.json` for evidence. The initial failed capture is retained separately rather than overwritten.

RGB thresholding here is only a diagnostic for an intentionally isolated high-contrast rectangle. It is **not** renderer-ground-truth segmentation and must not be reused for wildlife labels. Pass criteria include exact output dimensions, adequate contrast, and all three threshold boxes within 2 pixels of prediction. This establishes central planar scale, not distortion, off-axis/oblique projection or complete orientation calibration.

Each unique capture directory contains `scene.usda`, `warmup.png`, `rgb.png`, `metadata.json` and (after client validation) `validation.json`. Metadata includes explicit configuration, units, intrinsics, camera transform conventions, expected box/GSD, actual resolution and viewport matrices, geometry seed, stage hash and limitations. Global renderer appearance settings are inherited, not frozen; RGB bitwise reproducibility is not claimed. Failed captures may leave partial directories for diagnosis.

Tests: standard-library input/math tests run in the normal suite. Run `tests/test_calibration_geometry.py` through Blender for actual USD projection tests; both metre and centimetre unit conventions are checked independently through the authored USD camera's projection matrix.

Implementation references: NVIDIA's [separate viewport/context API](https://docs.omniverse.nvidia.com/kit/docs/omni.kit.viewport.utility/latest/omni.kit.viewport.utility.create_viewport_window.html) and [viewport resolution and capture controls](https://docs.omniverse.nvidia.com/kit/docs/omni.kit.viewport.docs/109.0.0/viewport_api.html).

Next milestone: implement and test explicit oblique camera conventions and directional local GSD, while obtaining the missing HiDef/Sony calibration inputs. Do not mark either real camera calibrated from this nadir test.

## Oblique engineering extension (2026-09-09)

Implemented: `calibration_oblique_v1.json` uses 30° engineering pitch and 7.77° roll with the same hypothetical 50 mm / 5 µm camera. It places nine 1 m × 1 m rectangles at image-fraction sample positions 15%, 50% and 85% in each direction. These are known-size **calibration rectangles, not animals**. The raw image intentionally contains nothing else.

```bash
/home/madil/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B tools/capture_calibration_target.py --config source/extensions/cris.madil.render_service/config/calibration_oblique_v1.json
```

Add `--roll 23.17` to test the second engineering roll. These numbers do not establish the PI's rotation convention: pitch here tilts the optical axis toward world −Z from nadir, then positive roll rotates camera right toward the unrolled camera up vector. Camera translation is adjusted to keep the optical axis aimed at the world-plane origin. Basis vectors and position are recorded explicitly; the authored USD transform matches them.

The metadata now contains per-target physical corners, projected polygons and boxes, sample locations and directional ray/plane GSD. GSD X/Y is the Euclidean ground distance between rays one pixel apart along image columns/rows at each sample; the two ground directions need not be perpendicular. The legacy top-level `gsd_cm_px` is only the **nadir reference at vertical height**, not an oblique local value. Do not infer local GSD by dividing physical target width by its rolled image bounding-box width.

For every target, the image validator checks boxes at three contrast thresholds within 2 pixels and polygon IoU of at least 0.95. `review.png` adds target IDs, predicted GSD and green projected outlines; `rgb.png` remains untouched. This labelled review makes the purpose of the otherwise plain capture explicit. It is not a wildlife annotation file. The client prints a concise summary and the review-image path; complete measurements remain in `validation.json`.

The first oblique capture, `artifacts/calibration/oblique_ula84t25`, passed all nine targets. Its directional GSD varies across the frame. Mathematical tests check ray/projection round trips, the zero-roll centre formula (horizontal scale proportional to sec(pitch), vertical to sec²(pitch)), and actual USD corner projection for both engineering roll angles. Real HiDef sensor/crop and rotation conventions remain unresolved. Global appearance settings remain inherited rather than radiometrically calibrated.
