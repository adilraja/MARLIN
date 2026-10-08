I would make the next sprint **“GAMA–MARLIN Behavioural Integration and Validation”**, with **eight explicit milestones**.

The objective should be:

> **Demonstrate that a real, versioned GAMA model can generate controlled animal behaviour, transfer that behaviour correctly into MARLIN, and produce reproducible five-GSD image sets without changing the underlying biological scene.**

This is a prerequisite for expanding the **behaviour-driven experiment**, not an instruction to build an entire marine ecosystem. Pilot v1 should remain unchanged: it already demonstrated the end-to-end imaging and detection workflow, while explicitly retaining limited biological states and provisional camera assumptions.[^pilot-scope][^pilot-limitations]

The following is ready to give to Codex.

# Next sprint: GAMA–MARLIN integration

## Milestone 1 — Preserve Pilot v1 and audit the existing GAMA work

**Objective:** Establish exactly what exists before making changes.

Preserve the completed pilot’s code, datasets, annotations, splits, predictions, metrics and manifests. Verify and back up the trained checkpoint separately; the final report says its bytes are local and Git-ignored, rather than stored in Git.[^pilot-checkpoint]

Inspect the existing GAMA integration and classify each component as **implemented and tested**, **implemented but unverified**, **fixture/mock**, or **missing**. In particular, identify whether the recorded trajectories actually came from a GAMA model or were constructed elsewhere.

Record the installed GAMA version, model files, existing adapter, transport, relevant endpoints and previous integration tests. Reuse working components rather than building a second bridge.

**Deliverable:** `M1_BASELINE_AND_GAMA_AUDIT.md`, with a preserved-output manifest.

**Acceptance criterion:** The team can clearly distinguish what already works from what this sprint must implement, and Pilot v1 remains intact.

---

## Milestone 2 — Define the state contract and ownership rules

**Objective:** Remove ambiguity about what GAMA controls and what MARLIN controls.

Write and validate a small, versioned exchange schema containing:

```text
schema_version
run_id
step_index
simulation_time_s
simulation_step_s
seed
agent_id
species
behavioural_state
position / horizontal position
heading
speed
vertical reference and depth / height
```

Specify coordinate axes, heading signs, units and angle conventions. Use SI units at the bridge boundary, and inspect MARLIN’s actual current unit configuration rather than assuming a scale factor.

**Make vertical positioning unambiguous.** Choose explicitly whether depth is relative to mean sea level or the instantaneous wave surface. Do not let absolute Y and relative depth independently control the same animal. If MARLIN resolves surface-relative depth into world Y, record the ocean state used and the resulting position.

Define ownership as follows:

| Responsibility | Owner |
|---|---|
| Behavioural state, trajectory, heading, speed and depth evolution | GAMA |
| Asset selection and deterministic state-to-pose mapping | MARLIN |
| Camera, projection, lighting, water appearance and capture | MARLIN |
| Capture scheduling and snapshot selection | Experiment orchestrator |

For a GAMA-controlled animal, disable competing autonomous MARLIN movement and diving controllers. Preserve their operation for unrelated demonstration animals.

**Deliverable:** Exchange schema, coordinate/ownership specification and schema-validation tests.

**Acceptance criterion:** A received state has one interpretation and one behavioural owner. Invalid or contradictory states are rejected before changing the scene.

---

## Milestone 3 — Generate trajectories from an actual GAMA model

**Objective:** Prove that GAMA—not a hand-authored replay file—is generating the behaviour.

Use **one existing harbour-porpoise asset**, subject to the audit confirming that it remains the appropriate available target. Do not add birds, pods or additional species during this milestone.

Implement or verify a small `.gaml` model with a demonstration sequence such as:

```text
surface
   → shallow_swim
   → descent
   → submerged_swim
   → ascent
   → surface
```

