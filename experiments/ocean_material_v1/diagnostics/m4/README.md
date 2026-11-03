# M4 — Animated ocean integration (milestone remains open)

The opt-in enclosure/material integration passed the declared above-water
checks. **Camera-inside attenuation was not demonstrated**, so full milestone
closure is not claimed. Start with `../../reports/M4_ANIMATED_OCEAN_INTEGRATION.md`.

## Select or restore

With the existing MARLIN marine scene running:

```bash
curl -sS -X POST http://localhost:8011/scene/ocean/material/preset \
  -H 'Content-Type: application/json' \
  -d '{"selection":"engineering_v1","bottom_depth_m":20,"configure_renderer":false}'
curl -sS http://localhost:8011/scene/ocean/material/preset/status
curl -sS -X POST http://localhost:8011/scene/ocean/material/preset \
  -H 'Content-Type: application/json' -d '{"selection":"original"}'
```

The default selects binding/geometry without changing the live renderer.
The tested optical configuration uses PathTracing, fog and firefly filtering
off, camera auto exposure off, 512x384 images and 64 rendered-frame settling.
`configure_renderer:true` applies the native controls only when the existing
viewport is already at 512x384 or smaller, saves their previous values and
restores them with the original preset. It does not silently resize the view.
Normal scene setup preserves an existing selection. Incompatible material
replacement or ocean reconfiguration requires explicit rollback first.

The runtime configuration is in
`source/extensions/cris.madil.render_service/config/ocean_medium_engineering_v1.json`.
The source M3 preset remains immutable. Serialized ownership metadata lives on
`/World/Ocean` and contains the original binding, geometry conventions and
renderer-property snapshots. No animal property or material is part of this
preset. The model remains an engineering medium, not calibrated seawater.

## Bounded diagnostics

For the complete scripted batch, start the standard scene with both swimming
and chase disabled so the diagnostic camera/animal pose remain fixed:

```bash
curl -sS -X POST http://localhost:8011/scene/marine/setup \
  -H 'Content-Type: application/json' \
  -d '{"start_swimming":false,"start_chase_camera":false}'
curl -sS -X POST http://localhost:8011/scene/ocean/material/preset/diagnostic/batch-preview \
  -H 'Content-Type: application/json' -d '{"action":"begin"}'
curl -sS -X POST http://localhost:8011/scene/ocean/material/preset/diagnostic/capture \
  -H 'Content-Type: application/json' \
  -d '{"selection":"engineering_v1","view":"oblique","phase_seconds":1}'
curl -sS -X POST http://localhost:8011/scene/ocean/material/preset/diagnostic/batch-preview \
  -H 'Content-Type: application/json' -d '{"action":"end"}'
```

Always end the preview session after a batch, including a failed batch. It
temporarily holds the same existing viewport at the declared diagnostic
resolution and restores the prior resolution/mode/settings. Each capture
restores its own overlay, root specs, camera, geometry, wave clock and guide
settings. A 768 MiB pre-request guard remains active. No second renderer or
arbitrary code/file/output-path API was introduced. The live-advance probe
rejects active chase/swim controllers; ordinary frozen captures pause and
restore controllers through the existing capture gate.

The fixed regression route is
`POST /scene/ocean/material/preset/diagnostic/regression`. It requires the
original selection and an active existing ocean. It compares five wave phases
and the actual existing swimmer update in normal and boundary cases; it
restores controller state and the animal's root transforms afterwards.

## Evidence

- `qa/capture_execution.json`: twelve successful main-batch captures.
- `qa/outer_edge_response.json`: an additional boundary-straddling capture.
- `qa/integration_validation.json`: data/geometry/transaction checks, target
  observations and the explicitly unqualified camera-inside case.
- `qa/effective_camera_poses.json`: camera poses derived from actual capture
  matrices, including the exit and boundary overrides. Inherited planar-target
  predictions in those capture records describe the nominal setup only.
- `qa/responsive_regression_response.json` and its referenced `result.json`:
  five-phase and deterministic controller equivalence results.
- `qa/accepted_capture_source_record.json` and `qa/capture_sources/`: exact
  source for the twelve main captures. Subsequent final changes added a
  non-rendering live-advance precondition, qualification metadata and the
  additional `outer_edge` view; the optical parameters/wave equations remained
  unchanged.
- `comparisons/frozen_original_candidate.png`, `animated_phase_sequence.png`,
  `inside_exit_edge_probes.png` and `outer_edge_hdr_log.png`: labelled fixed-
  scale HDR previews. Native display PNGs saturated; no coefficients were
  inferred from them. Preview transforms are not measured radiance calibration.
- `qa/capture_execution_attempt01.json`, `attempt02` and individual probe
  responses: preserved guard blocks, failed probes and earlier successful
  images. Their results are not silently substituted for the main batch.
- `qa/initial_request_timeouts.json`, `REGRESSION_AMENDMENT.md` and
  `PREVIEW_BUDGET_AMENDMENT.md`: execution/resource diagnoses.
- `qa/kit_restart_01/`: one checkpointed, graceful app restart, with sealed
  log snapshots; active logs are ignored because they may continue growing.

The Python driver `qa/run_captures.py` refuses to overwrite an existing log.
Single API requests always make a new output directory. Derived validation
and comparison images can be regenerated with
`/usr/bin/python3 -B experiments/ocean_material_v1/diagnostics/m4/qa/analyse_integration.py`.

The remaining issue is the installed renderer's initial medium state for a
camera already inside water. The neutral HDR target in that probe was not
accepted as evidence of underwater attenuation. No artificial camera shell,
object hiding, substitute height fog or unverified setting was added to
manufacture a pass. M5/M6 production capture and animal demonstration remain
separate work.

To verify the sealed evidence and final source pins without rendering:

```bash
/usr/bin/python3 -B experiments/ocean_material_v1/diagnostics/m4/qa/verify_package.py
```
