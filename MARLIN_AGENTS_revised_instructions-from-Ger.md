# MARLIN — Codex Working Manual
## Current research priority: GSD requirements for digital aerial wildlife surveys

### 1. Project identity
MARLIN stands for:

**Marine Animal Rendering, Locomotion, Interaction and Navigation**

MARLIN is an NVIDIA Omniverse Kit application being developed as a controllable marine/wildlife simulation environment.

The immediate research priority is no longer a framework/tool paper. MARLIN is to be used as an **experimental instrument** to quantify ground-sampling-distance (GSD) requirements for automated wildlife detection and classification in digital aerial surveys.

The MARLIN framework paper remains a valid second paper after the outcome-focused GSD study.

The user's separate agentic-SDLC / agentic track is not part of this task.

### 2. Repository
Repository root:

    /home/madil/kit-app-template

Main Kit app:

    source/apps/cris.madil.kit

Main extension:

    source/extensions/cris.madil.render_service

Primary service implementation:

    source/extensions/cris.madil.render_service/cris/madil/render_service/service.py

HTTP service:

    http://localhost:8011

Swagger:

    http://localhost:8011/docs

### 3. Generated directories
Do not inspect, search, edit, or modify generated/runtime material unless explicitly necessary:

    _build/
    __pycache__/
    .cache/
    *.pyc

Canonical source is under:

    source/

Do not edit generated copies inside `_build`.

### 4. Existing functionality that must remain working
Preserve:

- procedural animated ocean
- shared ocean-surface sampling
- ocean/environment generation
- USD wildlife spawning
- cetacean transform control
- swimming and heading control
- speed control
- boundary avoidance
- ocean-relative vertical following
- diving/surfacing work
- `/scene/marine/setup`

Do not redesign unrelated functionality during the GSD-paper work.

### 5. Existing cetacean asset library must be retained
All cetacean/marine-mammal assets downloaded and converted so far are to remain in the project.

Current converted assets include:

- bottlenose_dolphin
- cuvier_whale
- frasers_dolphin
- humpback_whale
- manatee
- model_61a_-_bottlenose_dolphin
- pantropical_spotted_dolphin
- pilot_whale
- pygmy_sperm_whale
- sperm_whale
- steno_dolphin

Do not delete or discard these assets simply because they are not all required for the first GSD experiment.

They remain valuable for:
- later MARLIN framework work
- multi-species simulation
- behavioural work
- future papers
- demonstrations

However, **paper-specific wildlife assets take implementation priority**.

### 6. Paper-first scientific objective
Primary question:

> Holding environment and target conditions controlled, at what GSD does each task — detection, group classification, and species classification — fall below an explicitly defined performance threshold?

The planned GSD sweep is:

    0.5 cm/px
    1.0 cm/px
    2.0 cm/px
    3.0 cm/px
    4.0 cm/px

GSD is the primary independent variable.

The system must make it possible to render controlled synthetic observations while preserving exact ground truth.

### 7. Paper-specific wildlife taxonomy
Implement the following first because they correspond to commercial survey categories.

#### Avian groups / species
- Storm petrels — European storm petrel
- Shearwaters — Manx shearwater
- Terns — Common tern
- Small gulls — Kittiwake
- Auks — Guillemot and Razorbill
- Gannet — Northern gannet

Note: this is six avian groups but seven named bird species because the Auk group contains both Guillemot and Razorbill.

Birds must support at least two distinct states:
- sitting on water
- in flight

For flying birds, altitude above the sea must be represented because it changes effective GSD.

#### Non-avian targets
Prioritise:
- Harbour porpoise
- Common dolphin
- Risso's dolphin
- Minke whale

Keep the broader downloaded cetacean library intact alongside these.

### 8. Camera models
Implement two explicit camera configurations.

#### A. HiDef validation replica
Use the PI-specified geometry:
- Prosilica GT6600C
- image dimensions: 6576 × 2192
- focal length: 150 mm
- nominal flight altitude: 549 m
- pitch: 30 degrees
- roll cases: 7.77 degrees and 23.17 degrees
- non-nadir geometry
- across-frame GSD varies approximately 2.22–3.36 cm/px against a nominal 2 cm/px

The non-nadir geometry is scientifically important.
Do not replace it with an easier nadir camera for the validation configuration.

#### B. Sony trial configuration
- Sony ILX-LR1
- focal length: 85 mm
- altitude: 150 m
- nominal GSD: 0.663 cm/px
- swath: approximately 63 m

This configuration is intended to de-risk planned fixed-wing flights.

### 9. Controlled environment for the GSD experiment
For the first paper, keep environmental appearance intentionally fixed.

Target condition:
- calm sea
- overcast / diffuse lighting
- no sun glint
- one controlled water appearance
- no precipitation
- no unnecessary environmental variation

