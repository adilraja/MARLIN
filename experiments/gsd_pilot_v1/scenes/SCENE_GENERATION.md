# Milestone 3 — Frozen environment and seeded scenes

This milestone establishes reproducible scene geometry and recorded renderer
state for the two calibrated targets. It prepares candidate records and four
representative frozen scenes. Dataset rendering, underwater label visibility,
actual captured GSD and RGB repeatability remain Milestone 4–5 work.

## Frozen engineering choices

`../environment.json` defines `gsd_baseline_v1`, derived from the existing
`survey_environment_v1.json`. The ocean is a flat 160 m square at Y=0; its shared
surface-sampling convention is preserved. The declared diffuse dome is retained,
the sun has zero intensity, underwater fog is disabled, and the additional Kit
`/Environment/defaultLight` is removed from the experiment snapshot. No source
ocean, material, wildlife asset, swimming or dive implementation was changed.

The preset records 73 renderer/control settings, including null values for
unavailable or unset options. It requests PathTracing, 8 samples per iteration,
128 total samples, disabled adaptive sampling, disabled OptiX denoising and
temporal mode, and disabled path/light caches. Exposure, tone mapping, colour
correction/grading and post effects are explicit. These are engineering choices;
actual capture sample counts and image noise still need M4 verification.

The installed OCIO configuration path is retained as an external runtime
dependency. Its generated/cache contents were not inspected or hashed. No
verified RTX random-seed control was found, so renderer seed remains null.
Biological scene seeds do not imply deterministic RTX noise or bitwise RGB.
Renderer setting names follow the [NVIDIA path-tracing documentation](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/rtx-renderer_pt.html)
and [post-processing documentation](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/rtx_post-processing.html).

## Sampling contract

| Quantity | Frozen choice |
| --- | --- |
| Master seed | 20260929 |
| Initial candidates | `european_storm_petrel_0000`–`0024`; `harbour_porpoise_0000`–`0024` |
| Root X and Z | Independent uniform draws from −0.6 to +0.6 m |
| Heading | Uniform draw from 0 to 360 degrees |
| Petrel root altitude | Uniform draw from 0.75 to 1.25 m |
| Porpoise clearance below water | Uniform draw from 0.02 to 0.08 m, measured from highest calibrated vertex |
| Porpoise root Y | Negative calibrated maximum local Y minus sampled clearance |
| Pitch and roll | Fixed at zero |
| Pose | M2 static pose, evaluated at time code 1 |
| World convention | Y-up; heading 0 = +Z; heading 90 = +X; stage unit = 0.01 m |

Upper interval endpoints are excluded. These ranges are deliberately narrow,
provisional engineering variations, not measured flight altitudes, natural dive
depths or population distributions. The petrel remains a static spread-wing
proxy; the porpoise remains a shallow static mesh. Unsupported biological states
were not added. The unchanged M2 records retain size/landmark uncertainty.

`sampling.py` reuses `survey_spec.condition_seed(master_seed, scene_id)`. Each
named draw uses a separate SHA256-derived stream, so evaluation order and the
global Python random generator cannot change results. GSD is excluded from all
animal draws. Every manifest stores sampled values, subdraw seeds, algorithm
version, IDs, calibration and asset hashes, physical units and camera variants.
Validation rejects modified inputs and tampered manifests, even if their outer
hash is recomputed.

Candidates rejected by later QA must retain their reason and ID. Replacement
IDs advance numerically from 0025; the sampler does not silently resample. All
50 initial proposals passed geometric footprint checks at all five GSDs. They
are not yet accepted dataset scenes: visibility and capture QA are outstanding.

## Geometry, cameras and frozen time

`build_scenes.py` composes the existing calibrated assets into private USD
stages using MARLIN's root/Model transform layout. It uses the existing
`calibration_geometry.build_camera` helper. Blender supplies USD for
preprocessing and verification; MARLIN's existing Kit renderer remains the
rendering engine. No new server or renderer was introduced.

