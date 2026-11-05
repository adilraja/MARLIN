# MARLIN — GAMA–Omniverse Bottlenose Dolphin Behaviour and Animation

## Codex sprint specification

| Field | Specification |
|---|---|
| Document version | 1.0 — proposed execution specification |
| Prepared | 5 November 2026 |
| Project | Continue the existing MARLIN / Omniverse Kit repository |
| Repository | `/home/madil/kit-app-template` |
| Target | One existing bottlenose dolphin: the DigitalLife3D Model 61A asset used in the accepted ocean-material demonstration, subject to M1 verification |
| Water | Preserve the accepted `engineering_v1` preset and its documented limitations |
| Primary outcome | Coherent, reproducible behaviour, movement and visible body animation for one animal |
| First authorised work | M1 audit and baseline only; stop at Gate A before implementing the proposed behaviour or animation changes |
| Completion scope | Engineering demonstration plus named visual review; biological support is assessed separately |

> **Sprint objective:** Produce one bottlenose dolphin whose GAMA-generated behavioural state and movement agree with its visible body animation in MARLIN, with smooth transitions, reproducible playback and freezeable scene snapshots.

This is an incremental development sprint, not a new integration project. Reuse the working GAMA bridge, animal asset, capture path, wave sampler and controllers where appropriate. Do not rebuild MARLIN or replace working components without an identified requirement and an explicit review decision.

The six milestones below are the agreed development structure. The detailed tasks, test workload and file names are proposed execution requirements, not statements that those capabilities or evidence already exist. The current local repository and asset must be inspected during M1. Reported ocean-material acceptance does not establish biological realism or resolve the remaining ocean limitations.

---

## 1. Scope and boundaries

### 1.1 In scope

The sprint covers one animal's behaviour state machine, constrained movement, deterministic state-to-animation mapping, playback, freeze/replay and bounded verification. It includes reuse or limited improvement of the existing rig or procedural body animation where necessary for the demonstration.

The first controlled sequence is:

**Steady swimming → gradual turn → controlled descent → submerged swimming → ascent → return to steady swimming.**

This is an engineering test scenario. Its order and timing are not an assertion of a natural dolphin activity cycle. After the deterministic sequence works, introduce bounded seeded variation in selected parameters without making independent random changes every rendered frame.

### 1.2 Out of scope

Do not add other species, pods, flocking, migration, feeding ecology, physiological oxygen/fatigue models, a new ocean system, new water materials, camera redesign, annotation redesign, dataset production or ML training. Do not turn this into full hydrodynamic simulation or a general character-animation framework.

Do not modify the accepted water preset, the dolphin's material or its calibrated size merely to improve the appearance of a manoeuvre. Do not change the historical GSD pilot, GAMA engineering dataset, previous reports, metrics, manifests or accepted checkpoint scenes.

Small validation captures are allowed. They are engineering evidence, not a new training dataset or an operational survey-validation result.

### 1.3 Existing environment

Read the applicable repository instructions, including `AGENTS.md`, before working. Canonical application code is expected under `source/apps/` and `source/extensions/`; verify the current structure. Do not edit generated files in `_build/`, `extscache/`, caches or installed dependencies. Any essential read-only dependency inspection must be recorded and limited to resolving a specific interface or version question.

Inspect the installed GAMA, Kit and animation capabilities rather than assuming a current online example matches this runtime. No reinstall, broad dependency upgrade or new animation subsystem is authorised by this specification alone.

Verify current GPU resources. Do not assume that a previously discussed hardware upgrade has arrived. Retain existing memory safeguards and qualified capture settings. Native LDR PNG, camera-inside attenuation and full-resolution HiDef/Sony capture are not prerequisites for this sprint and must not be declared solved by it.

---

## 2. Responsibility and timing contract

Use the existing interface where possible. Extend it only where a necessary control or provenance field is missing, and record compatibility implications.

