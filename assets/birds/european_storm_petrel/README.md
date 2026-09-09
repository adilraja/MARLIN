# European storm petrel — skeletal validation asset

This milestone creates a conservative research pose rig, not a biologically validated flight model. The original scan and existing MARLIN static assets remain unchanged. No ocean or cetacean source code was modified.

## Inputs and inspection

Original: `assets/avians/storm_petrel/source/scene.gltf` (glTF 2.0, associated scene.bin and three texture maps). A source copy and licence are included here in `source/`. The licence identifies a model titled Storm petrel from Virtual Museums of Małopolska, CC0-1.0. The requested species identity comes from the task brief; this rig does not independently establish taxonomy.

The rig input is the earlier support-cleaned v1 Blender copy. That copy has 156,856 vertices, compared with 169,810 in the original; the difference predates this rig and concerns display-base cleanup. Original dimensions include the base. All reported dimensions are native imported units, not calibrated animal sizes.

Original inspection:

- Six mesh objects: Object_2 through Object_7; no armature.
- 169,810 vertices; 193,628 polygons, all triangles.
- Combined transformed vertex dimensions: X 54.036100, Y 34.625000, Z 28.208985.
- The main body, both wings and tail share a connected scan surface across the glTF mesh chunks. Five components remain after analysis-only positional welding (rounding coordinates to five decimals); the other four small components occupy the eye region. No topology was welded in the asset.
- Object_4, Object_5 and Object_6 span wings/body/tail; objects are not anatomical partitions. Whole-object wing weighting would be incorrect.
- Texture maps: ptak_baseColor.png, ptak_metallicRoughness.png, ptak_normal.png.
- Detailed per-object local bounds/dimensions, triangle counts, hierarchy, transforms, materials and actual Blender exporter API are in `working/inspection/inspection.json`. Three reference views are beside it.

## Geometry and coordinate convention

Blender world up is +Z. The scan is turned slightly relative to the axes. Approximate body forward is normalized (11.5, -21, 0); anatomical left is normalized (21, 11.5, 0). Body center used for the rig is (-1, -15, 8). These are inspected geometric rig landmarks, not physical anatomical measurements.

Shoulder locations use equal offsets from the centerline. Mid/tip landmarks follow median positions in actual left/right wing bands; the scan's asymmetry is retained. Parent transforms are baked into vertex coordinates while preserving world-space positions. There is no remeshing, smoothing, rest-pose reshaping or scale normalization.

## Rig and skinning

Eleven stable bones: root → body; body → neck → head; body → wing_L_shoulder → wing_L_mid → wing_L_tip; mirrored R chain; body → tail.

Explicit geometric weights replace automatic heat weighting. Shoulder influence blends across lateral distance 4–8; mid/tip influence blends further out. Vertices on one side have no weights for the opposite wing. Central torso vertices remain rigid under wing controls. Neck/head and tail weights follow the inspected longitudinal axis. Lower leg geometry stays with the body.

Individual 8-degree bone tests cover both shoulders, both mids/tips, body, neck, head and tail. Every tested bone moves geometry. Wing tests leave the opposite wing and central torso unchanged to floating-point tolerance. Maximum rest-coordinate difference from the cleaned input is 0.000005722 native units. Maximum weight-sum error is 2.22e-16. Reports: `working/rig_report.json`.

## Poses and animation

Named Blender actions and separate USD skeletal snapshots: glide, wings_up, wings_down, bank_left, bank_right. Conservative test rotations are recorded exactly in the rig report. Bank poses include root bank and modest shoulder lift. They demonstrate control; no claim is made about natural flight kinematics.

`wingbeat_test` runs frames 1–49 at 24 fps: glide → wings_up → glide → wings_down → glide. First/last samples match exactly. Two seconds is arbitrary test timing. The main .blend opens with this action active at frame 1; static named actions are retained with fake users.

Main editable file: `working/european_storm_petrel_rigged.blend`.
Main animated USD: `usd/european_storm_petrel_rigged.usd`.
Pose USDs are skeletal snapshots with their posed bind/rest configuration; they are not separate animation clips to bind onto the main skeleton.

## Export and verification

The installed Blender 5.0.1 USD RNA API was inspected before choosing export_animation, export_armatures, export_materials and export_textures_mode. The export contains SkelRoot, one 11-joint Skeleton, six skinned meshes, materials, three resolving textures and UsdSkelAnimation. USD upAxis remains Z and exporter metersPerUnit is 1; that metadata is NOT a claim that the model's native dimensions are biologically correct metres.