The fixed ideal camera has 1024×768 pixels, 50 mm focal length, 5 μm pixel pitch,
nadir orientation and world X/Z=0. Across paired variants only world camera Y
changes, at 50/100/200/300/400 m above the saved animal-root reference plane.
Clipping planes are explicitly held constant at 1 and 100000 stage units,
overriding the helper's height-dependent defaults. Camera fixture dimensions
used to satisfy the helper's validation are never used as animal labels and no
fixture target mesh is created.

Skinning is baked on private flattened stages, then every sampled attribute is
evaluated at time code 1 and replaced by a constant. Snapshots contain no time
samples. The live orchestration stops the ocean, gallery, single swimmer,
chase-camera and petrel controllers and verifies their stopped states before
attachment and after waits. An advancing timeline therefore has no changing
geometry left to evaluate. Checkpoint restoration alone would not stop those
application callbacks.

Each representative scene has a canonical biological identity that includes
animal state, calibration, geometry, environment and dependency records. Camera
variants are excluded from that identity and are recorded separately. USD byte
hashes protect saved files; numerical/semantic comparisons verify reconstructed
scenes because equivalent USD serialization need not have identical bytes.

## Reconstruction evidence

`../qa/m3_scene_geometry.json` records all 50 proposals and their five geometric
projection checks. First and last candidate IDs for each species additionally
have full USD snapshots under `snapshots/`, with independent reconstruction.
`snapshot_index.json` identifies the registered packages used by the existing
bounded Kit checkpoint loader.

`live_replay.json` records two attachments per representative scene and an
immediate plus delayed checkpoint for each attachment. The final verifier checks
all 16 snapshots against their expected geometry, authored attributes,
relationships, material connections, lights, camera, viewport resolution and
renderer settings. World-vertex tolerance is 1e-5 m; general numeric attributes
use 1e-6 absolute and 1e-7 relative tolerances. No RGB-equality claim is made.
The final pass/fail result is `../qa/m3_reconstruction.json`.

Two failed configurations remain under `rejected_replays/`:

1. `fill_frame=True` made the viewport follow the panel's 837×356 size instead
   of the requested 1024×768. Final snapshots use `fill_frame=False`.
2. Kit retained antialiasing mode 3 despite a request for 0 and authored three
   camera-exposure attributes. The final preset explicitly records mode 3 and
   those observed exposure values. The verifier requires their equality rather
   than ignoring them.

The only runtime implementation change expands renderer-state recording in
`hidef_marine.py` and preserves compatibility with older replay records. Older
records explicitly report settings they never captured; current before/after
restoration checks remain strict. Kit reloaded the source without a restart.

## Reproduction and completion preview

Run sampler tests with system Python and geometry checks with the existing
Blender installation, always disabling bytecode:

```bash
python3 -B -m unittest discover -s experiments/gsd_pilot_v1/qa -p 'test_*contract.py'
python3 -B -m unittest discover -s experiments/gsd_pilot_v1/qa -p 'test_scene_sampling.py'
PYTHONDONTWRITEBYTECODE=1 /home/madil/opt/blender-5.0.1-linux-x64/blender --background --factory-startup --python-exit-code 1 --python experiments/gsd_pilot_v1/qa/verify_m3_reconstruction.py
```

The builder and `live_session.py prepare/replay` refuse to overwrite completed
evidence. For a new run, create a separately configured output revision and
retain the existing manifests and failure records. `prepare` uses the preserved
empty M2 checkpoint; registered snapshot packages live under
`artifacts/scene_checkpoints/`. External texture/material/runtime dependencies
must still resolve on another machine.

At the user's request, each remaining milestone must end by restoring the
existing demonstration environment and 11 default animals swimming in moving
water. `live_session.py preview` performs this bounded operation and records
statuses plus two checkpoints. The M3 verifier checks changing animal-local
body geometry, changing world positions and changing ocean vertices, then
leaves the live viewport running for the user's visual validation. The saved
experiment snapshots remain frozen and separate from that demonstration.

```bash
python3 -B experiments/gsd_pilot_v1/scenes/live_session.py preview
```

Milestone 4 must still prove actual five-GSD images, visible labels and
pixels-on-target, including the underwater projection limitations.
