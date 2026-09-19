# MARLIN — command reference

Run the launch command in one terminal. Send HTTP commands from a second
terminal after Kit finishes loading. Do not launch a second Kit instance.

## 1. Start Kit

```bash
cd /home/madil/kit-app-template/_build/linux-x86_64/release
./cris.madil.kit.sh --enable cris.madil.render_service
```

Check the API:

```bash
curl --fail -sS http://localhost:8011/openapi.json >/dev/null && echo "MARLIN API ready"
```

API documentation: <http://localhost:8011/docs>

### Preserve a visual checkpoint before restarting

With the scene loaded, save a frozen visual checkpoint without a new GPU render:

```bash
curl --fail-with-body -sS -X POST http://localhost:8011/debug/scene/checkpoint
```

Record the returned `checkpoint_id`. After a clean Kit launch, restore it with:

```bash
curl --fail-with-body -sS -X POST \
  http://localhost:8011/debug/scene/checkpoint/checkpoint_ID/restore
```

Replace `checkpoint_ID` with the complete returned ID. This restores the frozen
scene, camera and tracked renderer settings; it does **not** resume controllers
or recover their exact animation phase. External asset dependencies must remain
available. Use restoration in a fresh Kit session, not over running controllers.
For a swimming presentation, reload the gallery from original assets before
starting swimming (step 3); do not use frozen, already-deformed mesh points as
a new rest pose. The recoverable pre-restart checkpoint from 2026-09-15 is
`checkpoint_dtrp8kj1` under `artifacts/scene_checkpoints/`.

## 2. Single-dolphin demonstration

Creates the ocean, lighting and swimming dolphin, with a following camera.
Use this first when starting from a fresh Kit session. Fog is disabled here.

```bash
curl --fail-with-body -sS -X POST http://localhost:8011/scene/marine/setup \
  -H 'Content-Type: application/json' \
  -d '{"underwater_cue":false}'
```

## 3. All 11 gallery animals swimming

After step 2, stop its single-dolphin controller and following camera, load the
gallery, then start gallery swimming with its overview camera:

```bash
curl -sS -X POST http://localhost:8011/scene/cetacean/swim/stop
curl -sS -X POST http://localhost:8011/scene/camera/chase/stop

curl --fail-with-body -sS -X POST http://localhost:8011/scene/cetaceans/gallery \
  -H 'Content-Type: application/json' \
  -d '{"activate_viewport_camera":true}'

curl --fail-with-body -sS -X POST http://localhost:8011/scene/cetaceans/gallery/swim/start \
  -H 'Content-Type: application/json' \
  -d '{"activate_viewport_camera":true}'
```

If the gallery is already loaded, only the last command is needed.
These are presentation animations, not biologically calibrated behaviours.

## 4. Gentle waves + overcast lighting (current milestone)

Apply to a running marine scene. Keeps animal and camera controls unchanged:

```bash
curl --fail-with-body -sS -X POST http://localhost:8011/scene/environment/gentle-overcast
```

Restore the water and lighting saved before applying it:

```bash
curl --fail-with-body -sS -X POST http://localhost:8011/scene/environment/gentle-overcast/restore
```

Run the apply command again to return to gentle overcast. Restore requires the
same stage and extension session; restarting Kit or reloading the extension
loses the saved environment. Restoration restarts ocean phase, not animal motion.

## 5. Other environment presets

These apply presets; they do not restore a saved snapshot. If gentle overcast
is active, use its restore command first to finish that comparison.

**Demonstration lighting and gentle water:**

```bash
curl --fail-with-body -sS -X POST http://localhost:8011/scene/demonstration/environment
```

This older demonstration preset enables the underwater fog cue. Disable it
for an unobscured above-water view if needed:

```bash
curl --fail-with-body -sS -X POST http://localhost:8011/scene/ocean/underwater-cue/disable
```

**Legacy flat-water survey appearance (no waves):**

```bash
curl --fail-with-body -sS -X POST http://localhost:8011/scene/survey/environment
```

This is the older experimental flat-water preset, not the gentle-wave milestone
and not a validated data-generation configuration. It does not select a survey
camera or calibrate animal placement.

## 6. Pause, resume and status

Stop gallery swimming (does not stop the ocean):

```bash
curl -sS -X POST http://localhost:8011/scene/cetaceans/gallery/swim/stop
```

Restart gallery swimming without changing the active camera:

```bash
curl --fail-with-body -sS -X POST http://localhost:8011/scene/cetaceans/gallery/swim/start \
  -H 'Content-Type: application/json' \
  -d '{"activate_viewport_camera":false}'
```