GAMA provides a finite-state-machine architecture suitable for expressing states and transitions. The biological rules and parameters still have to be supplied and justified by the project. ([gama-platform.org](https://gama-platform.org/wiki/ControlArchitecture))

Start with a **record-first workflow**:

```text
Run GAMA → export timestamped states → replay those states in MARLIN
```

GAMA supports headless execution, so this need not depend on an open graphical interface. If the existing implementation uses GAMA Server, preserve it where appropriate; its documented interface is WebSocket-based, so do not assume it is the same protocol as MARLIN’s HTTP service. ([gama-platform.org](https://gama-platform.org/wiki/RunningHeadless?utm_source=chatgpt.com))

Store the model hash, configuration, actual seed, runtime version, execution command and state-sequence output.

**Deliverable:** Runnable GAMA model, repeatable launch procedure and a trajectory file demonstrably generated by that model.

**Acceptance criterion:** A fresh execution produces the documented state transitions and continuous movement. Manually constructed trajectories remain separate test fixtures.

---

## Milestone 4 — Verify state transfer, control ownership and recovery

**Objective:** Establish that MARLIN faithfully applies GAMA’s output.

Test known positions, all four cardinal headings, and the chosen vertical-reference convention. Compare the expected state with the **actual composed MARLIN transform**, not only the adapter’s internal variables.

Declare numerical tolerances before running the acceptance tests and report measured errors.

Then test the failure cases: duplicate updates, out-of-order steps, malformed payloads, unknown agents, reset, interrupted replay and reconnection where applicable. Duplicate updates must not create duplicate animals or advance behaviour twice.

Define what happens when updates stop. For this sprint, use an explicit **freeze-and-report** policy rather than silently handing control back to the autonomous swimmer.

Test coexistence with the existing populated demonstration scene, and clean removal of only the bridge-owned animal. Other agents must retain their controllers.

**Deliverable:** Automated adapter tests, transform-comparison results and a short visual demonstration.

**Acceptance criterion:** One GAMA-controlled animal moves correctly, never has two competing behavioural controllers, and can be stopped or removed without damaging the rest of MARLIN.

---

## Milestone 5 — Validate reproducibility and review the behavioural model

**Objective:** Separate “repeatable software” from “defensible animal behaviour.”

### Engineering checks

As a proposed acceptance workload, run **ten declared seeds**, with at least **three seeds repeated in fresh GAMA processes**.

Compare canonical state sequences under the same pinned model, configuration and runtime. Exclude wall-clock timestamps and machine-specific paths from the state comparison. Different seeds should generate variation in the intended stochastic variables.

Do not treat a seed alone as proof of reproducibility. GAMA’s documentation specifically warns that parallel execution, display-side randomness and asynchronous interactions can affect repeatability. ([gama-platform.org](https://gama-platform.org/wiki/Ensure-model-reproducibility))

### Behavioural checks

Produce a parameter register covering state durations, speeds, turning, depth evolution and pose constraints. Label each parameter as **literature-supported**, **expert-specified**, **engineering assumption**, or **unresolved**.

Measure the generated state durations, transitions, depths, speeds and turning rates. Check them against the declared model constraints. Review representative trajectories and rendered poses with a named human reviewer.

Do not interpret deliberately balanced state coverage as an estimate of how often wild animals occupy those states.

**Deliverable:** Reproducibility results, behavioural parameter register, trajectory plots and a review record.

**Acceptance criterion:** Report two separate outcomes:

- **Engineering reproducibility:** passed or failed.
- **Biological suitability:** approved for a stated limited use, provisional, or blocked.

Codex must not award itself biological approval merely because the software tests pass.

---

## Milestone 6 — Freeze one GAMA state across all five GSD captures

**Objective:** Preserve experimental pairing despite rendering delays or capture order.

At a selected GAMA step, resolve and freeze the animal’s position, orientation, behavioural state, asset pose and animation phase. Freeze the ocean and lighting state relevant to that snapshot as well.

Capture:

```text
0.5, 1, 2, 3 and 4 cm/px
```

without advancing biological or environmental time.

Store a **resolved scene-state hash** separately from the camera-condition metadata. Repeat selected captures in different GSD orders and with artificial delays. These must not change the underlying animal state.

Preserve the declared imaging protocol. Do not reposition the animal between conditions merely to force identical frame coordinates. Also retain the fact that Pilot v1’s GSD sweep changed camera height and footprint; do not silently relabel it as a fixed-footprint experiment.[^pilot-camera]

Use the previously validated, manageable-resolution capture route first. Full native HiDef or Sony rendering is **not** a prerequisite for this integration check.

**Deliverable:** Paired-capture manifests, state-hash comparisons and capture-order/delay tests.

**Acceptance criterion:** Every image in a paired set comes from the same resolved biological and environmental snapshot. Pixel-identical RGB reproduction is a separate test, not something inferred from matching state hashes.

---

## Milestone 7 — Produce a small GAMA-driven capture and annotation test set

**Objective:** Prove the integrated workflow without starting another large experiment.

Use a bounded acceptance set:

| Component | Proposed minimum |
|---|---:|
| Independent GAMA runs | 5 |
| Snapshots selected per run | 3 |
| GSD conditions per snapshot | 5 |
| Target-present captures | 75 |
| Matched target-absent captures | 75 |

This is an **engineering test set**, not a statistically powered wildlife study.

Declare snapshot-selection times or state-based rules before inspecting the rendered images. Record selection failures and unsuitable states rather than silently choosing attractive replacements.

For every capture, verify the source GAMA run and step, resolved scene state, camera configuration, annotation semantics and output hashes. Keep **all snapshots from a related trajectory or encounter**, their five GSD versions and their negative counterparts in the same dataset split.

Do not confuse *submerged or invisible* with *target absent*. Create negative counterparts by an explicitly recorded target-removal operation. Keep physically present but poorly visible animals distinguishable in metadata.

Preserve the annotation limitations: Pilot v1 used direct amodal mesh boxes, not exact visible or refracted underwater outlines. Do not claim that adding GAMA resolves that distinction.[^pilot-pixels][^pilot-annotations]

**Deliverable:** Small image set, labels, contact sheets, trajectory-group split manifest and QA report.

**Acceptance criterion:** Each accepted image is traceable back to an actual GAMA-generated state, annotations are honestly described, pairing is intact and related trajectories do not cross splits.

---

## Milestone 8 — Complete the regression review and expansion decision

**Objective:** Decide whether MARLIN is ready for a larger behaviour-conditioned experiment.

Run the existing MARLIN regression and camera-contract tests, plus the new bridge and capture tests. Confirm that Pilot v1’s preserved artifacts are unchanged and that the standard marine demonstration still operates after cleanup.

In parallel, close the **read-only pilot audit** items identified previously: document the detector’s complete input-resizing path, AP aggregation convention and amodal-box interpretation. Do not retrain the detector or overwrite the completed test results during this sprint.

Produce one final report with an evidence-backed status for every milestone:

```text
Implemented
Executed
Passed
Failed
Blocked
Provisional
```

Every “passed” entry must link to the command, test result or output that supports it.

The final decision must distinguish:

| Decision | Required basis |
|---|---|
| **Ready for further engineering tests** | Actual GAMA execution, correct transfer, deterministic state replay and paired capture verified. |
| **Ready for a limited behaviour-conditioned study** | Engineering checks pass, supported asset states are reviewed, and the behavioural assumptions are accepted for a clearly stated scope. |
| **Not ready for expansion** | Material timing, ownership, pose, annotation or biological-evidence gaps remain. |

**Deliverable:** `GAMA_MARLIN_SPRINT_REPORT.md`, reproduction instructions, regression evidence and an explicit expansion recommendation.

**Acceptance criterion:** The team can reproduce the engineering demonstration and see precisely which biological claims remain unsupported.

# Scope limits for the sprint

Do **not** add pods, flocking, migration, new species, a replacement ocean, additional camera models, large-scale dataset generation or new ML training.

Keep the petrel’s existing asset and results preserved, but do not make full bird rigging or flight modelling a prerequisite for proving this first cetacean-based integration.

The milestone order is:

**Audit → contract → actual GAMA execution → faithful transfer → reproducibility and behavioural review → frozen GSD capture → small test set → expansion decision.**

**The sprint is successful when we can trace a rendered wildlife image back to a reproducible GAMA state—and state clearly whether the behaviour is merely an engineering demonstration or suitable for a defined research use.**

[^pilot-scope]: *MARLIN GSD pilot v1 — final sprint report*, `M8_FINAL_REPORT.md`, lines 3–8.
[^pilot-limitations]: *MARLIN GSD pilot v1 — final sprint report*, `M8_FINAL_REPORT.md`, lines 86–100.
[^pilot-checkpoint]: *MARLIN GSD pilot v1 — final sprint report*, `M8_FINAL_REPORT.md`, lines 106–114.
[^pilot-camera]: *MARLIN GSD pilot v1 — final sprint report*, `M8_FINAL_REPORT.md`, lines 86–90.
[^pilot-pixels]: *MARLIN GSD pilot v1 — final sprint report*, `M8_FINAL_REPORT.md`, lines 53–62.
[^pilot-annotations]: *MARLIN GSD pilot v1 — final sprint report*, `M8_FINAL_REPORT.md`, lines 91–96.
