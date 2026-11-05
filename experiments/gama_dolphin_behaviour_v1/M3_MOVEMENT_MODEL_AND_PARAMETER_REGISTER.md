# M3 — Smooth, constrained GAMA movement and parameter register

Sprint: **MARLIN — GAMA–Omniverse Bottlenose Dolphin Behaviour and Animation**.
Milestone: **Implement smooth, constrained GAMA movement**.
Technical execution completed: **5 November 2026**. **Gate B remains pending**;
no trajectory acceptance or authority to begin body-animation work was invented.

## Executed result

A versioned bottlenose GAML model was adapted from the existing porpoise model's
explicit-clock, single-agent, record-first structure. Eight actual GAMA executions
completed: a non-stochastic reference and its repeat, followed by three declared
stochastic seeds and one fresh-process repeat of each. Each run retained 297
samples at 0.25 s over 74 s; 2,376 samples were preserved in total.

Every primary/repeat pair had identical canonical v3 state bytes and realised
choices. Only `run_id` was excluded from canonical state comparison; step/time,
seed, state, position, attitude, speeds, transition information and phase clocks
were retained. Raw XML, logs and process metadata were preserved separately and
were not asserted byte-identical. Three stochastic seeds produced three distinct
recorded choices and paths. Seeded runs began only after both reference executions
and their repeat comparison passed.

All model parameters are engineering test assumptions. No physiological, wild
behaviour, propulsion, underwater optics or rendered body-animation validation was
performed. Gate B reviews these trajectories as inputs for later animation work.

## Canonical implementation and evidence

- Model: `integrations/gama/bottlenose_constrained_v1.gaml`.
- Runner/exporter: `tools/gama_bottlenose.py`.
- Independent trajectory acceptance oracle: `tools/analyze_gama_bottlenose.py`.
- Negative-case and boundary tests: `tools/test_gama_bottlenose.py`.
- Parameters/provenance: `config/m3_parameters_v1.json`.
- Pre-run movement bounds: `config/m3_acceptance_v1.json`.
- Workload and exact input hashes: `qa/m3/locked_plan.json` and
  `qa/m3/implementation_lock_attempt01.json`.
- Actual executions: `trajectories/m3_*01/`, each with model snapshot, effective
  parameter exports, XML plan, raw GAMA XML, logs, v3 states, diagnostics, analysis
  and execution metadata. Snapshots are execution records; the canonical model
  remains in `integrations/gama`.
- Summary/repeatability: `qa/m3/campaign_analysis.json`.
- Executed state joins: `qa/m3/boundary_audit.json` (40 boundaries across eight runs).
- Review packet: `reviews/GATE_B_REVIEW.md`.

The current sprint and explicit authorisation for M3 superseded the historical
GSD freeze note in `integrations/gama/GEMINI.md`. Existing GSD experiments,
porpoise model, M1/M2 evidence and accepted water work were preserved.

## State machine and continuous controls

The equivalent timed state machine evaluates its active phase from elapsed
simulation seconds. It does not depend on render frames, communication timing or
wall clock. Recorded state labels describe the controls actually executed.

| Time interval (s) | Executed state | Control and exit |
| --- | --- | --- |
| [0,10) | `steady_swim` / initial episode | Held still through 2 s; ramped to cruise over 2–6 s; continued until elapsed time 10 s. |
| [10,22) | `turn` | Applied the chosen positive heading change with a quintic ramp; ended at 22 s. |
| [22,38) | `descent` | Moved from initial depth to the chosen target with a quintic depth curve; reached the target at 38 s. |
| [38,48) | `submerged_swim` | Held target depth and the completed heading; ended at 48 s. |
| [48,64) | `ascent` | Returned along a quintic depth curve to initial depth; completed at 64 s. |
| [64,74] | `steady_swim` / final episode | Continued cruise until 68 s; ramped down over 68–72 s; held still through the final sample. |

For normalized phase time u, the ramp is `q(u)=6u^5-15u^4+10u^3`, with
`q'(u)=30u^2(1-u)^2`. Speed, turn angle and depth use this shape in their relevant
phases. Their values and first/second ramp derivatives join continuously.
The last observation is right-censored at 74 s; the final state has no subsequent
transition in this demonstration. Initial/final steady labels include declared
stationary holds; neither label asserts breathing or a biologically validated
surface behaviour.

`speed_mps` means instantaneous **horizontal** speed. The horizontal velocity is
`[speed*sin(heading), speed*cos(heading)]` in the M2 X/Z metre frame. Horizontal
position advances by the declared endpoint trapezoidal rule:

```text
p[i] = p[i-1] + dt * (v[i-1] + v[i]) / 2
```

Depth is evaluated analytically from its quintic, and upward velocity is its
negative derivative. Pitch is the trajectory tangent `atan(v_up/speed)` in degrees
while moving. At zero speed, pitch is explicitly zero and the defined heading is
retained. Roll is zero throughout; no arbitrary banking pose was invented.
The 3D speed is `hypot(horizontal_speed, vertical_velocity)` and is checked
separately. Per-sample speed is not incorrectly equated with an interval secant.
The oracle independently checks the integration residual, analytic depth and
vertical velocity, tangent pitch, state timing and movement limits.

The explicit SI variables are authoritative for the exchange; native GAMA
`location` and geographic/display coordinates do not independently drive the
output. This preserves the M2 local right-handed frame, +Y up, heading 0° toward
+Z and 90° toward +X. Depth is below fixed mean sea level at Y=0. No wave sampling,
position clamping, surface clipping, second avoidance controller or accepted-path
teleport was used. The complete path stays in the predeclared [-80,80] m X/Z,
[0,4] m depth volume without an edge correction.

M2's two-sample, linear/shortest-angle presentation remains the declared replay
interpolation. Sampled secants and that presentation curve are not described as
an exact reconstruction of all between-sample continuous derivatives.

## Phase and bounded stochastic variation

Animation phase remained a recorded control only. At each sample, the clock was
re-anchored continuously using the previous recorded rate and elapsed step. The
rate was 0.8 cycles/s while moving and zero at zero horizontal speed. This
constant-rate version has no hidden speed-dependent accumulator. Every clock
passed the existing v3 continuity validator; identical timestamp states/phase were
retained across repeats. No clip or body pose was evaluated or bound by M3.

Variation was enabled only after the reference sequence passed. Exactly three
explicit variation draws occurred at initialization, after setting and exporting
the requested RNG seed: turn angle, target depth, cruise speed, in that order.
The choices remained fixed for the entire run. The counter describes these
model-defined draws, not internal GAMA bookkeeping. No frame-wise random walk,
per-step redraw or seed remapping was introduced. Positive seeds 1, 42 and 184729
were declared before execution; seed zero was outside this accepted workload.

| Scenario / seed | Realised turn (degrees) | Target depth (m) | Cruise speed (m/s) | Fresh-process repeat |
| --- | --- | --- | --- | --- |
| Reference | 75.000000 | 3.200000 | 0.800000 | Exact |
| 1 | 80.480243 | 3.428032 | 0.801757 | Exact |
| 42 | 83.258726 | 3.459525 | 0.792622 | Exact |
| 184729 | 81.936368 | 3.406631 | 0.799684 | Exact |

## Parameter evidence register

The complete machine-readable register gives every value an explicit
`engineering_test_assumption` status and basis. **None was marked as reviewed
biological evidence or expert-specified animal physiology.** Animal-specific
validation of speeds, turn/dive limits, phase/frequency relationships and poses
remains unresolved for biological or survey use.

| Parameter | Value | Units | Evidence status |
| --- | --- | --- | --- |
| `step` | 0.25 | s | Engineering test assumption |
| `start_x_m` | -10.0 | m | Engineering test assumption |
| `start_z_m` | -15.0 | m | Engineering test assumption |
| `initial_heading_deg` | 350.0 | degrees | Engineering test assumption |
| `steady_s` | 10.0 | s | Engineering test assumption |
| `turn_s` | 12.0 | s | Engineering test assumption |
| `descent_s` | 16.0 | s | Engineering test assumption |
| `submerged_s` | 10.0 | s | Engineering test assumption |
| `ascent_s` | 16.0 | s | Engineering test assumption |
| `final_steady_s` | 10.0 | s | Engineering test assumption |
| `initial_depth_m` | 0.2 | m | Engineering test assumption |
| `target_depth_m` | 3.2 | m | Engineering test assumption |
| `cruise_speed_mps` | 0.8 | m/s | Engineering test assumption |
| `turn_angle_deg` | 75.0 | degrees | Engineering test assumption |
| `speed_ramp_s` | 4.0 | s | Engineering test assumption |
| `stationary_hold_s` | 2.0 | s | Engineering test assumption |
| `turn_spread_deg` | 10.0 | degrees | Engineering test assumption |
| `depth_spread_m` | 0.4 | m | Engineering test assumption |
| `speed_spread_mps` | 0.1 | m/s | Engineering test assumption |
| `animation_rate_hz` | 0.8 | cycles/s | Engineering test assumption |
| `initial_phase_cycles` | 0.25 | cycles | Engineering test assumption |