| Component | Responsibility |
|---|---|
| GAMA | Behavioural progression; world-space trajectory; speed, heading and depth evolution; manoeuvre timing; seeded choices |
| MARLIN adapter | Validate and map recorded GAMA state into the established scene coordinates and units; perform documented presentation interpolation without inventing new behaviour |
| MARLIN animation controller | Evaluate supported skeletal or procedural body motion from simulation time, motion state and fixed parameters |
| Asset-calibration transform | Preserve the fixed source-asset orientation and scale correction, separately from dynamic motion |
| Experiment/replay controller | Start, pause, seek, resume, capture, reset and preserve evidence |
| Ocean and camera systems | Continue their established duties without an unrecorded redesign |

**One owner per controlled degree of freedom.** GAMA owns progression through the world. The animation system must not add a second world translation or heading. Handle root motion embedded in animation clips explicitly; do not let it silently double the commanded movement.

Define precisely where trajectory-related pitch and roll are calculated. They may be supplied by GAMA or deterministically derived from its trajectory according to a recorded rule, but must not be independently recalculated by competing controllers. Local skeletal motion remains distinct from the world transform.

Simulation time is authoritative. Wall-clock delays, network arrival time, viewport frame rate and render-settling frames must not independently advance the animal's behavioural state or animation phase.

A frozen snapshot must retain the resolved world transform, selected pose/animation state, phase, blend weights, relevant controller state, ocean state and lighting state. A seed is provenance, not a substitute for retaining the realised state sequence.

---

## Milestone 1 — Audit the existing dolphin and preserve a baseline

### Objective

Establish what actually exists, how the dolphin currently moves, and the smallest changes needed for this sprint.

### Tasks

**M1.1 — Read the existing implementation.** Identify the active GAMA model, its launch/replay path, bridge code, state schema, animal-spawning functions and controller entry points. Distinguish actual GAMA output from manually constructed fixtures.

**M1.2 — Resolve the exact asset.** Locate the dolphin used in the accepted ocean-material demonstration. Record its asset identifier, USD paths, dependencies, source/licence record, calibration transforms and measured composed dimensions. Verify that the active asset is the intended Model 61A rather than another bottlenose mesh.

**M1.3 — Inspect animation capabilities.** Determine whether the asset uses a skeleton, animation clips, procedural vertex deformation or a combination. Inventory joints, clips, actions, playback controls, loop behaviour, root motion and any helper geometry. Do not assume that an armature in an earlier source file survives in the active USD asset.

**M1.4 — Audit movement ownership.** List every mechanism able to write the target's world transform or pose: existing swimmer, dive controller, boundary avoidance, ocean following, GAMA adapter, timeline clips and procedural callbacks. Identify conflicts and existing controls that can be disabled for this instance only.

**M1.5 — Verify configuration and hardware.** Read current stage units and axis conventions, active water preset, supported capture route, installed runtime versions and current GPU headroom. Verify relevant preset/dependency pins; do not reopen water-material development.

**M1.6 — Preserve the baseline.** Save a restorable scene/configuration and record the code commit and dirty-worktree state. Retain representative current dolphin motion and stills through the supported capture route where resources permit. Preserve the original asset and material unchanged.

**M1.7 — Propose the implementation path.** Classify capabilities as working, unverified, missing or conflicting. Prefer existing body animation. If there is no usable body-motion mechanism, propose the smallest rig or procedural adaptation and stop for approval before substantial asset work.

### Deliverables

- `M1_ASSET_AND_CONTROLLER_AUDIT.md`
- `baseline_manifest.json` and restorable baseline scene/configuration
- Asset/animation inventory and proposed implementation plan
- Baseline images or a short recording, or an explicit capture-blocker record

### Acceptance criteria — Gate A

The exact animal and active controllers are identified; prior work is preserved; the animation limitations are explicit; and a named reviewer accepts the proposed change scope. No new behaviour model, rig replacement or controller refactor begins before this gate passes.

