# GAMA single-actor fixture verification — 2026-09-17

Follow-up: the populated-scene test subsequently passed in
`artifacts/gama/marine_coexistence_01.json`. The captured RGB and its state/camera
provenance were audited on 2026-09-18; see [CAPTURE_VERIFICATION.md](CAPTURE_VERIFICATION.md)
for the positive results and the unresolved image-level instance-identity limit.
The fresh-stage results below are retained as the original milestone record.

## Passed

- Installed GAMA 2025.6.4 executed `trajectory.gaml` twice via `trajectory.xml`.
- Both runs produced identical 20-state trajectories, times 0–19 s, seed 184729.
- Canonical trajectory SHA-256:
  `61e3b8401d65548f336aee6f79bd7f355f3947fd81cdb660f3e2dbf5419ef143`.
- Independent circle-radius, tangent-heading and speed checks passed.
- Nine exchange/router unit tests passed using system Python.
- Five real-USD ownership/transform/isolation tests passed using Blender Python.
- Fresh Kit launched with the optional bridge. Twenty states were replayed through
  HTTP onto one explicitly owned bottlenose asset. Each composed USD world position
  and forward direction matched the external state (tolerance 1e-5 scene units /
  direction components).
- With updates withheld for two seconds, the actor held its last world pose.
- Explicit release succeeded. Before/after `/debug/scene/inspection` results were
  identical, including active camera, layers and reported scene prims.
- Unit tests additionally verified exact original root/session layer restoration,
  rejection of foreign IDs/tokens, capture-pause rejection, stage replacement,
  duplicate retry behaviour and refusal to overwrite an existing integration root.

Machine-readable evidence:

- `artifacts/gama/trajectory_validation.json`
- `artifacts/gama/live_replay_validation.json`

Raw GAMA outputs for this run:

- `/tmp/marlin-gama-fixture-final1/simulation-outputs0.xml`
- `/tmp/marlin-gama-fixture-final2/simulation-outputs0.xml`

The reports contain the validated state sequence; temporary raw output directories
may be removed by the operating system. Repeat commands are in `README.md`.

## Scope and limits

This was a **fresh Kit stage**, not the populated animated marine presentation.
Existing canonical render-service/app source, camera/GSD, assets, ocean and lighting
code were not edited. The optional extension is not in the default app dependencies.
Full populated-scene regressions and image/capture validation remain outstanding.

The transport is offline GAMA output → JSON conversion → HTTP replay, not live
WebSocket co-simulation. There is no biologically calibrated behaviour, physical
asset calibration, skeletal swimming animation or detectability claim. No render
was requested or certified. The test animal was released after verification; Kit
was left running with no owned fixture animal.

The initial fixture used GAML `mod`, which truncated fractional headings. This was
caught during output inspection and replaced with a floating-point wrap before
the final two runs and all reported evidence.
