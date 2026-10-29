# Reproduce the M2 isolated water diagnostic

Read `../../reports/M2_TRANSMISSION_REFRACTION.md` for results and limitations.
The selected preset is `selected_preset.json`. The production marine material
was not changed. Keep earlier failed and unstable captures intact.

With the existing MARLIN application and render-service extension running:

```bash
curl -X POST http://localhost:8011/scene/ocean/material/diagnostic/capture \
  -H 'Content-Type: application/json' -d '{}'
```

The default request selects the tested oblique water fixture, positive native
depth 100 and a completed 64-rendered-frame settling wait. The response identifies
a fresh output folder containing `scene.usda`, `fixture.json`, `metadata.json`,
`warmup.png` and `rgb.png`. Wait for a complete PNG write before reading it.

For the full control set, request each combination of `view` (`nadir`, `oblique`)
and `condition` (`dry`, `matched`, `water`) with `probe:"positive_depth"` and
`settled:true`. The fixed endpoint accepts no arbitrary script, output path or
renderer-setting payload. It uses a separate context, temporarily disables the
height-fog cue and restores global settings/default stage after capture.

The capture helper checks available memory before the isolated render. Do not
disable its 768 MiB guard. Capture errors and unsupported capabilities are
failures, not equivalent transparent fallbacks. The positive-depth value is
native to the shader; physical attenuation-distance conversion is unverified.

The three `qa/run_*.py` scripts preserve their declared output-log names and
refuse to overwrite prior executions. Use a new explicitly declared execution
log for another run; do not delete the retained records to rerun in place.
`run_captures.py` explicitly reconstructs the original null-depth/update-settled
conditions; `run_acceptance.py` reconstructs the failed positive-depth/update-only
set; `run_settled.py` reconstructs the passing positive-depth/rendered-frame set.

Offline analysis and mathematical checks, from the repository root:

```bash
python3 -B experiments/ocean_material_v1/diagnostics/m2/qa/analyse_refraction.py
python3 -B -m unittest discover -s experiments/ocean_material_v1/diagnostics/m2/qa -p test_refraction_analysis.py -v
```

The analysis retains the fixed measurement method and reports failed earlier
sets alongside the settled result. Per-run raw metadata was not rewritten to
turn earlier failures into passes. The result requires the recorded renderer,
geometry, shader inputs, camera and settling procedure; it is not field validation.