Do not introduce weather/domain randomisation into the principal GSD experiment.

The purpose is to isolate resolution as the experimental variable.

### 10. Randomisation within each GSD level
Within every GSD condition, randomise target nuisance variables evenly, including where applicable:

- pose
- heading
- position in frame
- surfacing state
- bird flight/sitting state
- bird altitude above water
- individual placement

Randomisation must not confound GSD.

### 11. Synthetic data generation
MARLIN must support automated dataset generation.

Each rendered example should have machine-readable metadata sufficient to reconstruct the experimental condition.

At minimum record:
- frame ID
- species
- group label
- task labels
- object/world position
- image position
- pose/orientation
- heading
- behavioural/surfacing/flight state
- bird altitude when applicable
- camera model
- camera pose
- nominal GSD
- local/effective GSD where geometry causes variation
- pixels on target
- bounding box or segmentation information as available
- scene/instance identifier for split control

### 12. Automated annotation outputs
Implement exact synthetic ground truth.

Required outputs should support:
1. detection
2. group classification
3. species classification

Prefer export formats that can be consumed by common CV pipelines, e.g.:
- COCO-style JSON
- optional YOLO-format boxes
- per-frame metadata JSON/CSV

Do not derive labels from image analysis when the simulator already knows the ground truth.

### 13. Dataset splitting
Avoid leakage.

Train/validation/test splits must be clean by:
- scene
- species instance / asset instance where appropriate
- generated sequence

Do not allow near-duplicate renders of the same scene/instance to appear across train and test.

### 14. ML experiment
The first ML system should be a simple, reproducible baseline rather than an elaborate architecture.

Evaluate three separate tasks:

#### Task A — Detection
Object present / localisation.
Primary threshold candidate: **90% recall**, because survey screening is recall-critical.

#### Task B — Group classification
Correct assignment to the survey-relevant group.

#### Task C — Species classification
Correct species assignment within/beyond group as applicable.

Possible experimental design:
- detector/model per GSD level, or
- one model trained with GSD explicitly recorded/conditioned

Keep evaluation synthetic-to-synthetic for the controlled curve.

### 15. Optional real-data sanity check
Do not make real imagery the main validation of the GSD curve.

Optionally compare at the one resolution point represented by the real benchmark.
The PI identifies Ben's frame-by-frame cross-validation survey benchmark as the defensible reference.

Treat this only as a sanity check at one point, not validation of the whole synthetic GSD curve.

### 16. Primary scientific outputs
The key result should be a lookup table:

    species/group
    task
    minimum acceptable GSD
    pixels on target
    equivalent altitude for HiDef configuration
    equivalent altitude for Sony configuration

The paper should make it possible for a survey planner to use the result operationally.

Report both:
- cm/px
- pixels on target

Pixels-on-target makes the result more transferable across sensors.

### 17. Current priority order
Implement in this order:

1. Freeze experimental specification and taxonomy.
2. Retain existing cetacean library.
3. Acquire/convert/calibrate paper-specific bird and marine-mammal assets.
4. Implement bird flight/on-water states and bird altitude handling.
5. Implement/calibrate HiDef camera model.
6. Implement/calibrate Sony camera model.
7. Implement controlled survey scene injection.
8. Implement GSD sweep control.
9. Implement automated annotation/metadata outputs.
10. Generate QA dataset.
11. Develop baseline ML pipeline.
12. Run controlled GSD experiments.
13. Derive task/species thresholds and lookup table.
14. Complete first paper.
15. Return later to MARLIN framework paper and broader cetacean behaviour work.

### 18. What not to do now
Do not:
- delete existing cetacean assets
- expand unrelated pod behaviour before the GSD experiment needs it
- redesign the ocean unnecessarily
- add broad weather randomisation
- mix the agentic track into MARLIN
- prioritise a MARLIN framework paper ahead of the GSD result
- invent biological parameters without evidence
- silently change coordinate conventions
- refactor large unrelated parts of service.py

### 19. Development style
Use small, testable increments.
Reuse existing spawning/camera/service mechanisms.
Preserve existing endpoints unless a change is explicitly required.
Keep new experimental APIs parameterised and reproducible.
Add useful validation and informative error messages.
Stop after each major milestone and report what changed before moving to the next milestone.

### 20. Immediate next milestone
The next concrete milestone is:

**Research-specification and asset-injection phase**

Definition of done:
- paper taxonomy represented in code/config
- existing cetacean library retained
- asset folders created for required paper species
- required new models acquired/converted or clearly flagged as missing
- camera-model configuration schema designed
- GSD experiment configuration schema designed
- no unrelated large refactor performed

After this, proceed to camera injection and automated data generation.
