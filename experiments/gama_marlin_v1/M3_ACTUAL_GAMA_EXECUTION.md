# Milestone 3 actual GAMA execution report

Sprint: GAMA–MARLIN Behavioural Integration and Validation.
Milestone: Generate trajectories from an actual GAMA model.
Executed on 8 October 2026. Status: **Passed** for the bounded engineering model.

Implemented and executed a versioned GAML model with one harbour porpoise agent
using GAMA's FSM architecture. Two separate headless processes each generated 41
timestamped states over 20 simulated seconds, using seed 184729 and 0.5-second
steps. Both produced the full declared state sequence and continuous motion.
The Python tooling converted actual GAMA variables into the existing v2 exchange
contract and checked their values; it did not generate replacement trajectories.

## Deliverables

- [Runnable GAMA model](../../integrations/gama/porpoise_behaviour.gaml).
- [Pinned engineering configuration](porpoise_model_config.json).
- [Repeatable record-first procedure and model explanation](../../integrations/gama/PORPOISE_RECORD_FIRST.md).
- [Recorder and acceptance checker](../../tools/gama_porpoise.py).
- [Run A execution provenance](trajectories/m3_seed_184729_a/execution.json),
  [raw GAMA XML](trajectories/m3_seed_184729_a/raw/simulation-outputs0.xml) and
  [v2 trajectory](trajectories/m3_seed_184729_a/trajectory.json).
- [Run B execution provenance](trajectories/m3_seed_184729_b/execution.json),
  [raw GAMA XML](trajectories/m3_seed_184729_b/raw/simulation-outputs0.xml) and
  [v2 trajectory](trajectories/m3_seed_184729_b/trajectory.json).
- [Verification results](qa/m3_validation.json) and
  [synthetic parser/acceptance test log](qa/m3_export_tests.log).

Each run retained its executed model copy, configuration, XML experiment plan,
launcher log, GAMA console output, original raw XML, converted state sequence,
validation errors and execution metadata. Commands, runtime version/commit/JDK,
actual exported seed and model/configuration/output hashes are recorded.
The actual engine was installed GAMA 2025.6.4 with JDK 21.0.7+6.
The model SHA-256 was
`fff5b482af65152789d161c2a00af61680c05bd9a8f0d2b53f83072ddc03020f`.

## Executed acceptance checks

The two recorded commands, each launching a fresh GAMA process, were:

```bash
python3 -B tools/gama_porpoise.py --run-id m3_seed_184729_a
python3 -B tools/gama_porpoise.py --run-id m3_seed_184729_b
```

Each run exited successfully and exported exactly one GAMA agent on every step.
Observed transitions were:

| Step | Simulation time in seconds | Exported state |
| --- | ---: | --- |
| 0 | 0 | `surface` |
| 4 | 2 | `shallow_swim` |
| 12 | 6 | `descent` |
| 20 | 10 | `submerged_swim` |
| 28 | 14 | `ascent` |
| 36 | 18 | `surface` |

The final recorded sample was step 40 at 20 s. Root depth ranged from 0.2 to
3.0 m below the fixed mean sea plane. Horizontal speed was 0.5 m/s on an 8 m-radius
circle, with a seed-generated initial phase of 304.8546178781564 degrees.
Depth changes used continuous cubic easing between the declared levels.
All these behavioural values are **engineering assumptions**, not species
measurements or scientifically approved behaviour.

Both runs passed every v2 boundary and engineering trajectory check. Observed
maximum errors were the same in both runs:

| Check | Declared tolerance | Maximum observed error |
| --- | --- | --- |
| Circle radius | 1e-8 m | 8.89e-16 m |
| Per-step horizontal chord length | 1e-8 m | 7.11e-15 m |
| Tangent heading | 1e-8 degrees | 2.85e-14 degrees |
| Declared depth profile | 1e-8 m | 0 m |
| Simulation clock | 1e-9 s | 0 s |

Initial-phase position reconstruction also passed the 1e-8 m tolerance on every
sample. Exported constant speed and configuration values matched exactly.
State labels and transition times matched the declared schedule. The tolerances
were pinned in configuration before execution.

Canonical state sequences matched exactly across the two fresh processes after
excluding only `run_id`, which intentionally differed between executions.
The common canonical SHA-256 was
`5c602f67e1c2bb7d551a23785b8bc1d355fc6fd17e84d8fc4c8257cd1ad82fb2`.
Raw XML and full v2 trajectory hashes differ because they retain each run's own
identity. Execution timestamps and machine paths are outside the compared states.

Verification command:

```bash
python3 -B experiments/gama_marlin_v1/qa/verify_m3.py
```

This reparsed both retained raw outputs, checked their converted states and
validation reports, verified model/configuration/plan/output hashes and equality,
and ran **11 passing synthetic parser/acceptance tests**. These rejection fixtures
remain explicitly separate from the actual GAMA-generated evidence. Tests covered
missing/duplicate variables, malformed/truncated/reordered steps, wrong seed/run
identity, extra agents, changed configuration/phase, unsupported v2 values,
nonfinite values, incorrect state/depth/motion and output overwrite refusal.

## Asset selection and preservation

Retained the existing Pilot harbour porpoise static candidate identified by
`experiments/gsd_pilot_v1/wildlife/harbour_porpoise.json`. Its USD SHA-256 matched
`1d5e96c29b976e07a434381db5e58aae95198cec91a1738c2176a0d4ff7346ef`
before each GAMA execution. The original calibration record hash was recorded
with each run. Asset selection is recorded for subsequent MARLIN rendering;
GAMA owns numerical behaviour and does not load or convert that USD model.

The final verification confirmed all 915 protected M1 files, all 18 sealed M2
outputs and both Pilot checkpoint copies remained unchanged. Existing GAMA
bottlenose fixtures, bridge code, rendering service, scene, ocean, camera and
autonomous controllers were not modified. No HTTP call, Kit restart, scene actor
acquisition, capture or ML operation was used in this milestone.

## Limits and next milestone

M3 demonstrated actual GAMA generation and a repeatable record-first procedure.
It did not establish biological suitability, support for the asset's rendered
surface/dive poses, or faithful application of this new porpoise sequence in Kit.
The static mesh remains the previously reviewed Pilot proxy. No animal rigging,
species calibration or biological approval was invented.

The two-process one-seed check does not complete M5's ten-seed workload or human
review. Scene replay, control ownership, actual composed transforms, failure
recovery and coexistence for the porpoise remain M4. The generated v2 trajectory
is now available as that milestone's input; the existing v1 actor endpoint must
not be used for it.

Acceptance outcome: **Passed**. Fresh actual GAMA execution generated the documented
transitions and continuous movement, and retained evidence links the runnable
model to its v2 state sequence. Biological suitability remained **provisional**.
