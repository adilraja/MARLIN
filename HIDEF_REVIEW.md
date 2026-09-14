# HiDef geometry and uncertainty review — 2026-09-14

Follow-up: the viewport-matrix discrepancy identified below has been resolved
for new version-2 captures; see [CAPTURE_PROJECTION_FIX.md](CAPTURE_PROJECTION_FIX.md).
The historical audit and original artifacts below remain unchanged as evidence.

## Outcome

The numerical reconstruction and authored USD cameras are consistent. Agreement
with the paper is close, not exact. **Deployment calibration is not established.**
An additional discrepancy was found in saved viewport-matrix metadata; therefore
this review does not certify every marine RGB image as aligned with its GSD maps.
No runtime source, active specification, animals, ocean, or live Kit state was changed.
No message was sent to Ger.

Reproducible results: [audit report](artifacts/camera_validation/hidef_audit_iv32zz7c/report.json).
This contains fresh full-resolution extrema for six cases, input/code hashes,
endpoint errors, footprints, gaps, USD projection tests and saved-artifact checks.

```bash
/home/madil/opt/blender-5.0.1-linux-x64/blender --background --factory-startup --python-exit-code 1 --python tools/audit_hidef_camera.py
```

## Independent comparison

All predictions were calculated before loading the comparison targets. Values
below are cm/native pixel, using precise inferred rolls and the paper-effective
36 × 12 mm aperture. No fitting was performed.

| Roll | Direction | MARLIN min–max | Published min–max | Absolute error min / max | Relative error min / max |
|---|---|---|---|---|---|
| 7.7675° | Width | 2.230198–2.496944 | 2.22–2.49 | 0.010198 / 0.006944 | 0.4594% / 0.2789% |
| 7.7675° | Height | 2.535429–2.899999 | 2.53–2.89 | 0.005429 / 0.009999 | 0.2146% / 0.3460% |
| 23.1748° | Width | 2.413005–3.142100 | 2.40–3.14 | 0.013005 / 0.002100 | 0.5419% / 0.0669% |
| 23.1748° | Height | 2.664823–3.364277 | 2.66–3.36 | 0.004823 / 0.004277 | 0.1813% / 0.1273% |

The targets were checked against section 5.3 of
[Bartlett et al. (2025)](https://doi.org/10.1016/j.ecoinf.2025.103242),
using the [accessible article text](https://www.researchgate.net/publication/392682958_Supporting_offshore_wind_growth_Automating_data_analysis_in_digital_aerial_surveys_to_enhance_wildlife_protection_and_survey_efficiency).

### What explains the discrepancies?

- Nominal nadir GSD is 2.003649635 cm/px. It is not an oblique validation target.
- Five of eight endpoint errors exceed 0.005 cm/px: ordinary nearest-hundredth
  rounding alone cannot explain them. The authors' exact formatting/aggregation
  convention is unavailable; this is not proof of an error in the paper.
- Replacing precise rolls with 7.77°/23.17° changes endpoints by at most
  0.00005856 / 0.00031502 cm/px respectively. Roll rounding is insufficient.
- The independent manufacturer-ROI hypothesis (36.168 × 12.056 mm aperture)
  increases every endpoint, worsening this comparison. It is not adopted as a fix.
- Sampling/aggregation and unresolved reconstruction conventions remain possible
  contributors, not established explanations. The paper discusses pixel centres
  and averaged pixel sides; reproducing its exact implementation requires its
  code or unrounded outputs. No focal length, crop, pose or altitude was fitted.

## Inputs, provenance and conventions

| Parameter | Value / status | Evidence category |
|---|---|---|
| Output; focal length; nominal height; pitch | 6576 × 2192; 150 mm; 549 m; 30° from nadir | Published |
| Effective aperture | 36 × 12 mm in nominal equations | Published model, not calibrated sensor/ROI |
| Candidate camera identity | Prosilica GT6600C | Inferred from metadata |
| Candidate native sensor | 6576 × 4384; 5.5 µm pitch | Manufacturer specification, conditional on identity |
| Roll | Initial estimates 7.5°/22.5°; simulation 7.7675°/23.1748° | Inferred geometric reconstruction, not measured mountings |
| Acquisition and ROI origin | ROI more plausible; binning possible; mode/offsets unknown | Unresolved deployment details |
| Historical height | Barometric record, not known camera-to-sea distance | Published record; target reference unresolved |
| Lens calibration and mounting | Intrinsics, distortion, exact lens/focus, measured pose unavailable | Unresolved, deployment-specific |
| Principal point, distortion, array origin | Centred, zero distortion, coincident origins | Explicit MARLIN assumptions |

The existing [evidence note](source/extensions/cris.madil.render_service/config/CAMERA_EVIDENCE.md)
retains the complete record. Exact yaw is not inferred from possible glare-driven
rig reversal. Missing aircraft attitude cannot be recovered from nominal geometry.

Y is vertical, camera centre (0,549,0) m, target plane Y=0.
`Rx(pitch) Rz(roll) R_nadir`: roll is cross-track tilt, not optical-axis roll.
At native resolution fx=fy=27400, cx=3288, cy=1096 (image-edge origin).
Pixel centres are (i+0.5,j+0.5). For right R, up U, forward F:
`d = F + (u-cx)/fx R - (v-cy)/fy U`; `P = C - 549/d_y * d`.
Width and height GSD are separate forward-neighbour distances. Missing final
neighbours are NaN. Pixel area is a projected quadrilateral, not simply width
times height. These maps concern the flat plane, not waves or underwater refraction.

Oblique bottom/top edge lengths are 151.4229/158.7895 m (inner camera) and
175.4141/185.9481 m (outer). Mirrored four-camera facing-edge clearances are
20.0363–21.0089 m for outer/inner pairs and 20.0057–20.9448 m centrally.
The central maximum does not exceed 21 m under this definition. Neither baselines
nor angles were adjusted to force the paper's gap description.

## Authored camera versus recorded viewport

Fresh USD tests at both precise rolls and divisors 1, 2, 4 sampled 81 image
locations each. Maximum discrepancy was 6.14e-12 pixels. Independent matrix
rays and runtime scalar rays agreed within 8.04e-14 m. Native calculations do
not require native rendering. Twelve existing HiDef/shared regression tests passed.

Three saved Kit stages were hash-verified and their authored cameras tested:
maximum error below 2.3e-12 pixels. But their recorded viewport matrices disagree:

| Saved capture | Expected vertical projection scale | Recorded scale | Maximum sample reprojection error |
|---|---:|---:|---:|
| oblique_zg8cz847 | 25 | 11.755952 | 144.890 px |
| oblique_s345vic1 | 25 | 11.755952 | 144.890 px |
| oblique_6h25133y | 25 | 19.592697 | 59.156 px |

The two prior metric images nevertheless passed nine-target raster checks:
maximum bounding-box errors 1.761/1.530 px, minimum IoU 0.9707/0.9630.
The first review image was visually reinspected. These facts suggest a
display-aspect matrix versus capture-product distinction; that mechanism is
**not yet proven**. Do not use `actual_projection_matrix` as verified RGB
intrinsics. Repeatability alone cannot detect a consistently wrong mapping.

Next bounded task: record the actual capture-product projection separately from
the UI matrix and validate that same marine capture path with known pixel targets.
Do not adjust the correct USD intrinsics merely to match the UI matrix.
The present four-part review is delivered, with this issue explicitly open;
end-to-end marine image/GSD alignment is not newly certified.

[Questions for Ger — draft only](GER_CAMERA_QUESTIONS.md). Biological detectability
and new native-resolution rendering remain outside this milestone.
