# GAMA marine capture audit — 2026-09-18

Follow-up: [the controlled actor-on/off comparison](COUNTERFACTUAL_VERIFICATION.md)
has now verified a local pixel contribution. The original RGB-only audit below is
retained unchanged in scope; recognisable species appearance remains unverified.

Capture: `artifacts/hidef_marine/oblique_2h82kfx4`.
Original RGB, USD snapshot, camera metadata and GAMA sidecar were retained unchanged.
This audit was offline: no Kit restart, actor movement, camera change or re-render.

## Result

**Location and provenance verified. A small image feature is visible at the predicted
location; instance identity and recognisable animal appearance are not certified.**
All eleven automated geometry/provenance checks passed. The original image was
visually inspected using a nearest-neighbour magnification of its actual pixels.

| Item | Verified value |
|---|---|
| Image | 1644 × 548 preview; not native resolution |
| Actor | `/MarlinGamaFixture/Bottlenose_001` |
| Projected origin, top-left image coordinates | (865.9491, 390.3615) px |
| Projected world-space bounding box | x=863.450–868.062, y=389.209–391.323 px |
| Bounding-box extent | 4.612 × 2.114 px; conservative bounds, not segmentation |
| GAMA simulation time / seed | 19.0 s / 184729 |
| State / heading | `shallow_swim` / 91.854617878° |
| Position, metres, Y-up | (0.388362433, -0.8, 11.993713963) |
| Speed / mean-plane depth | 0.628318531 m/s / 0.8 m |

A dark, roughly horizontal few-pixel feature lies within the predicted rectangle.
The enclosing 6 × 3 integer-pixel region has a maximum channel difference of 81/255
from the surrounding median water colour. This measures local contrast, **not** a
detection score or evidence of biological recognisability. The provisional asset
has a world bounding-box extent of approximately 0.405 × 0.134 × 0.149 m; it must
not be interpreted as a physically calibrated adult bottlenose dolphin.

Without an instance-ID/depth pass or actor-on/off reference, the original RGB alone
cannot unambiguously attribute that feature to the actor. Water/refraction,
occlusion and antialiasing are additional caveats. No threshold was invented to
turn contrast into an identity certificate. `gama_state.json` retains its original
`image_visibility_verified:false` value.

## Clock, seed and camera linkage

- GAMA's time=19 s and seed=184729 agree with custom metadata in the frozen USD.
- The complete GAMA state equals the final state in the validated 20-step trajectory.
- Position and heading independently agree with the composed frozen USD transform.
- Camera metadata's `seed:0` means deterministic camera geometry with no
  randomisation; it is **not the GAMA seed**.
- MARLIN's source timeline was 0.265181818181803 s (USD time code
  15.910909090908179); it is **not the ecological simulation clock**.
- Snapshot wall-clock timestamp: `2026-09-17T22:07:33.771139+00:00`.
- The GAMA sidecar binds `scene.usdc`, `rgb.png` and `metadata.json` by SHA-256.
  All three hashes matched. The camera record's scene hash also matched.
- The frozen camera view/projection matrices exactly matched the saved matrices.
  Independent reference-plane reprojection error was at most 9.1e-13 px;
  sampled GSD map error was at most 1.8e-12 cm/px. These checks do not establish
  refraction-aware underwater image geometry or measured hardware calibration.

## Artifacts

- `artifacts/gama/capture_audit_2h82kfx4/verification.json`
- `artifacts/gama/capture_audit_2h82kfx4/visibility_diagnostic.png`
- `artifacts/hidef_marine/oblique_2h82kfx4/projection_validation.json`
- Earlier coexistence test: `artifacts/gama/marine_coexistence_01.json` — 20 applied
  poses, eleven swimmers continuing, ocean advancing, stable lighting/materials/
  camera/settings, capture restoration and isolated actor release all passed.

## Scope of completion

The existing capture is inspected and documented, and its state/camera provenance
is verified. **Strict image-level instance visibility certification remains open.**
Its next bounded test should use an instance-ID pass or controlled actor-on/off
comparison from the same frozen scene, without rescaling the animal or changing
camera geometry merely to obtain a more visible result. No biological detectability
conclusion follows from this preview.

Repeat commands are in the root `RUN_COMMANDS.md`, GAMA integration section.
