# M1 baseline recovery and verification

The baseline is a frozen visual scene plus recorded configuration, saved
through existing MARLIN APIs. No recovery or restart was needed during M1.
Read [the limitations](#continuing-live-controllers) before using it as a
simulation restart.

## Files and original checkpoint

- `baseline/live_before/scene.usdc` is a verified byte-for-byte copy of
  `artifacts/scene_checkpoints/checkpoint_qippped8/scene.usdc`.
- Its SHA-256 is
  `21c08d1e80b5ccdb646e942896a4ffc557e1f32719cfdfceaa0a3d2ff0382ff1`.
- `baseline/live_before/checkpoint.json` records the original checkpoint ID,
  directory, time and settings; `checkpoint_metadata.json` is the original
  metadata copy.
- `baseline/live_after/` supplies a second checkpoint and after-audit status.
- `baseline_manifest.json` pins the source, asset dependencies and evidence.

The USD copies were reopened and inspected using Blender's USD-enabled Python.
This establishes readable frozen USD and evaluated rest-pose geometry. A
fresh Kit process/render replay was not executed during this read-only audit.

## Recheck the audit package

From `/home/madil/kit-app-template`:

```bash
/usr/bin/python3 -B experiments/gama_dolphin_behaviour_v1/qa/verify_package.py
```

This checks file hashes, source bytes at the recorded Git commit, asset
dependencies, Gate A status and the saved audit outcomes. It separately reports
current source differences from M1. A later authorised source change must not
rewrite this M1 seal to claim those new source bytes were the original baseline.

The read-only asset inventory can be repeated with the installed USD-enabled
interpreter, directing copied scripts/data into a new audit output location
if retaining the sealed result:

```text
/home/madil/opt/blender-5.0.1-linux-x64/5.0/python/bin/python3.11
```

`qa/audit_asset.py` reads the source asset, saved baseline and accepted water
scene. Its current output paths belong to the sealed audit; do not rerun it
in place after sealing. `qa/collect_baseline.py --name <new_name>` similarly
refuses an existing output directory; `--checkpoint` additionally invokes the
existing scene-checkpoint endpoint.

## Reopen frozen geometry when recovery is actually needed

Preserve any new unsaved work first. With the existing MARLIN HTTP service
available, stop only the controllers that would modify this restored stage:

```text
POST /scene/cetacean/swim/stop
POST /scene/cetaceans/gallery/swim/stop
POST /scene/camera/chase/stop
POST /scene/ocean/animation/stop
POST /debug/scene/checkpoint/checkpoint_qippped8/restore
```

Use empty JSON bodies where appropriate and require `ok: true` in each
response. Check the saved checkpoint bytes before restoration. If the original
artifact-store checkpoint is unavailable, the preserved scene/metadata copies
remain recovery inputs; the restore endpoint recognises IDs in its checkpoint
store rather than arbitrary file paths. Do not add a general path/command
execution endpoint to work around that restriction.

Verify `/debug/scene/inspection`, `/scene/ocean/material/preset/status` and the
saved camera/resolution/settings against `baseline/live_before/`. The recorded
water selection was **original**, the animal root was `[0,-20,0]`, and its
swimmer and gallery controllers were **stopped**. Do not use a default marine
setup call with swimming enabled as if it were this baseline.

## Continuing live controllers

The original scene had the ocean and chase camera running, with the dolphin
stationary. Their public configurations are saved in `ocean.json` and
`chase.json`. The ocean configuration was 16,000 units wide, resolution 128,
speed 0.7, choppiness 0.55 and target 15 updates/s. The recorded process had
been reconstructed by the retained previous restoration script:

```text
experiments/ocean_material_v1/diagnostics/m4_grid_material_audit/qa/restore_live_in_kit.py
```

That script uses the existing standard setup with `start_swimming=False` and
documents phase reconstruction. It is historical provenance, not a new command
executed by M1 or an instruction to overwrite its output directory.

Starting public ocean/chase controllers again reconstructs their dynamics;
it does not restore Python subscriptions, internal accumulators or the exact
old wave/renderer history. The checkpoint has no atomic controller-state
serialization. Keep the frozen geometry if exact saved wave positions are
required. Complete simulation-time/animation-phase snapshots are later M2/M5
work. No current GAMA ownership token or running actor needs restoration.

Runtime MDL definitions and absolute local asset references remain external
dependencies. Their identities and available local hashes are recorded; no
vendor cache was copied or byte-verified by this audit. This package is not a
self-contained Kit/GAMA installation.
