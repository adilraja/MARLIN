# Milestone 2 — Wildlife calibration

Completed 2026-09-29 for the provisional engineering pilot. The selected European
storm petrel and harbour porpoise both spawn through the existing MARLIN Kit API.
Evaluated world geometry, unit conversion, orientation, material bindings,
texture resolution and static placement passed verification. Physical references
and visual states retain the uncertainties below. This does not certify animal
behaviour, photorealism or visibility at the five experimental GSDs.

Machine-readable inputs are `calibration_inputs.json`; final records are
`european_storm_petrel.json` and `harbour_porpoise.json`. `measurements.json`
contains every landmark and dependency hash. `sources.json` records provenance.

## Selected references and transforms

| Quantity | European storm petrel | Harbour porpoise |
| --- | --- | --- |
| Scientific name | Hydrobates pelagicus | Phocoena phocoena |
| Physical reference | 0.17 m nominal body length | 1.555 m publisher-reported specimen length |
| Fit landmarks | Beak to tail candidates | Rostrum to fluke-notch candidates |
| Corrected mesh dimensions X/Y/Z, m | 0.264831 / 0.105417 / 0.170000 | 0.419237 / 0.432788 / 1.601489 |
| Spawn scale in a 0.01 m/unit stage | 0.46948425525029247 | 100.0 |
| Model XYZ correction, degrees | −70.55174997306713 / −24.139515839037514 / 0 | −90 / 0 / 0 |
| Selected static state | `static_spread_wing_proxy` | `static_shallow_swim` |
| Asset licence | CC0-1.0 | CC-BY-NC-4.0 |

The JSON records retain computational precision for replay. These digits do not
represent physical measurement accuracy. Mesh bounding-box dimensions include
wings, fins and other retained geometry; they are not anatomical body lengths.

