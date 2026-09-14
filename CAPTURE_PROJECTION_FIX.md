# Capture-image projection correction — 2026-09-14

## Cause and correction

NVIDIA documents `ViewportAPI.projection` as the camera projection **in terms
of its UI element** ([API reference](https://docs.omniverse.nvidia.com/kit/docs/omni.kit.widget.viewport/latest/omni.kit.widget.viewport/omni.kit.widget.viewport.ViewportAPI.html)).
MARLIN incorrectly labelled that display-aspect matrix as the actual image
projection. The authored USD camera and raster geometry were not shown to be
wrong by that mismatch; the metadata field was wrong for image reconstruction.

New captures use `projection_metadata_version: 2`:

- `capture_view_matrix` and `capture_projection_matrix`: authored USD camera
  frustum with image-matching aperture aspect. Row-vector USD/Gf convention.
- `ui_view_matrix` and `ui_projection_matrix`: UI diagnostics only.
- `actual_*` matrices remain available as explicitly documented aliases for
  the corrected capture matrices. Their version-1 meaning was different.
- Render-product camera, resolution, square pixels and full data window are
  checked. Unsupported mismatches fail capture instead of silently relabelling.

No focal length, pitch, roll, sensor size, animal calibration or environment
preset was adjusted. Old artifacts are preserved unchanged: do not trust their
version-1 `actual_projection_matrix` for RGB reprojection. Recapture with version
2 rather than silently overwriting historical metadata.

## Same-path raster verification

The optional HiDef `projection_probe` uses a frozen marine-stage copy, hides its
scene geometry and adds nine known targets. The camera, resolution, renderer,
capture operations and restoration path are the same as normal marine capture.
Only the copy changes; probe images are clearly labelled diagnostics, not data.

| Roll | Probe under artifacts/hidef_marine | Maximum bbox error | Minimum polygon IoU |
|---|---|---:|---:|
| 7.7675° | oblique_5vqpn5iu | 1.346 px | 0.9797 |
| 23.1748° | oblique_82yg8on3 | 1.505 px | 0.9736 |

Both passed the pre-existing 2-pixel / 0.95-IoU thresholds at all three contrast
thresholds. Output was 1644 × 548 (divisor 4). Corrected matrix reprojection error
was below 1.5e-12 px; sampled numerical directional-map errors below 6e-12 cm/px.
These numerical tolerances are not claims of equivalent raster or physical precision.

Normal marine capture: `oblique_84nq0v7m`; replay: `oblique_2oh2ojlw`.
Each has a `projection_validation.json`; probes also have raster `validation.json`
and `review.png`. Correct capture projection vertical scale is 25; the normal
capture's UI value was 19.166667. The render product used the requested camera,
1644 × 548 resolution, square pixels and an uncropped image.

All captures restored the live stage/camera/viewport and tracked renderer state.
Eleven swimmers and ocean animation were checked running afterward. Extension
reload required resuming controllers and restoring the previous fog-off state;
Kit was not restarted and no live assets were replaced. Four new projection
regression tests and seven existing shared HiDef tests passed.

## Reproduce

With the existing marine scene loaded:

```bash
curl -s -X POST http://localhost:8011/scene/camera/hidef/marine/capture \
  -H 'Content-Type: application/json' \
  -d '{"roll_deg":7.7675,"downsample":4,"projection_probe":true}'
```

Repeat with roll 23.1748. On each returned directory, using Python with NumPy
and Pillow:

```bash
python3 tools/capture_calibration_target.py --measure-existing CAPTURE_DIRECTORY
python3 tools/verify_capture_projection.py CAPTURE_DIRECTORY
```

Normal capture and replay commands are unchanged. `verify_capture_projection.py`
also checks their version-2 matrices, output hashes and sampled directional maps;
it does not pretend normal wildlife RGB contains metric validation targets.

## Bounded conclusion

The UI-versus-image matrix discrepancy is resolved for new metadata. The tested
HiDef quarter-resolution marine capture path is geometrically aligned with its
flat-reference-plane GSD maps, supported by same-path raster targets. This is
**not** native-resolution GPU validation, deployed-camera calibration, underwater
refraction calibration, or biological detectability certification. Other output
modes and non-square/cropped products require their own validation.
