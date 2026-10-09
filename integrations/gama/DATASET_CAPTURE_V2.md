# Bounded GAMA-driven capture and annotation groups

Milestone 7 adds one fixed engineering capture operation to the existing
NVIDIA Kit Services bridge:

```text
POST /integration/gama/v2/actor/dataset-capture
```

```json
{"ownership_token": "<the acquired actor token>"}
```

Acquire and replay the actual version-2 GAMA trajectory through the existing
actor routes first. The new route accepts only the ownership token. It captures
the five conditions 0.5, 1, 2, 3 and 4 cm/px for a physically present target,
then the same five conditions after explicit target removal. Ownership must
subsequently be released through the existing actor release route.

The M6 public paired-capture interface remains unchanged. Both routes use one
shared transaction engine for controller/timeline gates, freezing, camera
construction, unique PNG probes, settling checks and fail-closed restoration.
The dataset operation adds a second private USD stage; it never removes the
animal from the original live stage.

## Pairing and presence

One composed scene is frozen before any asynchronous capture wait. Its positive
identity uses the unchanged M6 resolved-state definition. A private flattened
copy physically removes `/MarlinGamaPorpoise` using `RemovePrim`. The negative
identity binds the original GAMA state, positive parent hash and explicit removal
operation. The manifest records both scene identities and retained USD files.

A separate common-background hash excludes only the bridge-owned target,
camera subtrees and `/Render`. Renderer settings, source clocks and the common
positive dependency records remain in that hash. Both variants must have the
same background hash before and throughout rendering. The private negative
must contain no target root or target meshes. A submerged, hidden or out-of-frame
animal is still physically present and is never converted into a negative.

For each GSD, positive and negative camera-condition metadata must match. The
camera remains nadir, ideal perspective, 1024 × 768, 50 mm focal length and
5 µm pixel pitch. X/Z is anchored once to the selected animal root; only camera
Y changes with GSD. The reference plane remains the original animal root Y in
both variants. Camera height and footprint both vary, as in Pilot v1.

The current presentation environment is preserved. This is not a reconstruction
of Pilot's survey environment, and underwater refraction remains uncalibrated.
RGB equality is not inferred from matching camera or background hashes.

## Annotation semantics

Every condition retains `annotation.json`, `labels.txt`, capture metadata,
accepted RGB and all settling probes, with SHA-256 hashes. Class 0 denotes only
the bridge-owned harbour porpoise. Other demonstration animals are preserved
as explicitly unlabelled background; a negative means this target was removed,
not that every wildlife species was absent.

Positive boxes project every evaluated target-mesh vertex using its complete
world transform and the actual capture-camera matrices. JSON retains the raw
amodal rectangle, image-clipped rectangle, COCO-style rectangle and vertex
provenance. YOLO labels encode the clipped rectangle in normalized coordinates.
These are direct **amodal mesh boxes**, not exact visible silhouettes or refracted
underwater outlines. Rectangle area is not labelled as visible or silhouette area.

Rendered visibility remains `unknown` in machine metadata. No visible mask,
biological approval or calibrated refraction is inferred. A physically present
animal outside the image retains presence metadata and an empty image label.
Removed counterparts have no target geometry or box and an empty label file.
The static pose remains a provisional engineering proxy for all behaviours.

## Declared acceptance workload

The sealed declaration at
`experiments/gama_marlin_v1/m7_capture_declaration.json` selects actual M5
fresh-process runs with seeds 1, 42, 184729, 20261008 and 2147483647. It selects
steps 8, 16 and 32 (t = 4, 8 and 16 seconds): shallow swimming, descent and
ascent. These choices were declared from state records before M7 image viewing.
They do not cover every behaviour or validate biological dive poses.

The workload contains fifteen snapshot groups, seventy-five present images and
seventy-five matched removed-target images. It reuses actual independent GAMA
executions already sealed in M5; it does not manufacture replacement states or
claim new M7 GAMA executions.

Whole trajectories remain in one split. Seeds 1, 42 and 184729 belong to train;
20261008 to validation; 2147483647 to test. Related M5 repeated executions share
their trajectory family and split even when they contribute no new M7 images.
All three snapshots, five GSD versions and negative counterparts stay together.
This partition proves grouping mechanics; it does not establish statistical
independence, realistic wildlife prevalence or detector generalization.

Run the bounded client against the already running marine demonstration:

```bash
/usr/bin/python3 -B tools/capture_gama_dataset_v2.py \
  --declaration experiments/gama_marlin_v1/m7_capture_declaration.json \
  --output experiments/gama_marlin_v1/qa/m7_live_next
```

Choose a new output directory for every attempt. The client verifies source
seals, reparses raw GAMA exports, pins current runtime code and validates captures,
annotation arithmetic, hashes, pairing and split membership. It preserves
unsuccessful groups and never chooses more attractive replacement steps.
`--preflight-only` checks prerequisites without acquiring an actor or rendering.

The capture engine collects unreachable helpers before the existing GPU
headroom check. Its 768 MiB requirement remains unchanged. The client may retry
an exact, explicitly pre-render headroom refusal up to four attempts, twenty
seconds apart, while verifying that the same applied state and pose remain held.
Every refusal is recorded. Any allocated group, other error, state change or
exhausted retry budget stops the attempt; no snapshot or trajectory is replaced.

Independent retained-USD verification subsequently rebuilds both scene
identities, target removal, common background, cameras and direct vertex labels
without attaching a stage to Kit. Contact sheets are viewing derivatives; all
source captures remain unchanged. The live client verifies original-scene
restoration and resumed ocean/demonstration animals after each trajectory.

No detector training, new species, biological parameter changes or full native
HiDef/Sony experiment is part of this bounded test set.