This restarts the preview; it is not an exact pause/resume of animation phase.

```bash
curl -sS http://localhost:8011/scene/cetaceans/gallery/swim/status | python3 -m json.tool
curl -sS http://localhost:8011/scene/ocean/animation/status | python3 -m json.tool
```

## 7. Capture the current viewport

```bash
curl --fail-with-body -sS -X POST http://localhost:8011/debug/viewport/capture
```

The response gives the output path, normally `/tmp/marlin_viewport.png`.
Each capture overwrites that file. After changing cameras or lighting, wait for
the viewport to settle and capture twice if the first image shows an older frame.

## HiDef camera geometry validation (oblique, not Sony)

These commands capture nine metric targets in a separate Kit scene. They do
not replace the marine scene or activate a nadir camera. Preview output is
1644 × 548; geometry retains the native 6576 × 2192 field of view.

```bash
curl --fail-with-body -sS -X POST http://localhost:8011/scene/camera/hidef/capture \
  -H 'Content-Type: application/json' -d '{"roll_deg":7.77,"downsample":4}'
curl --fail-with-body -sS -X POST http://localhost:8011/scene/camera/hidef/capture \
  -H 'Content-Type: application/json' -d '{"roll_deg":23.17,"downsample":4}'
```

Responses identify the scene, image and metadata output directory. Do not label
preview PNGs as nominal 2 cm/px. Native output requires `downsample:1` and
`allow_full_resolution:true`, plus adequate GPU headroom; it remains unverified
on this GPU. Full assumptions/results are in
`source/extensions/cris.madil.render_service/config/HIDEF_IMPLEMENTATION.md`.

## HiDef marine snapshot + directional GSD maps

With the marine scene loaded:

```bash
cd /home/madil/kit-app-template
python3 tools/capture_hidef_marine.py
```

This briefly pauses MARLIN updates and uses the existing viewport to render a
frozen scene, then restores the live stage, overview camera, selection, display
options, resolution and recorded render settings. It does not open a second RTX
renderer. Output is **1644 × 548**, not native 6576 × 2192.

The response gives a `capture_id` and paths to `rgb.png`, `scene.usdc`,
`metadata.json`, `directional_gsd.npz` and diagnostic map PNGs.

Re-render an existing snapshot (replace the ID with your own):

```bash
python3 tools/capture_hidef_marine.py --replay oblique_6h25133y
```

The saved scene is used even if the live animals have moved. Replay refuses
changed tracked renderer settings or changed hashed texture files. RTX pixels
need not be bit-for-bit identical. A low-memory refusal means no render was
attempted; do not repeatedly retry or lower the safety check.

Defaults: roll 7.77°, pitch 30° **from nadir**, 150 mm, 549 m above Y=0,
principal ray aimed at X=-3 m, Z=0 m. The 3 m framing shift keeps the default
footprint inside the 160 m demonstration ocean; it does not change GSD or tune
camera intrinsics. Other framing can be requested with `--target-x`/`--target-z`.
`--roll 23.17` is supported but may extend beyond this finite ocean mesh.

These maps describe the **flat reference sea plane**, not the wavy surface,
submerged animals or biological detectability. See [HIDEF_CAPTURE.md](HIDEF_CAPTURE.md)
for assumptions, verification and the artifact layout.

## Sony ILX-LR1 provisional camera capture

With the marine scene loaded:

```bash
python3 tools/capture_sony_marine.py
# Optional framing shift in metres, without moving animals:
python3 tools/capture_sony_marine.py --target-z -30
# Replace the placeholder with the returned ID:
python3 tools/capture_sony_marine.py --replay sony_CAPTURE_ID
```

This uses the same guarded snapshot/restoration pipeline as HiDef. Sony is a
separate **assumed-nadir** 85 mm / 150 m profile. Output is **1188 × 792** at
**5.30303 cm/preview pixel**, retaining the nominal 63 × 42 m footprint.
Native geometry predicts 0.66288 cm/px; native rendering is deferred.
The trial image mode, camera mounting and calibration remain unresolved.
See [SONY_CAMERA.md](SONY_CAMERA.md) for provenance and limitations.

Sony image/GSD diagnostic: nine known targets on a frozen copy, with the live
marine viewport restored afterward. This is not a wildlife-data capture:

```bash
curl -s -X POST http://localhost:8011/scene/camera/sony/marine/capture \
  -H 'Content-Type: application/json' -d '{"projection_probe":true}'
# NumPy/Pillow required; substitute the returned directory:
python3 tools/capture_calibration_target.py --measure-existing CAPTURE_DIRECTORY
python3 tools/verify_capture_projection.py CAPTURE_DIRECTORY
```

## Experimental native HiDef capture

With the marine scene loaded, use memory-bounded native tiles (not preview upscaling):

```bash
python3 tools/capture_hidef_marine.py --native --roll 7.7675 --projection-probe
python3 tools/capture_hidef_marine.py --native --roll 7.7675
```

Native targets passed; marine output must pass overlap checks before acceptance.
See [NATIVE_CAPTURE.md](NATIVE_CAPTURE.md) for results, limitations and verification.

To diagnose selected overlaps from an existing **native HiDef** capture:

```bash
curl -sS --max-time 650 -X POST \
  http://localhost:8011/scene/camera/hidef/marine/oblique_CAPTURE_ID/tile-diagnostic \
  -H 'Content-Type: application/json' -d '{"mode":"baseline"}'
```

Replace `oblique_CAPTURE_ID` with the saved capture ID. Fixed modes are
`baseline`, `guard64`, `rendered_frames`, `pt_denoised`, `pt_raw`, and
`pt_raw_8192`.
PT modes temporarily use Interactive path tracing (8 samples per iteration,
1024 total requested) and wait for delivered frames; saved live settings are
restored afterwards. Do not run below the 768 MiB free-GPU safety threshold.
The experimental `pt_raw_8192` mode instead requests 64 samples per iteration
and 8192 total, without denoising. It timed out on this host in the latest test;
it is not an accepted capture preset. Frame waits are not measured sample counts.
These capture only seven samples, including a repeat: **not a complete image or
an accepted dataset**. A failing overlap deliberately returns `ok:false`.

With NumPy/Pillow, compare pristine-source diagnostics on identical pixel regions:

```bash
python3 tools/analyse_tile_diagnostics.py BASELINE_DIRECTORY OTHER_DIRECTORY \
  --output artifacts/hidef_marine/tile_diagnostic_comparison.json
```

## GAMA integration: optional, isolated test animal

For the live step-controlled coordinator (two seeded 20-step trials verified),
see [live GAMA commands and server-binding warning](integrations/gama/LIVE_COMMUNICATION.md).

The normal launch remains standalone. To enable the bridge, use this launch only
when Kit is stopped; do not discard a live scene or launch a second instance:

```bash
cd /home/madil/kit-app-template/_build/linux-x86_64/release
./cris.madil.kit.sh --enable cris.madil.render_service \
  --ext-folder /home/madil/kit-app-template/source/extensions \
  --enable cris.madil.gama_bridge
```

Load the standard marine scene and eleven swimmers using sections 2–3 above.
Then replay the previously verified GAMA trajectory, capture with the existing
HiDef pipeline, and release only the isolated test animal:

```bash
cd /home/madil/kit-app-template
python3 -B tools/verify_gama_marine.py \
  --trajectory artifacts/gama/trajectory_validation.json \
  --output /tmp/gama-marine-verification-new.json
```

Choose an unused output filename. The JSON result includes the capture directory.
This temporarily pauses updates for MARLIN's standard snapshot capture and restores
the overview. It does not replace existing swimmers. GAMA drives a rigid test actor;
this is not biological calibration or a skeletal swimming demonstration.

### Audit the saved GAMA capture without running Kit

New isolated actors use the provisional 2.6 m `coastal_candidate_v1` profile.
See [size/waterline evidence and limits](integrations/gama/BOTTLENOSE_CALIBRATION.md).
The normal replay command above acquires this candidate and releases it afterwards.
To acquire the old preview size instead (only when no isolated actor is owned):

```bash
curl --fail-with-body -sS -X POST http://localhost:8011/integration/gama/actor/acquire \
  -H 'Content-Type: application/json' -d '{"profile":"legacy_preview"}'
```

Retain its returned `ownership_token`; release before running the replay script:

```bash
curl --fail-with-body -sS -X POST http://localhost:8011/integration/gama/actor/release \
  -H 'Content-Type: application/json' -d '{"ownership_token":"TOKEN_FROM_ACQUIRE"}'
```

Regenerate the non-destructive landmark measurements and diagram without Kit:

```bash
cd /home/madil/kit-app-template
/home/madil/opt/blender-5.0.1-linux-x64/5.0/python/bin/python3.11 -B tools/inspect_gama_bottlenose.py
/home/madil/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B tools/plot_gama_bottlenose.py
```

