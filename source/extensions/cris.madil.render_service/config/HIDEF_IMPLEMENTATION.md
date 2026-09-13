# HiDef Prosilica GT6600C reconstruction

## Official hardware evidence — checked 2026-09-13

Allied Vision's [GT6600 datasheet](https://www.alliedvision.com/assets/support/Camera-Documentation/Allied-Vision/Cameras/Prosilica/Data-Sheets-Discontinued/Prosilica_GT_6600_DataSheet_en.pdf)
lists 6576 × 4384 native pixels, 5.5 µm square pitch, ON Semi KAI-29050
progressive CCD, global shutter, 4 fps full-frame, Gigabit Ethernet/PoE,
14-bit ADC and 128 MB image buffer. F-mount is listed; EF control is an option.
The colour variant supports Bayer and processed colour outputs. ROI, vertical
and horizontal binning are available. Exposure and gain are configurable;
sensor-noise performance tables are explicitly for monochrome models and are
not a calibrated colour-camera noise model.

The [GigE feature reference](https://www.alliedvision.com/assets/support/Camera-Documentation/Allied-Vision/User-guides/GigE_Features_Reference.pdf)
defines OffsetX/OffsetY as readout origins and provides ROI and binning controls.
These capabilities do not identify the historic acquisition settings. The
[current documentation index](https://www.alliedvision.com/en/support/camera-documentation/area-scan-cameras-documentation/prosilica-gt-documentation)
lists this model as discontinued; its current family user guide does not contain
a GT6600 model entry. The archived model datasheet is therefore used here.
No firmware, driver, SDK or camera CAD model is required for a USD pinhole replica.

## Reconstruction, not deployment certification

Fixed: focal length 150 mm, camera-to-flat-plane separation 549 m, pitch 30°
FROM NADIR. Default requested rolls are 7.77° and 23.17°; the precise prior
paper-reconstruction values 7.7675° and 23.1748° are also accepted explicitly.
Roll is cross-track tilt: Rx(pitch) Rz(roll) R_nadir, not optical-axis image roll.
Combined off-nadir angle exceeds the pitch component. World is Y-up, USD local
view direction is -Z. No look-at correction silently recentres the footprint.

Default `paper_effective` aperture is 36 × 12 mm. The alternative
`manufacturer_roi_hypothesis` uses 36.168 × 12.056 mm (5.5 µm native pitch
times output dimensions), explicitly assuming half-height ROI, not binning.
Neither assumes that actual deployment ROI centring is known: a centred
principal point is a reconstruction assumption in both modes. Native full
sensor height is 24.112 mm. Do not mix the two aperture models to fit results.

Model identity and roll mounting remain inferred. Historical altitude was
barometric, not measured frame-by-frame sea-relative distance. Lens identity,
focus, intrinsics, distortion, acquisition settings and ROI offsets remain
unresolved. Zero distortion/DOF/motion blur are geometry-test assumptions;
colour processing, noise and optical MTF are not validated by this implementation.
Sony, animal calibration, the active survey specification and existing camera
evidence have not been changed. No message is sent to Ger.

## Implementation and commands

`hidef_camera.py` specialises the existing metric-target fixture. USD optical
values are converted to tenths of scene units, preserving 150 mm physically.
Nine 8 m square targets span the oblique image; their predicted polygons and
local width/height GSD are recorded. A separate Kit context/viewport is used.
The native output is 6576 × 2192. Preview divisors 2 and 4 retain the same
aperture/pose/FOV and have correspondingly coarser GSD; they are NOT full-GSD data.

```bash
curl -sS -X POST http://localhost:8011/scene/camera/hidef/capture \
  -H 'Content-Type: application/json' \
  -d '{"roll_deg":7.77,"downsample":4}'
curl -sS -X POST http://localhost:8011/scene/camera/hidef/capture \
  -H 'Content-Type: application/json' \
  -d '{"roll_deg":23.17,"downsample":4}'
```

For a full-resolution request use `"downsample":1,"allow_full_resolution":true`.
Check GPU headroom first; earlier Kit OOM failures must not be ignored. Each
request returns a unique directory containing scene.usda, RGB and metadata.
The existing `tools/capture_calibration_target.py --measure-existing DIRECTORY`
checks projected polygons against rendered metric targets. This is a diagnostic
image measurement, not wildlife annotation. Errors/black images are failures,
not successful validation merely because HTTP returned 200.

Published directional GSD targets remain separate in
`bartlett_validation_targets_v1.json`. Existing `validate_bartlett_camera.py`
computes full-resolution width/height maps without tuning parameters. The
rounded requested rolls can be compared separately from the precise paper rolls.
An oblique HiDef image must never be reported simply as GSD=2 cm/px.

## Verified results — 2026-09-13

Native-resolution numerical predictions, cm/px (rounded requested rolls):

| Roll | Width direction | Height direction |
| --- | --- | --- |
| 7.77° | 2.230201–2.497002 | 2.535431–2.900042 |
| 23.17° | 2.412891–3.141785 | 2.664743–3.364055 |

Endpoint discrepancies against the precise-roll published comparison are below
0.54%; they are reported, not fitted away. The nominal nadir calculation is
2.0036496 cm/px, not the actual oblique GSD.
Full per-pixel extrema and error values:
`artifacts/camera_validation/hidef_rounded_0v0wzw0i/report.json`.

Live Kit validation used exact 1644 × 548 images (divisor 4):

| Roll | Directory under artifacts/calibration | Maximum bbox error | Minimum polygon IoU |
| --- | --- | --- | --- |
| 7.77° | oblique_zg8cz847 | 1.761 px | 0.9707 |
| 23.17° | oblique_s345vic1 | 1.530 px | 0.9630 |

All nine targets in each case passed the existing 2-pixel/0.95-IoU tolerances
at three contrast thresholds. Green outlines in review.png are predicted
polygons; white rectangles are rendered geometry. Viewport grid overlays remain
visible, so these are diagnostic captures, not clean dataset images. The default
USD stage was retained. Five new host-independent HiDef tests pass; existing
geometry tests also pass (two USD-dependent cases skipped on the host runtime).

Full 6576 × 2192 rendering is implemented but NOT yet GPU-validated. At the
start of this run the RTX A2000 had 4427 of 6138 MiB occupied, and earlier
out-of-memory failures make an unguarded native capture inappropriate.
Quarter-resolution success does not prove native-resolution rendering works.
This is geometry validation, not complete sim-to-real validation of sensor
noise, optics, radiometry or wildlife detectability. Sony remains untouched.