`enable_variation=false/true`, positive requested seeds and run IDs were execution
controls. Quintic coefficients and their derivative maxima were mathematical
choices. The state order, single-agent scope, numerical limits and volume were
engineering requirements/assumptions. Realised choices and trajectories were
executed observations, not additional biological parameter sources.

## Locked numerical criteria and observed results

M2's original tolerance record was not changed. M3 added scenario bounds and
velocity tolerances in a separate record before any GAMA invocation, retaining
the M2 position/angle/time/phase precision gates. Full-input hashes were locked
before execution and checked again after every run. The entire declared variation
box was also bounded analytically before execution: max q' = 1.875,
max |q''| = 10/sqrt(3). Speed-ramp, turn and depth manoeuvres do not overlap,
allowing conservative vector-acceleration bounds. Integrating the speed ramps
and holds bounds total horizontal travel by 59.4 m, leaving a margin to the volume.

| Quantity | Locked limit | Largest sampled value across executions |
| --- | --- | --- |
| Horizontal speed | 1.0 m/s | 0.801757 m/s |
| Full 3D speed | 1.1 m/s | 0.886517 m/s |
| Horizontal/vector acceleration | 0.5 / 0.6 m/s² | 0.371927 m/s² |
| Heading change rate | 15 degrees/s | 12.994127 degrees/s |
| Heading acceleration | 4 degrees/s² | 3.333225 degrees/s² |
| Vertical speed magnitude | 0.45 m/s | 0.381976 m/s |
| Vertical acceleration magnitude | 0.1 m/s² | 0.073484 m/s² |
| Pitch magnitude | 35 degrees | 25.730069 degrees |
| Pitch change rate | 8 degrees/s | 5.101526 degrees/s |
| Roll magnitude | 0 degrees | 0 degrees |

The continuous parameter-box proof is separate from sampled peak measurements;
its conservative bounds are in `analytic_bounds_before_execution.json`.
Maximum horizontal oracle discrepancy was 1.013e-13 m against 1e-5 m;
heading discrepancy was 1.706e-13 degrees against 1e-4 degrees. Depth discrepancy
was 4.45e-16 m. Clock and phase discrepancies were zero. All repeated-state
position, depth, heading, pitch, speed, clock and phase discrepancies were zero;
canonical state/choice equality was exact.

Nine acceptance tests passed, covering actual reference acceptance, injected
teleport, inconsistent vertical velocity/pitch/state, repeated draw count, missing
sample, discontinuous phase, continuous boundary controls and stationary heading.
The first test attempt had one expectation error: it expected `passed=false` for
an invalid label transition, while the existing v3 validator correctly raised
`ValueError` earlier. The failed result and exact test source were retained;
`acceptance_test_amendment.json` records the correction. No model, analysis,
configuration or tolerance was changed for the retry. All eight GAMA runs passed
on their first execution; the test-harness failure was not hidden.

## Runtime, preservation and review limits

Actual runtime: GAMA 2025.6.4, commit ab35ccb69a12b3e2ac9e0b902662f24a82367995;
bundled Temurin Java 21.0.7+6. Each run invoked the installed legacy-headless
launcher with its own workspace and JVM invocation. Runtime/configuration,
launcher, model, configuration, XML plan, implementation-lock and output hashes
were retained. No SDK, installation or MARLIN runtime source was changed.

M3 made no HTTP mutation, Kit restart, scene acquisition or animation integration.
Read-only observations during and after the campaign verified unchanged scene
structure, non-ocean bounds, water selection and swimmer/gallery state. Ocean and
chase kept running with the same configurations. Accepted M1/M2 packages verified
again; M2's water-evidence preservation check also passed.

Review the three scientific figures, per-run XML/JSON/CSV and the named Gate B
packet. Human acceptance is still pending. M4 body animation may begin only after
that review; rigid trajectory pitch and a phase trace do not establish coordinated
body motion, deformation quality or biological plausibility.

Technical references used for GAML/API semantics were the official
[GAMA headless documentation](https://gama-platform.org/wiki/RunningHeadless),
[legacy XML plan documentation](https://gama-platform.org/wiki/1.9.3/HeadlessLegacy)
and [GAML angle operators](https://gama-platform.org/wiki/OperatorsAA).
The installed runtime's actual executions remain the implementation evidence.
These references supplied no animal parameter values.