---

## Milestone 2 — Define and test movement ownership and simulation time

### Objective

Give the two systems an unambiguous contract for movement, orientation, vertical placement, timing and animation control.

### Tasks

**M2.1 — Specify required state information.** Reuse existing field names where suitable. The contract must identify schema/model version, run ID, agent ID, sequence/step index, simulation time, time step, behavioural state, world position or its unambiguous equivalent, movement variables and relevant parameters. Record state-entry time and transition progress where required for animation blending.

**M2.2 — Verify coordinate mapping.** Document GAMA-to-MARLIN axis mapping, handedness, angle units, rotation order and heading convention. Verify the previously used Y-up, 0° = +Z convention rather than silently assuming it. Keep source-asset calibration separate from dynamic orientation.

**M2.3 — Resolve the depth reference.** Select the existing supported convention where possible: mean sea level, absolute world height or instantaneous surface-relative depth. Do not allow absolute Y and depth to independently drive the same target. If the wave sampler resolves a relative depth, retain the sampled surface and resolved position. Do not make submerged motion follow every wave by accident.

**M2.4 — Enforce single-controller ownership.** Disable competing autonomous movement and diving for the experimental dolphin only. Define acquire, pause, release and restoration behaviour. Keep other demonstration animals working. Detect duplicate subscriptions or other writers that continue modifying the target.

**M2.5 — Define the animation clock.** Derive clip/procedural phase from simulation time and recorded parameters. If the animation uses speed-dependent phase accumulation, retain enough controller state to reproduce it or recompute it deterministically from the trajectory. Changing capture order must not change animation phase.

**M2.6 — Define interpolation and delivery rules.** Document the interpolation method and its permitted effects on trajectory reconstruction. Use correct angle wrapping around 0°/360°. Define duplicate, stale, out-of-order and missing-state behaviour. Default to freezing the last valid state and reporting the condition rather than starting an independent autonomous fallback.

**M2.7 — Test the contract.** Exercise known translations, all four cardinal headings, depth changes, zero speed, pause/resume and reset. Compare the composed USD transform with the expected state, not only an internal dictionary. Invalid values must not partially mutate the scene.

**M2.8 — Lock numerical tolerances.** Before acceptance runs, declare tolerances for mapping, interpolation, replayed world transforms and the available pose measurements. Select and justify numeric values from the runtime's precision, units and use case. A tolerance cannot be chosen after inspecting a failure simply to make it pass.

### Deliverables

- `M2_STATE_OWNERSHIP_AND_TIME_CONTRACT.md`
- Schema or schema extension with valid/invalid fixtures
- `acceptance_tolerances.json`
- Automated coordinate, ownership, timing and failure-handling results

### Acceptance criteria

A recorded state maps to one expected scene state; only the designated controller advances movement; root motion does not duplicate translation; zero-speed and heading-wrap cases work; malformed/stale messages follow the declared policy; and pause/resume does not cause a jump.

---

## Milestone 3 — Implement smooth, constrained GAMA movement

### Objective

Generate coherent swimming, turning, descent and ascent trajectories instead of disconnected positions or an uncontrolled random walk.

### Tasks

**M3.1 — Implement the controlled scenario.** Use the existing GAMA model as the starting point. Express steady swimming, gradual turn, descent, submerged swimming, ascent and return to steady swimming through a small state machine or an equivalent documented controller. State names alone do not count as executed movement.

**M3.2 — Define transition conditions.** Record how each state starts and ends: elapsed simulation time, progress through a turn, arrival at a depth or completion of a transition. Avoid unexplained frame-count triggers and unrecorded wall-clock decisions.

**M3.3 — Add compatible movement constraints.** Configure speed, acceleration, heading-change rate, vertical velocity and trajectory-attitude limits. Define whether `speed` means horizontal speed or full 3D speed. Cross-check position changes against the stated velocities. At zero speed, retain a defined orientation rather than deriving one from a zero-length velocity vector.

