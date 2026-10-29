# M3 — Controlled absorption and underwater clarity

Start with `../../reports/M3_UNDERWATER_APPEARANCE.md`. The final engineering
candidate is `engineering_medium_v1.json`; it has not been applied to the
animated ocean. M4 owns that integration.

## Reconstruct one condition

With the existing MARLIN Kit app and render-service extension running:

```bash
curl -sS -X POST http://localhost:8011/scene/ocean/material/diagnostic/medium/capture \
  -H 'Content-Type: application/json' \
  -d '{"depth_m":0.75,"condition":"scattering_low","native_distance":100,"meters_per_scene_unit":0.01,"renderer":"PathTracing"}'
```

The bounded endpoint creates an isolated context, closed finite volume,
fixed target/background/lights and camera. It uses the existing viewport SDK,
requests native HdrColor explicitly, waits 64 rendered frames, saves full
512x384 PNG/EXR/float-array outputs, records the effective USD camera/product
settings and restores global settings on completion or error. A 768 MiB GPU
guard and busy lock remain active. Request values are a fixed allowlist, with
unknown fields rejected. No arbitrary code or output path is accepted.

Every successful directory contains `scene.usda`, `fixture.json`,
`metadata.json`, `effective_settings.json`, `aov_inventory.json`,
`hdr_buffer.json`, `warmup.png`, `rgb.png`, `hdr.exr` and `hdr.npz`.
The NPZ contains a float32 `rgba` array copied from the native RGBA16F buffer
while the SDK owns it. These are half-precision renderer samples, not a
measurement instrument or a recovered physical spectrum.

## Evidence and reconstruction

- `PLAN.md` records the initial controls, sweep, ROIs and tolerances.
- `CONTROLLED_RUN.md`, `PATH_TRACING_CHECK.md`, `UNCLAMPED_CHECK.md` and
  `FINAL_RUN.md` preserve the successive diagnoses before final acceptance.
- `qa/final/*_execution.json` identifies the 26 accepted captures by exact path,
  request, response and time; `*_gpu.json` contains one-second observations.
- `qa/measurements_final.json` and `qa/final_validation.json` contain the fixed-
  ROI measurements and numerical checks. `comparisons/` contains labelled HDR
  previews and plots; its display scale is fixed across every condition.
- Earlier `captures/`, initial `qa/*_execution.json`, `qa/controlled/`,
  `qa/pathtraced/` and `qa/unclamped/` are retained diagnostic attempts. Most
  were clamped and must not be substituted for final attenuation measurements.
  Two initial HDR requests failed; their PNG/scene outputs and responses remain.
- `qa/previous_evidence_integrity.json` checks all M1/M2 pinned evidence.
  Earlier milestone manifests and reports remain unchanged.

From the repository root, the declared suites can be reconstructed with
`/usr/bin/python3 -B .../qa/run_medium.py SUITE --pathtraced --final`, where
SUITE is `controls`, `absorption`, `scattering`, `units` or `exposure`.
The driver refuses to overwrite an existing execution log. Preserve the
evidence package and use a new experiment copy/output-log location for a
complete rerun. A single API request always creates a fresh capture directory.
Run `qa/analyse_medium.py --final`, then `qa/validate_final.py` and
`qa/plot_medium.py` to regenerate derived measurements/comparisons.

## Scope and rollback

No production ocean material, wave code, animal controller, target opacity or
coordinate convention was changed. The new capture path is optional; all old
capture calls retain their defaults. Closing the diagnostic destroys its
temporary context. Global settings and paused state are restored in `finally`.
The saved pre-work checkpoint and restoration responses are under `qa/`.
The live marine scene is restored separately after extension hot reload;
procedural animation phase is reconstructed, not serialized or claimed equal.

Dependencies remain the installed NVIDIA Kit/RTX/MDL runtime and the existing
Python packages. No runtime binaries, vendor source, assets or shader modules
were changed. M5 still owns repeat/save-reload qualification of the eventual
production capture configuration.
