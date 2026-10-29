# Restore the M1 material and capture configuration

No production file or candidate material was changed during M1. The accepted
baseline is `../baseline/frozen_02/`; never overwrite its scene, PNGs or metadata.
The original starter stage also remains checkpointed in `qa/startup_checkpoint.json`.

## Frozen appearance-baseline restoration

1. Read `baseline/frozen_02/checkpoint.json` from the experiment root. Confirm
   `scene_sha256` matches `baseline/frozen_02/scene.usdc`. Its `directory` identifies
   the checkpoint stored by the existing MARLIN service under `artifacts/scene_checkpoints/`.
2. Preserve any scene that now matters using `POST /debug/scene/checkpoint` before
   replacing it. Do not assume the later user's live scene can be discarded.
3. Stop live chase and ocean controllers using the existing endpoints
   `POST /scene/camera/chase/stop` and `POST /scene/ocean/animation/stop`.
   Stop swimming too if a later session has enabled it. The checkpoint does not
   serialize controllers or their phases.
4. Use `POST /debug/scene/checkpoint/{checkpoint_id}/restore` with the **ID from the
   saved checkpoint metadata**, not an invented path or identifier. This attaches
   a private copy of the saved sampled scene and restores its camera, viewport
   size and recorded renderer settings. The endpoint checks the stored scene hash.
5. Inspect `/scene/ocean/material/status`, `/debug/render-settings` and
   `/debug/scene/inspection`. Compare with retained JSON and the full settings
   record. The restored camera is `/World/Cameras/DolphinChaseCamera`, resolution
   1280 × 720. This restores an appearance baseline, not a validated metric projection.

Both checkpoint restores passed in the M1 execution. Water/material settings
matched. The later complete renderer comparison covered 73 saved settings and
had no differences using the existing `same_settings` tolerance helper.

The frozen USD retains external USD/textures and the installed MDL dependency;
it is not a standalone vendor-runtime bundle. Keep the original assets and tested
runtime available. A copy of a scene file alone does not restore global renderer
settings or controller subscriptions.

## Reconstruct the baseline's live demonstration

`POST /scene/marine/setup` with JSON `{"start_swimming": false}` reconstructs the
same existing setup parameters used here, starting the standard ocean animation
and chase camera. It resets procedural history; it does **not** reproduce the
saved wave/camera phase. This restoration was executed after the frozen tests;
its response is in `qa/restore_live_marine_setup.json`.

Do not replay setup over an unrelated live scene without preserving that scene.
No system reboot is needed. No historical experiment output should be changed.

## Reproduction helpers and retained failures

`qa/audit_in_kit.py` is the fixed local diagnostic used at Kit startup. Its first
attempt refused the default starter stage. Its corrected attempt exported the
material and scene, then failed the existing strict projection-conformance check.
Do not treat it as a successful complete capture recipe.

`qa/http_baseline.py` completed the existing-API appearance-baseline path. It is
intentionally pinned to an output folder and refuses to overwrite prior evidence.
For a new run, create a new declared run folder and preserve the previous one.
Follow `ACCEPTANCE_PLAN_V2.md`; keep the 768 MiB pre-capture guard and disk-commit
verification. Do not claim the original 512 × 384 projection test passed.