**M3.4 — Smooth transitions.** Ramp speed, heading and vertical movement where the scenario requires it. Test state boundaries for position discontinuities, sudden reversals and unsupported orientation jumps. Any intentional reset/teleport must be outside the accepted continuous demonstration and explicitly marked.

**M3.5 — Introduce bounded variation only after the reference sequence works.** Permit seeded variation in a small declared set of quantities, such as manoeuvre timing, chosen turn or target depth. Draw state-compatible values at defined events, not independently on every rendered frame. Log realised choices.

**M3.6 — Keep the animal in the accepted volume.** Reuse compatible domain constraints or choose a bounded scenario that avoids the edges. Do not introduce invisible position clamps, surface clipping or a second avoidance controller. Keep controller changes local to this test animal.

**M3.7 — Separate parameter provenance.** For each value, identify whether it is sourced from reviewed evidence, specified by an expert, an engineering test assumption or unresolved. No numerical values in this specification prescribe validated bottlenose physiology or wild behaviour.

**M3.8 — Record and compare actual runs.** Produce one deterministic reference scenario and three declared stochastic seeds, with a fresh-process repeat for each seed. Store GAMA outputs, versions, seed, model/configuration hashes and commands. Compare realised trajectories using the locked tolerances and document any nondeterminism.

### Deliverables

- Updated versioned `.gaml` model and parameter configuration
- `M3_MOVEMENT_MODEL_AND_PARAMETER_REGISTER.md`
- Recorded reference and seeded trajectories with repeatability results
- Time-series and path plots showing position, speed, heading, depth and state

### Acceptance criteria — Gate B

Actual GAMA executions complete the agreed scenario without unexplained discontinuities; position, speed, heading and depth are mutually consistent under the declared model; repeat runs satisfy the locked criteria; and all parameter evidence statuses are visible. A reviewer accepts the trajectories for animation integration, without this being interpreted as biological validation.

---

## Milestone 4 — Map behaviour and movement to visible body animation

### Objective

Make the dolphin's visible body motion agree with its trajectory and state while preserving the existing asset and material.

### Tasks

**M4.1 — Reuse the inspected animation path.** Use the approved existing clips, rig or procedural motion. Any required local adaptation must follow the M1 scope. Do not automatically install a new animation framework or generate a replacement animal.

**M4.2 — Define the state-to-pose mapping.** Document the supported visible response for steady swimming, turning, descent, submerged swimming and ascent. Distinguish world orientation from local torso, tail and fluke motion. A rigid root rotation alone does not demonstrate coordinated body animation.

**M4.3 — Preserve the calibrated asset.** Keep source scale, fixed orientation correction, mesh identity and material unchanged unless an approved animation adaptation requires a new working asset version. Never alter the preserved original. Record dependencies and licence provenance for the working copy.

**M4.4 — Synchronise motion with trajectory.** Use simulation-time-indexed controls for animation phase, blend weights and any speed-to-animation mapping. Keep mappings bounded and explicit. Do not assume a universal relation between speed and tail-beat frequency, or claim physically generated propulsion from a visual animation.

**M4.5 — Blend rather than snap.** Implement supported transitions between swimming and manoeuvre poses. Check loop boundaries, direction changes, startup, state re-entry and recovery from pause. Keep phase continuous unless an intentional reset is declared.

**M4.6 — Handle unsupported manoeuvres honestly.** Do not invent a biologically realistic bank, turn or dive pose by applying an arbitrary angle. Where the asset cannot provide a credible local response, mark that capability partial and seek a bounded refinement decision rather than calling a rigid proxy complete.

**M4.7 — Check deformation and contact.** Inspect unwanted stretching, disconnected geometry, self-intersection, mesh inversion, scale change and unintended movement of helper objects. Test above/surface-crossing/submerged portions of the planned path from an above-water camera. Underwater optical appearance remains subject to the fixed water preset's limitations.

