# Camera evidence after paper review — 2026-09-09

Supersedes the earlier unresolved-pitch and generic acquisition questions. No active survey specification, animal calibration or live scene is changed. No message is sent. Source: user-supplied review of Bartlett et al. (2025), *Ecological Informatics* 90, 103242, [DOI](https://doi.org/10.1016/j.ecoinf.2025.103242), with the original sections 5.2–5.5 checked for geometry and numeric comparisons.

## Provenance categories

| Parameter | Value / interpretation | Category |
| --- | --- | --- |
| HiDef model | Candidate Allied Vision Prosilica GT6600C; not deployment-certified | Inferred from metadata |
| Candidate native sensor | 6576 × 4384, 5.5 µm pixels | Manufacturer specification, conditional on candidate identity |
| Recorded output | 6576 × 2192, about 6.51 fps | Published |
| Acquisition | Half-height ROI more plausible than vertical binning ×2; neither confirmed | Inferred from metadata; unresolved mode |
| ROI origin / centring | User-adjustable; deployed offsets unknown | Unresolved |
| Array pitch | 30° from nadir, not horizontal | Published |
| Glare handling | Possible 180° rig yaw reversal, not pitch-sign reversal | Interpretation; exact yaw unresolved |
| Initial roll estimates | 7.5°, 22.5° | Approximate geometric estimates |
| Simulation rolls | 7.7675°, 23.1748°, reconstructed to reproduce 20 m gaps | Inferred from geometric reconstruction, not measured mountings |
| Physical mounting rolls | May differ from reconstruction | Unresolved |
| Nominal model | 549 m, 150 mm, 36 × 12 mm, 6576 × 2192 | Published nominal pinhole inputs |
| Historical altitude | Barometric, not radar; 437.5–580.5 m observed | Published |
| Aircraft attitude record | Heading recorded; pitch/roll absent | Published |
| Historic altitude-to-sea reference | Cannot equate recorded altitude to sea-relative height | Unresolved |
| Sony trial | ILX-LR1, 85 mm, 150 m, nominal 0.6629 cm/px, 63 m swath, autonomous fixed-wing UAV | Published trial parameters |
| Sony acquisition and optical details | Mode, dimensions, crop, RAW/JPEG, correction, intrinsics, distortion, mounting, exact lens and focus unknown | Unresolved, trial-specific |

Manufacturer sources: [Allied Vision](https://www.alliedvision.com/assets/support/Camera-Documentation/Allied-Vision/Cameras/Prosilica/Data-Sheets-Discontinued/Prosilica_GT_6600_DataSheet_en.pdf), [Sony sensor](https://helpguide.sony.net/ilc/2390/v1/en/contents/221h_specifications.html), [Sony available image modes](https://helpguide.sony.net/ilc/2390/v1/en/contents/0404M_jpeg_image_size.html). Sony's 35.7 × 23.8 mm sensor and available 9504 × 6336 output do not establish the trial's selected mode. The derived 3.7563 µm effective pitch remains an approximation, not calibrated intrinsics.

## GSD distinctions

- **nominal_nadir_GSD:** H × sensor dimension / (focal length × output dimension). Paper inputs give 2.0036496 cm/px on both axes. The separate manufacturer-pitch check gives 2.013 and is not substituted for this model.
- **directional_oblique_GSD:** separate ground distances in image-width and image-height directions; no scalar averaging.
- **per_pixel_GSD:** directional values evaluated at individual image locations.
- **effective_pixel_area:** area of the projected pixel quadrilateral in cm²; generally not the product of directional lengths because ground directions need not be perpendicular.

The paper reports no part of its reconstructed imagery reaches 2 cm/px. This is not calibrated knowledge of every historic frame. MARLIN must independently compare rather than force agreement.

## Controlled experiment assumptions

Use a flat plane and 549 m camera-to-plane separation for this controlled validation only. A centred 36 × 12 mm nominal projection is a reconstruction assumption, **not proof of deployed ROI centring**. Keep geometry separate from comparison targets; do not refit the two inferred rolls to the 20 m constraint. Report the chosen rotation order, assumed coincident array origins, simulated swaths and gaps. Exact yaw, mechanical baselines, full original rotation convention and historic height reference remain unresolved. No waves, distortion, curvature or attitude perturbations are introduced.

## Remaining questions for Ger — draft only, not sent

1. Was the HiDef 6576 × 2192 imagery actually acquired using half-height ROI rather than vertical binning?
2. If ROI was used, was it centred? If not, what were the offsets?
3. Can the deployed camera be confirmed as the Allied Vision Prosilica GT6600C?
4. What exact 150 mm lens was used, and was focus fixed?
5. Were physical camera roll mounting angles measured? If so, what were they?
6. Is nominal 549 m intended height above the sea/target plane, or nominal barometric flight altitude?
7. Is intrinsic calibration available: fx, fy, cx, cy and distortion coefficients?
8. For the Sony trial: exact image dimensions/mode, crop, image format, distortion/lens correction, mounting pitch/roll/yaw, exact 85 mm lens, focus setting and intrinsic calibration?

Do not ask to reconfirm basic Sony trial values or the 30°-from-nadir pitch. Stop at geometry validation; do not proceed to biological detectability.