The petrel publisher identifies museum specimen Z/155/MT as *Hydrobates
pelagicus*. The selected asset is the existing `glide.usd` derivative of that
mounted specimen. Species identity is publisher-supported, without independent
taxonomic examination. [Publisher model](https://sketchfab.com/3d-models/8bb167b9a8144b97a011f50aabcdc270)

The 0.17 m body reference is an explicit midpoint choice from the published
0.15–0.19 m species range, not a measurement of this museum specimen. That range
is not a confidence interval. The candidate endpoints were checked in dorsal
and side geometry plots. Their equivalence to a biological measurement protocol
is provisional. [Naturalis species account](https://birds-europe.linnaeus.naturalis.nl/linnaeus_ng/app/views/species/taxon.php?id=130352)

An initial 0.38 m wingspan fit was rejected: the mounted wings are bent and
asymmetric, so their posed tip distance is not a fully extended wingspan. That
fit made the body approximately 0.24 m long, exceeding the reference range.
`rejected_wingspan_fit.json` retains the calculation. At the selected body scale,
the posed tip distance is 0.266192 m. No wings or anatomy were altered to force a
match. [Wingspan context](https://www.seabird.org/wildlife/storm-petrel)

The porpoise is the existing static derivative of DigitalLife3D Model 75A,
Freja, whose publisher reports a total length of 155.5 cm. The candidate already
has that scale baked into its geometry: its selected landmark distance measures
1.554999991 m. Scale 100 converts metres into this Kit stage's centimetres; it
does not assert that every species needs scale 100. The publisher's measurement
protocol and its correspondence to the chosen rostrum/fluke-notch pair remain
unverified. The 1.601489 m fin-inclusive bounding box is not an alternative
biological length. Preserve DigitalLife3D attribution and its noncommercial
licence with derived outputs. [Publisher model and length](https://sketchfab.com/3d-models/eb02e57f17d741329a66844a3a8d2094)

## Geometry and visual review

Measurements use all 156,856 petrel vertices and 23,456 porpoise vertices after
parent transforms. Petrel skinning is evaluated at time code 1 on a private,
flattened USD stage. Original layers are unchanged. The source assets declare
Z-up and metre units, but metadata alone does not establish biological scale.
References are composed with MARLIN's existing root/Model transform layout.
Stage Y is vertical, heading 0 points horizontally +Z and heading 90 points +X.
The source origin is retained; it is not necessarily the animal's centre.

`live_validation.json` compares every evaluated vertex from two actual Kit scene
checkpoints against independent calibrated positions. The largest discrepancy
is 4.83e-9 m, within the declared 1e-5 m engineering tolerance. All four cardinal
headings pass geometric checks; heading 90 was also authored and inspected live.
The chase camera follows heading, so a similar silhouette orientation in the
heading screenshots is expected and is not used as evidence of world rotation.

All meshes have bound surface materials, and all expected local textures resolve
with unchanged hashes. Some small eye/material meshes intentionally have constant
materials rather than texture images. Dry top, side and oblique views were
reviewed. Initial tight top views cropped the animals and are retained as failed
framing evidence; `*_top_complete.png` supersedes them. Wider cameras fixed the
framing without changing either model's scale.

The petrel retains asymmetric wings, feet/contact remnants, damaged feather
edges and taxidermy appearance. `glide.usd` is a filename, not evidence of a
validated natural gliding posture. One static spread-wing proxy is supported;
flight kinematics and animation are not part of this calibration.

The porpoise's dorsal view is very dark; mottled ventral texture appears in the
side view. The shallow-water view is visibly blurred. Texture resolution passed,
but albedo, lighting, water optics and apparent underwater outlines have not
been calibrated. The static candidate excludes previously identified helper
geometry; original source, helper and armature files remain preserved.

## Static placement and saved scene

The review uses flat water at Y=0. Petrel root Y=1 m is an engineering inspection
placement, not a sourced flight altitude; the lowest retained vertex is
approximately Y=0.94714 m. Porpoise root Y=−0.180725579 m is derived from its
measured maximum local Y and a chosen 0.02 m clearance. Its highest vertex is
Y=−0.02 m and its lowest is approximately Y=−0.452788208 m. This demonstrates a
fully submerged static mesh, not a breathing waterline or biological dive depth.
No species speed, dive-duration or motion parameters were invented.

Kit was not running at the start. It was launched using the documented app
launcher; its initial empty scene was checkpointed before preview setup. The
review reused `/scene/survey/environment`, `/scene/cetacean/spawn`, transform,
camera and debug capture endpoints. No runtime source, registry, behaviour
controller, original asset or camera calibration profile was edited.

| Checkpoint | Purpose |
| --- | --- |
| `checkpoint_0si09svp` | Empty scene before review |
| `checkpoint_1mkaca7v` | Both animals above water for geometry and material inspection |
| `checkpoint_gfirg5og` | Final petrel-above-water and shallow porpoise scene |

Checkpoint directories are under `artifacts/scene_checkpoints/`; response records
with exact paths and hashes are in `kit_review/`. Kit remains open with the review
scene. These snapshots have external material dependencies and do not serialize
behaviour-controller state. They are M2 evidence, not the M3 reconstruction proof.

## Reproduce the checks

Run from the repository root, with bytecode disabled:

```bash
PYTHONDONTWRITEBYTECODE=1 /home/madil/opt/blender-5.0.1-linux-x64/blender --background --factory-startup --python-exit-code 1 --python experiments/gsd_pilot_v1/wildlife/measure_calibration.py
/home/madil/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B experiments/gsd_pilot_v1/wildlife/plot_calibration.py
PYTHONDONTWRITEBYTECODE=1 /home/madil/opt/blender-5.0.1-linux-x64/blender --background --factory-startup --python-exit-code 1 --python experiments/gsd_pilot_v1/wildlife/verify_live_calibration.py
python3 -B experiments/gsd_pilot_v1/qa/verify_milestone_2.py
```

These commands replace their measurement/validation outputs. The final packaging
manifest hashes the original completed outputs; a later rerun may change output
bytes and must retain separate provenance. Resolve the desktop Python runtime
through its dependency loader on another installation; it supplies NumPy/Pillow.
Blender supplies USD. No new packages were installed.

`kit_preview.py` and `kit_review_states.py` retain the live API procedure. They
deliberately refuse to overwrite completed review reports; the initial preview
also rejects a populated scene. For a new review, use a separately configured
output directory and an intentionally empty scene. Do not delete these records
or reset an active scene simply to rerun the scripts.

## Handoff to Milestone 3

Specification 1.1.0 resolves target identity, physical reference records and one
static state per target. M1 originals remain under `history/milestone_1/` with a
path relocation map for its unchanged manifest. GSD, camera and ML protocols
remain unchanged. M3 must freeze sampling ranges, environment/renderer settings
and scene reconstruction. M4 must verify experimental image visibility, mesh
labels, underwater projection limits and actual GSD. No dataset or detector has
been generated by this milestone.