**M4.8 — Review at useful views and speeds.** Provide top, side/oblique and close diagnostic views of the same recorded states, plus normal-speed playback. Close-ups diagnose deformation; they do not establish survey realism. Retain settings and state IDs for each reviewed example.

### Deliverables

- `M4_STATE_TO_ANIMATION_MAP.md`
- Versioned animation/controller configuration and any approved working-asset derivative
- Transition tests, pose snapshots and a review clip
- A capability matrix: supported, limited/proxy, unsupported

### Acceptance criteria — Gate C

The supported swimming and manoeuvre states show coordinated body motion; transitions and loops do not visibly snap; dynamic animation does not double world movement; asset scale/material remain preserved; and a named reviewer accepts the candidate for the integrated demonstration. Unsupported motion is not concealed in the pass summary.

---

## Milestone 5 — Demonstrate the full sequence and reproducible frozen snapshots

### Objective

Prove that the behaviour, movement and animation remain aligned through playback, capture and restoration.

### Tasks

**M5.1 — Run the complete reference sequence.** Play steady swimming → gradual turn → descent → submerged swimming → ascent → steady swimming using actual recorded GAMA output and the accepted animation map. Use one experimental animal and the unchanged `engineering_v1` water preset.

**M5.2 — Verify timing coherence.** Log simulation time, state, world transform, movement variables and animation controls together. Ensure slower rendering or communication delays cannot advance the animal independently. Test at two different presentation/update schedules while querying the same simulation timestamps.

**M5.3 — Declare snapshot points before acceptance capture.** Select at least six simulation timestamps covering the principal states and transitions. Include manoeuvre boundaries where discontinuities are most likely. This is an engineering coverage requirement, not a biological sampling design.

**M5.4 — Freeze complete state.** Capture the resolved position/orientation, relevant joint transforms or procedural deformation state, animation phase, blend weights, controller state, and required ocean/lighting state. Freeze must hold while the renderer settles or captures frames. Compare evaluated body state, not only the root transform.

**M5.5 — Replay and seek.** Recreate selected timestamps in the original order and a different order. Where a controller is history-dependent, restore its saved state or deterministically replay to the requested time; do not claim stateless seeking if it depends on missing history. Repeat selected snapshots after a fresh process/scene reload.

**M5.6 — Test interruption and restoration.** Exercise pause, resume, controlled stop, reset, missing-state freeze, removal of the bridge-owned actor and return to the saved baseline. Restore the recorded pre-test controller and ocean state rather than assuming every controller should always be running.

**M5.7 — Use the qualified image route.** Retain the supported HDR/EXR and fixed display-conversion path if that remains the accepted configuration. Do not reinterpret generated display PNGs as qualified native LDR output. Preserve camera, lighting, exposure and render controls for matched comparisons.

**M5.8 — Check bounded resource use.** Record the tested resolution, runtime, sampled GPU memory and actual retry/restart behaviour. Retain the existing guards. State if only a smaller workload succeeded. Do not scale to native survey resolution or remove safety limits just to finish.

**M5.9 — Package the demonstration.** Produce a normal-speed video or reproducible playback equivalent, a labelled snapshot contact sheet, motion/phase plots and a machine-readable state-comparison report. Quantify root and pose/deformation discrepancies against the locked tolerances. RGB identity is a separate property and is not inferred from matching state records.

### Deliverables

- `M5_INTEGRATED_DEMONSTRATION.md`
- Reference playback/recording and at least six traceable snapshot records
- Timing, capture-order, reload and lifecycle test results
- Resource observations and recorded limitations

### Acceptance criteria

The full supported sequence plays coherently; queried states and body configurations reproduce within the declared criteria despite changed presentation cadence or capture order; freeze/pause do not advance animation; restart/seek rules are demonstrated; and cleanup preserves unrelated MARLIN functionality.

A five-GSD sweep is not required for this milestone. The requirement is compatibility with future frozen-state capture, not a new dataset experiment.

