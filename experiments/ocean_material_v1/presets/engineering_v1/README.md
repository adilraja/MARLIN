# MARLIN engineering water preset v1

This package freezes the existing `engineering_v1` parameters and exported material, with the closed-medium requirements and tested capture configuration. The parameter JSON is preserved byte for byte from canonical source; its older status text is provenance. `qualification.json` describes the newer M5/M6 checks. Human acceptance is recorded separately in `../../diagnostics/m6/review_state.json`.

**Supported:** the tested above-water camera, original and engineering water comparisons, 512 × 384 PathTracing native HDR/EXR plus a deterministic display conversion, and fresh-process reload/rollback. **Unqualified:** inside-water camera attenuation, useful native LDR PNG under this exposure, native HiDef/Sony output, and real-world optical/biological/survey validity. The initial M6 in-process stage switch exited before completing; fresh-process reload is the validated path.

## Contents and dependencies

- `parameters.json`: original measured parameter/configuration source.
- `material.usda`: exported `/World/Looks/OceanWaterEngineeringV1` with native `OmniSurface.mdl` binding; no water textures.
- `geometry_requirements.json`: unchanged top surface, closed sides/bottom, 20 m depth, Y-up and centimetre units.
- `capture_settings.json`: actual camera/product/global controls, projection, runtime and fixed display mappings.
- `demonstration_scene.usdc`: frozen engineering intersecting-animal scene used in the accepted fresh-process replay. It retains repository-local animal texture dependencies; it is not a standalone redistributable asset bundle.
- `dependency_manifest.json`, `source_snapshot/`, `ASSET_LICENSE.txt`: source pins, texture/model hashes and provenance. Native vendor runtime files are referenced by name/version and were not copied or inspected.

The demonstration uses "Model 61A - Bottlenose Dolphin" by DigitalLife3D, licensed under CC-BY-NC-4.0. The original source attribution, links and terms are retained in `ASSET_LICENSE.txt`; no source model or licence was removed.

## Apply and roll back through the existing service

Run the normal MARLIN application and checkpoint any current work first:

```sh
curl -sS -X POST http://localhost:8011/debug/scene/checkpoint
curl -sS -X POST http://localhost:8011/scene/marine/setup -H 'Content-Type: application/json' -d '{"start_swimming":false}'
curl -sS -X POST http://localhost:8011/scene/ocean/material/preset -H 'Content-Type: application/json' -d '{"selection":"engineering_v1","configure_renderer":false}'
```

The last call changes binding/medium geometry only; it does not claim that an arbitrary viewport/camera has the tested capture settings. The exact capture configuration is in `capture_settings.json` and in the frozen scene. Use the original selection before changing ocean geometry or units.

```sh
curl -sS -X POST http://localhost:8011/scene/ocean/material/preset -H 'Content-Type: application/json' -d '{"selection":"original"}'
curl -sS -X POST http://localhost:8011/scene/marine/setup -H 'Content-Type: application/json' -d '{"start_swimming":false}'
```

The second rollback command reconstructs the standard scene and controller phase; it does not restore an exact animation clock. Restore an existing checkpoint through `/debug/scene/checkpoint/<checkpoint_id>/restore` to recover its frozen visual state instead. Checkpoints do not restart procedural controllers.

## Reproduce a fresh-process capture

From the repository root, verify the sealed package first. Checkpoint and close any running Kit application before starting the replay; the launcher refuses a duplicate and requires 2,048 MiB free. Use an unused two-digit identifier, such as 02, to preserve all earlier outputs.

```sh
python3 -B experiments/ocean_material_v1/diagnostics/m6/qa/verify_package.py
python3 -B experiments/ocean_material_v1/diagnostics/m6/qa/launch_reload.py --attempt 02
python3 -B experiments/ocean_material_v1/diagnostics/m6/qa/convert_hdr.py --input experiments/ocean_material_v1/diagnostics/m6/runs/reload_process02/reload_intersecting/hdr.npz --output experiments/ocean_material_v1/diagnostics/m6/runs/reload_process02/reload_intersecting/hdr_display.png
```

This uses the saved selected scene and the same native SDK route, then tests original-material rollback. The capture code used for accepted process01 is archived beside the audit; the current wrapper adds new-output selection and graceful termination after saved results if a posted quit does not exit promptly. No material/camera/sampling retuning is required in this repository layout. On another machine, provide the listed local assets and remap repository paths; do not assume the frozen scene is self-contained.

To return to the standard live app after replay, launch the documented existing application, restore the checkpoint saved before closing it and reconstruct controllers as needed. Do not run a second renderer concurrently.
