# Actor-on/off verification — 2026-09-18

**Result: the isolated GAMA actor contributes pixels at its predicted image location.**
It is still too small in this preview to claim recognisable dolphin appearance.
No physical scale, biological detectability or instance-segmentation certification
is implied.

## Controlled comparison

Source: `artifacts/hidef_marine/oblique_2h82kfx4` (1644 × 548 HiDef preview).
The original RGB, USD, camera metadata and GAMA sidecar hashes remain unchanged.

Two private source copies were made. The on copy retained the original USD bytes;
the off copy changed only
`/MarlinGamaFixture/Bottlenose_001.visibility` to `invisible`.
An exact text roundtrip check verified that removing this single intervention
restored the original layer content. Animal scale/pose, camera geometry, lighting,
water and all other animals remained identical.

MARLIN's existing snapshot replay rendered **on → off → off → on**. Two repeats
per state measured same-state RGB variation. All four captures passed existing
viewport/restoration checks and matched the source camera configuration and matrices.
No new renderer or live-scene visibility intervention was introduced.

## Pixel evidence

Predicted origin: (865.949, 390.362) px. Conservative projected bounds:
x=863.450–868.062, y=389.209–391.323 px. The enclosing integer ROI is
`[863,389,869,392]` (18 pixels).

- 11 ROI pixels had a consistent signed channel change in all four on/off pairings.
- Each qualifying channel exceeded both observed same-state variations by more
  than one 8-bit code value.
- Maximum same-state ROI difference: 11/255.
- Maximum cross-state ROI difference: 77/255.
- Visual review: the small dark horizontal feature is present on, absent off,
  and matches the location of the difference signal.

The rule was coded before inspecting the render outputs. It is a bounded
engineering check, not a statistical significance test. Across the full image,
147 pixels met the same rule; these are **not all assigned to the actor**.
Visibility can influence reflections/shadows, and two repeats cannot characterize
all renderer variability. The derived binary image is not a ground-truth mask.

## Restoration and tests

Original scene layers, active camera, lighting/material attributes, renderer settings
and ocean parameters matched after rendering. All eleven gallery swimmers advanced
without deformation errors, and the ocean advanced.

The initial report sampled immediately after restoration, before update callbacks
ran, so its immediate motion check was inconclusive. A separate `resume_audit.json`
confirmed subsequent progression. Original observations were retained; future
diagnostics wait two seconds before checking resumed motion.

Four synthetic pixel-analysis tests and six real-USD actor tests passed, including
the new visibility-only intervention test. The nine exchange and three live-protocol
tests also passed (22 total).

## Evidence

- `artifacts/gama/counterfactual_i9hp7lh1/render_report.json`
- `artifacts/gama/counterfactual_i9hp7lh1/resume_audit.json`
- `artifacts/gama/counterfactual_i9hp7lh1/analysis.json`
- `artifacts/gama/counterfactual_i9hp7lh1/comparison.png`

The render report identifies all derived input/output capture IDs. Artifacts remain
local and Git-ignored; the code, commands and this verification summary are versioned.
No GAMA server was required. The live marine presentation was left running.