---

## Milestone 6 — Review, preserve and close out

### Objective

Release a bounded, inspectable demonstration and state exactly what has and has not been validated.

### Tasks

**M6.1 — Run regression checks.** Execute the applicable existing GAMA/bridge, camera, wave-sampler, ocean-material and controller tests, plus this sprint's new tests. Record actual counts, failures and skips. Verify historical experiment and accepted-water pins remain unchanged.

**M6.2 — Verify scene coexistence and rollback.** Restore the standard demonstration, confirm unrelated animals/controllers remain functional and remove the experimental actor without deleting shared assets. Verify rollback to the preserved baseline configuration.

**M6.3 — Obtain named visual review.** Provide the complete sequence and traceable state/pose comparisons to Adil and, where available, Ger or a nominated reviewer. Record reviewer identity, date, evidence version and comments. Pending review remains pending; Codex cannot approve its own visual or biological suitability.

**M6.4 — Record three separate assessments.** Engineering correctness, visual plausibility and biological support must have independent statuses. Review sources for behavioural values and anatomical pose claims; do not turn an engineering assumption into empirical evidence because the motion looks smooth.

**M6.5 — Preserve the implementation and evidence.** Package model/configuration versions, adapter/animation changes, commands, runtime/dependency versions, seed records, realised trajectories, state/pose snapshots, comparison results and permitted visual outputs. Record hashes and any external dependencies or missing portable assets.

**M6.6 — Preserve unsuccessful attempts.** Retain failed/skipped outcomes and explain accepted amendments. Use separate output locations for retries. Do not overwrite a failure or change a locked tolerance after inspection without recording a revised protocol and new run.

**M6.7 — Write the closeout.** Link each claimed completion to actual evidence. Identify the exact scope, remaining proxies, resource constraints and any broken requirement. Add reproducibility and rollback instructions tested within the available environment.

**M6.8 — Make an explicit next-use decision.** State whether the result is accepted for bounded engineering/visual demonstrations, eligible for a specified later research use after review, or blocked. No dataset generation, ML training or species expansion starts automatically after closeout.

### Deliverables

- `M6_SPRINT_CLOSEOUT.md`
- `REPRODUCTION_AND_ROLLBACK.md`
- Named review record and final evidence manifest
- Updated implementation/parameter provenance and regression summary

### Acceptance criteria — Gate D

The declared engineering tests pass, the selected sequence receives named visual acceptance, preservation/rollback checks pass, and the documented package allows the same bounded demonstration to be reproduced. Biological support may remain provisional, but the report must state that plainly and must not claim approval for a biological study without a corresponding review decision.

---

## 3. Acceptance matrix and evidence rules

| Assessment | Required evidence | What a pass does not establish |
|---|---|---|
| Engineering correctness | Actual GAMA execution; faithful state mapping; single ownership; timing coherence; constrained trajectories; repeatable root and body state; recovery tests | Ecologically representative behaviour or physically simulated propulsion |
| Visual plausibility | Named review of the sequence, transitions and snapshots; absence of unexplained pose snapping, gross deformation or incoherent movement | Measured natural activity frequencies, validated physiology or operational survey realism |
| Biological support | Parameter/pose provenance and an explicit expert judgement for a stated use | General validity across populations, ages, conditions or all dolphin activities |
| Research-capture readiness | A later explicit decision covering poses, optics, visibility, labels and the target experiment | Automatically satisfied by this animation sprint |

Use the statuses `planned`, `implemented`, `executed`, `passed`, `failed`, `skipped`, `blocked` and `provisional` accurately. An implemented test is not an executed test; a passing proxy is not a validated biological model.

Every accepted test record should identify its inputs, expected result, tolerance or review rule, actual result, output path and code/configuration version. Preserve failures and justify amendments. Do not use completion percentages as a substitute for these records.

### Numerical criteria to freeze before acceptance runs