The verified size-candidate capture is `artifacts/hidef_marine/oblique_m7hloime`;
substitute it below to audit that image rather than the historical legacy preview.

This command uses the available NumPy/Pillow runtime and Blender's USD Python.
It reads the original image/snapshot/metadata without changing them. It writes an
audit report, pixel diagnostic and `projection_validation.json` derived report:

```bash
cd /home/madil/kit-app-template
/home/madil/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B \
  tools/verify_gama_capture.py artifacts/hidef_marine/oblique_2h82kfx4 \
  --output artifacts/gama/capture_audit_2h82kfx4
```

For a new capture, substitute its directory and a separate audit output directory.
Exit status 0 means geometry/provenance checks passed, **not** instance visibility
certification. Review the diagnostic and limitations in `verification.json`.
The original audited actor is only about 4.6 × 2.1 projected pixels.
See [GAMA capture verification](integrations/gama/CAPTURE_VERIFICATION.md) and
[GAMA fixture commands](integrations/gama/README.md) for full details.

CPU regression checks (do not contact Kit):

```bash
python3 -B tools/test_gama_exchange.py
/home/madil/opt/blender-5.0.1-linux-x64/5.0/python/bin/python3.11 -B tools/test_gama_actor.py
```

Return to standalone by releasing the test actor (the replay script does this
automatically) and omitting `--enable cris.madil.gama_bridge` on the next launch.
Disabling the bridge also removes its own private actor layer. Do not disable or
reload extensions while capture is running.

### GAMA actor-on/off pixel-contribution check

With MARLIN and the optional bridge running, replay private copies of a saved GAMA
HiDef preview. This performs four renders (on/off/off/on), preserves the source
capture, and restores the live viewport after each. Current renderer settings must
match the saved capture; insufficient GPU headroom fails closed.

```bash
curl --fail-with-body -sS --max-time 600 -X POST \
  http://localhost:8011/integration/gama/capture/counterfactual \
  -H 'Content-Type: application/json' \
  -d '{"capture_id":"oblique_2h82kfx4"}'
```

Check JSON `ok`, then analyse the returned directory. To inspect the verified run:

```bash
cd /home/madil/kit-app-template
/home/madil/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B \
  tools/analyse_gama_counterfactual.py artifacts/gama/counterfactual_i9hp7lh1
```

The analysis is offline by default. `--observe-live http://localhost:8011` explicitly
saves a separate current scene audit if a post-capture resumption check is needed.
Exit status 0 means the controlled comparison was valid; read
`pixel_contribution_observed` in `analysis.json` for the image result. It does not
certify biological recognition or provide an instance segmentation mask.
See [counterfactual results](integrations/gama/COUNTERFACTUAL_VERIFICATION.md).

## Stop Kit

### Experimental two-tile SDK diagnostic (not certified)

For a pipeline smoke test, replace `sdk_pair` below with `sdk_smoke` (one tile,
16 requested samples), `sdk_low_repeat` (three repeats at 16), or `sdk_single`
(three repeats at 1024). Low-sample modes do not validate image quality.
After capture, independently check saved PNG dimensions and recorded ray matrices:

```bash
python3 tools/verify_tile_diagnostic.py artifacts/hidef_marine/CAPTURE_ID
```

This requires NumPy and Pillow. It writes `tile_geometry_validation.json` and
does not certify full-image alignment or independently measure GPU sample count.

Enable the fixed NVIDIA capture dependencies explicitly; Kit may download them:

```bash
curl -sS -X POST http://localhost:8011/debug/capture-capabilities/enable
curl -sS -X POST \
  http://localhost:8011/scene/camera/hidef/marine/oblique_htk8y1za/tile-diagnostic \
  -H 'Content-Type: application/json' -d '{"mode":"sdk_pair"}'
```

Requires the saved snapshot and matching renderer settings. Tests tiles 3 and 4
twice, rejects size changes, and retains the 768 MiB memory guard. This path is
experimental: SDK completion does not independently verify GPU sample count.
See NATIVE_CAPTURE.md for the observed size-reset failure and unverified fix.

### Shut down

Close the Kit window or press **Ctrl+C** in its launch terminal. The live scene
is not automatically preserved by Git; recreate it using steps 2–3 next time.
Avoid broad commands such as `pkill -f kit`, which also match unrelated services.

Kit selected fallback port 8097 during recovery. May I use that port to restore the checkpoint?
curl -sS --max-time 120 -X POST http://localhost:8097/debug/scene/checkpoint/checkpoint_r7rmq2ii/restore
