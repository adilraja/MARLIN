# Isolated GAMA bottlenose: provisional size candidate

Verified 2026-09-19. This change affects only the optional bridge's private actor,
not the original USD, gallery swimmers, water, lights or camera geometry.

## Basis and measurement

`coastal_candidate_v1` uses a nominal 2.6 m coastal-ecotype size from the
[NAMMCO species account](https://nammco.no/common-bottlenose-dolphin/).
This is a selected reference-size candidate, not a measured specimen or a certified
adult age/sex/ecotype. Morphological and biological calibration remain incomplete.

The hash-bound configuration is
`source/extensions/cris.madil.gama_bridge/config/bottlenose_calibration_v1.json`.
Measurements include every parent transform and the fixed -90 degree X correction.
The corrected animal faces +Z with dorsal +Y; headings retain MARLIN's convention.
No geometry is edited or recentered. Mesh vertex landmarks are rostrum 959,
candidate centreline fluke notch (mean of 6838/6843), and dorsal tip 7552.
The notch requires expert anatomical review. Axial Z separation is not curved
body length and is not asserted equivalent to every literature measurement protocol.

| Quantity | Candidate result |
| --- | --- |
| Unscaled landmark separation | 0.390696797 |
| Scale relative to legacy preview | 6.654776850 |
| Rostrum-to-notch axial length | 2.600 m |
| Full mesh dimensions X/Y/Z | 0.903716 / 0.891478 / 2.665296 m |
| Root Y in fixture | -0.800 m |
| Highest mesh Y at that depth | -0.224379 m |

The root is the original mesh origin, not a measured body centre or blowhole.
The whole mesh lies below the mean Y=0 sea plane. This supports only the fixture's
static shallow-swim pose, not breathing/surfacing. Animated wave-relative clearance,
buoyancy, blowhole position and skeletal motion are not calibrated.

## Provenance caution

The source glTF metadata and `source/license.txt` identify CARI'MAM and
CC-BY-NC-SA-4.0, with the Sketchfab source recorded in the profile. The asset's
top-level `license.txt` instead identifies DigitalLife Model 61A. This conflict is
preserved and flagged, not silently resolved by overwriting licences. Do not assume
the nearby skeletal animation metadata belongs to this single-mesh asset.

## Verification evidence

- `artifacts/gama/bottlenose_review/calibration.json`: measurements.
- `artifacts/gama/bottlenose_review/orthographic.png`: labelled side/top geometry.
- `artifacts/gama/bottlenose_candidate_verification_01.json`: all 20 recorded GAMA
  states replayed; scene preservation, ongoing eleven swimmers/ocean, and private
  layer cleanup passed. This was file replay, not a new live GAMA server trial.
- `artifacts/hidef_marine/oblique_m7hloime/`: RGB, frozen USD, camera metadata,
  directional GSD and GAMA sidecar including `asset_calibration`.
- `artifacts/gama/bottlenose_candidate_capture_audit/verification.json`: all eleven
  geometry/provenance checks passed. GAMA time 19 s, seed 184729; camera seed 0 is
  a separate namespace. Authored and recorded camera matrices match exactly.
- The original-image diagnostic visibly contains a dolphin-shaped feature within
  the projected bounds (30.70 x 14.07 px), centred near (865.95, 390.36).
  Bounds are not segmentation. No new actor-on/off or instance-ID certification
  was performed for this capture; biological detectability is not validated.
- 24 regression tests passed: 8 actor, 9 exchange, 3 live protocol, 4 pixel analysis.

The isolated actor was released after verification; the original live overview and
eleven swimmers were preserved. `legacy_preview` remains an explicit acquisition
option. Both profiles fail closed if the inspected asset hash changes.