The M2 tolerance record must cover the applicable world-position error, orientation error, simulation-time agreement, path/movement bounds and evaluated body-pose or mesh-deformation comparison. Define how circular angles and animation phase are compared. Specify handling of floating-point differences and interpolation at queried timestamps.

For visuals, record concrete review questions: does local body motion agree with the manoeuvre, do transitions snap, does the asset deform implausibly, and is the same pose reproduced at the same recorded time? Do not invent a universal numerical realism score.

---

## 4. Proposed evidence organisation

Reuse an established experiment folder if it already serves this exact sprint. Otherwise, a suitable location is:

```text
experiments/gama_dolphin_behaviour_v1/
    README.md
    baseline/
    specification/
    config/
    gama/
    trajectories/
    animation/
    snapshots/
    captures/
    qa/
    reviews/
    M1_ASSET_AND_CONTROLLER_AUDIT.md
    M2_STATE_OWNERSHIP_AND_TIME_CONTRACT.md
    M3_MOVEMENT_MODEL_AND_PARAMETER_REGISTER.md
    M4_STATE_TO_ANIMATION_MAP.md
    M5_INTEGRATED_DEMONSTRATION.md
    M6_SPRINT_CLOSEOUT.md
    REPRODUCTION_AND_ROLLBACK.md
```

These are suggested names, not claims about existing files. Avoid duplicated authoritative copies of runtime source. Implement reusable runtime changes in the canonical source tree and reference them from the evidence package.

Do not commit installed SDKs, virtual environments, caches, model checkpoints or large generated media merely to make the package look complete. Retain appropriate media in the established artifact store with manifests/hashes and lawful asset provenance. A hash is not a substitute for preserving the actual file where reproduction requires it.

---

## 5. Human review gates and execution order

| Gate | When | Decision |
|---|---|---|
| A | After M1 | Accept the actual asset/controller audit and smallest implementation plan before changing behaviour or animation |
| B | After M3 | Accept the constrained, reproducible trajectories as suitable inputs for body-animation work |
| C | After M4 | Accept supported motion/pose mappings and identify any limitations before the integrated demonstration |
| D | After M6 | Accept the bounded engineering/visual result and record biological and future-research status separately |

M2 precedes acceptance of M3 and M4 because both depend on its ownership and time contract. Preserve the order **audit → contract → movement → body animation → integrated demonstration → closeout**. Do not open unrelated unfinished historical milestones as hidden requirements of this sprint.

When a gate needs human review, stop the affected implementation and present the evidence and specific decision required. Do not invent approval. A blocker should identify what failed, which evidence exists, its effect on this sprint and the smallest proposed remedy.

---

## 6. Final definition of done

The sprint is complete for its declared engineering/visual scope when:

1. The selected dolphin asset, current rig/animation and competing controllers have been audited and the baseline preserved.
2. Coordinate, unit, depth-reference, ownership and simulation-time rules are explicit and tested.
3. Actual GAMA executions generate the agreed constrained sequence, with recorded seeded variation and repeatability evidence.
4. The dolphin's supported body animation agrees with its movement, including smooth state transitions and no duplicated root motion.
5. The complete sequence is demonstrated and selected evaluated body states can be frozen, replayed and restored within predeclared criteria.
6. The accepted water, camera contracts and historical experiment records remain unchanged; applicable regression and rollback checks pass.
7. A named reviewer accepts the bounded visual demonstration, with any unsupported behaviour clearly identified.
8. Model/configuration provenance, commands, evidence and reproduction instructions are preserved.
9. The closeout separates engineering correctness, visual plausibility and biological support and makes no unsupported ecological or survey-validity claim.
10. No new species, ocean development, production dataset or ML training has been introduced under this sprint.

> **Success is one coherent, reproducible dolphin sequence—not a larger feature list.**

Stop after the closeout. Use the reviewed result to decide the next scientific or development increment rather than automatically expanding the scope.
