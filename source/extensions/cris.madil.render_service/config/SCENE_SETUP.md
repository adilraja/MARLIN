# Rebuilding the complete scene

With Kit and the MARLIN extension running, use:

```bash
python3 /home/madil/kit-app-template/source/extensions/cris.madil.render_service/config/rebuild_scene.py --mode survey
```

Use `--mode demonstration` for the existing 11-animal swimming preview and animated ocean. The demonstration dolphin and six new assets remain static. Switching modes rebuilds the named instances and replaces their manual transforms. It does not start Kit or persist an in-memory USD stage.

Survey mode creates 18 named instances: Dolphin_001, eleven original gallery animals, and six survey assets. It uses the versioned fixed environment, stops the gallery and demonstration controllers, and positions composed bounds in separated slots. The porpoise receives a provisional -90 degree X correction. The overview camera is static, not an animal-following camera.

These are display placements, not calibrated physical dimensions or verified waterlines. Full bounds may include supports or inaccurate skeletal extents. The viewport capture shows blue water, but several bird assets contain support/display geometry or unsuitable poses. Those require individual asset inspection before scientific image generation. The viewport grid also remains visible and must be excluded from dataset captures.

The command uses existing HTTP endpoints plus `/debug/scene/inspection`, reports failures immediately, and captures the final viewport to `/tmp/marlin_viewport.png`. Rerunning overwrites this diagnostic image. Its JSON output includes placements and limitations. A failed run can leave a partially rebuilt scene; rerun after resolving the reported error.