`tools/validate_petrel_usd.py` opens all exports and performs CPU USD skinning at frames 1, 13, 25, 37, 49. It verifies bindings, finite points, unchanged rest extents/vertex count, nonzero wing movement and loop closure. Named pose exports differ from glide. Meshes are compared by sorted paths because traversal order differs across exports.

`working/usd_validation.json` records the checks. Animated glide matches the pose snapshot within 0.000016 native units. First/last animation point arrays match exactly.

Kit successfully spawned `/World/Cetaceans/PetrelRigTest` through the existing reference-spawn API. Runtime rig inspection found all joints, skin bindings and animation. `working/kit_animation.png` and `working/kit_animation_second.png` show different wing positions under the existing Kit timeline.

## Reproduce and preview

From the repository root:

```bash
/home/madil/opt/blender-5.0.1-linux-x64/blender --background --factory-startup --python-exit-code 1 --python tools/inspect_petrel.py
/home/madil/opt/blender-5.0.1-linux-x64/blender --background --factory-startup --python-exit-code 1 --python tools/rig_petrel.py
/home/madil/opt/blender-5.0.1-linux-x64/blender --background --factory-startup --python-exit-code 1 --python tools/validate_petrel_usd.py
python3 tools/preview_petrel_rig.py --pose animation
python3 tools/preview_petrel_rig.py --pose wings_up
```

The build refuses to overwrite an existing rigged .blend; preserve/version the output before rebuilding. Preview requires running Kit, reuses only the named PetrelRigTest prim, and changes the active camera. Supported --pose values are animation and the five named poses. No full flight controller is implemented.

The animation preview now starts independent playback through `POST /scene/birds/petrel/playback`. Kit update elapsed time drives the complete two-second source clip, independent of shared timeline play/pause, time position and loop range. No global timeline settings are changed. Static pose selection stops this controller before replacing the preview reference.

## Independent playback controls

With Kit running, start the preview using `python3 tools/preview_petrel_rig.py --pose animation`. Then run any of these commands from the repository root:

```bash
python3 tools/control_petrel_playback.py pause
python3 tools/control_petrel_playback.py resume
python3 tools/control_petrel_playback.py glide
python3 tools/control_petrel_playback.py flap
python3 tools/control_petrel_playback.py flap --speed 0.5 --transition 1
python3 tools/control_petrel_playback.py status
python3 tools/control_petrel_playback.py stop
```

Pause freezes both the current pose and blend progression. Resume continues at the held phase. Flap/glide commands resume playback and crossfade over 0.5 seconds by default; interrupted transitions start from the current blend weight. Speed is a 0.05–4 playback multiplier, not a biological frequency. The phase continues advancing during glide to support a smooth return to flapping. Start is idempotent and resumes rather than rewinding an existing controller.

Stop releases the temporary override and restores the original binding, so shared-timeline animation may become visible again. Use pause to hold a pose. Overrides live only in a private anonymous session sublayer and are removed on stop, extension shutdown, stage change, or target invalidation. Neither original assets nor the root USD layer are edited by playback. Pausing the global timeline does not pause this application-time preview; use its own pause control. This is not yet deterministic offline survey playback or flight-path locomotion.

HTTP: GET and POST `/scene/birds/petrel/playback`. POST fields: `name` (default `PetrelRigTest`), `action` (`start`, `pause`, `resume`, `stop`), optional `mode` (`flap`, `glide`), optional `speed`, and `transition_seconds` (0–10). The target must use the validated animated petrel rig, not a posed snapshot. Errors return `ok: false`; schema errors use normal service validation.

Verification: real-USD tests in Blender cover loop closure, default-only poses at different USD times, pause/resume, speed, smooth/reversed blends, invalid inputs, static-pose rejection, multiple-instance isolation, target removal, and complete override cleanup. Live Kit checks verified a full loop beyond 1.5 seconds, phase wrap, pause holding, glide completion, flapping at double speed, and return to normal speed. Ocean and cetacean controller code was not modified.

## Limitations

Scan feather-edge damage, asymmetry and imperfect cleaned foot contacts remain. No missing anatomy was reconstructed. The rig is accepted here for modest controlled pose tests, not extreme articulation, verified physical scaling, scientifically calibrated flight dynamics or final GSD datasets. The numeric and visual checks do not establish anatomical correctness beyond preservation of the existing cleaned surface.
