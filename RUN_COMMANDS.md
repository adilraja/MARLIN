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

## Stop Kit

Close the Kit window or press **Ctrl+C** in its launch terminal. The live scene
is not automatically preserved by Git; recreate it using steps 2–3 next time.
Avoid broad commands such as `pkill -f kit`, which also match unrelated services.
