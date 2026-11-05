# Gate B — Review of M3 trajectories for animation integration

Prepared 5 November 2026. Proposed reviewer: **MAR**.
**Status: pending. No human acceptance has been recorded.**

## Decision requested

Accept the bounded `bottlenose_constrained_v1` reference and seeded trajectories
as suitable engineering inputs for M4 body-animation integration, or identify
specific trajectory/constraint changes needed before integration.

This decision does not accept biological realism, body deformation, a swimming
pose, tail-beat relationships, underwater optics or survey/research readiness.
Body-animation work has not started. The sprint's Gate B requires trajectory
review before that work may proceed.

## Material to inspect

1. [Movement overview](../qa/m3/figures/movement_overview.png): executed horizontal
   paths, depth, speed ramps and gradual heading wrap.
2. [Position and states](../qa/m3/figures/position_and_states.png): X/Z time series
   and all six state episodes, including the return to steady swimming.
3. [Attitude and constraints](../qa/m3/figures/attitude_and_constraints.png):
   trajectory pitch, vertical velocity, phase controls and acceleration.
4. [Movement model and parameter register](../M3_MOVEMENT_MODEL_AND_PARAMETER_REGISTER.md):
   state rules, integration scheme, every parameter's evidence status and limits.
5. `qa/m3/campaign_analysis.json`, `boundary_audit.json`, per-run raw XML/JSON and
   the primary-run CSV files beside the figures. `m3_manifest.json` pins the exact
   technical evidence and implementation to be reviewed.

## Technical findings

- Eight actual GAMA executions passed: reference plus repeat, then seeds 1, 42,
  184729 and their fresh-process repeats. Each retained 297 samples over 74 s.
- Each repeat matched canonical state bytes and realised choices exactly;
  measured position, heading, depth, pitch, speed, clock and phase discrepancies
  between repeated states were zero. Seeds produced distinct realised choices.
- The executed order was initial steady swimming → gradual turn → descent →
  submerged swimming → ascent → final steady swimming. Start/stop ramps and
  stationary endpoint holds were explicit.
- Forty actual state joins were audited across all runs. Independent control,
  integration and timing checks passed; no clamp, reset or teleport was used.
- Sampled maxima included horizontal speed 0.801757 m/s, vector acceleration
  0.371927 m/s², heading rate 12.994127 degrees/s, vertical speed 0.381976 m/s and
  pitch magnitude 25.730069 degrees, within the predeclared engineering limits.
- Nine acceptance tests passed, including fault injections. An initial test
  expectation error and its corrected retry were retained; production model,
  analysis and numerical criteria did not change to obtain acceptance.
- MARLIN was not restarted or mutated. Accepted scene/water/controller state and
  the earlier evidence packages remained preserved.

## Concrete review questions

- Is the path, turn direction and manoeuvre sequence appropriate for a small
  engineering animation demonstration?
- Are the stationary endpoint holds, speed ramps and timed depth transitions
  suitable, with no unexplained jump in position, attitude or phase?
- Are the explicit engineering parameter assumptions and bounded seed variation
  acceptable for this demonstration, without interpreting them as animal biology?
- May these exact trajectories proceed to M4's separate body-motion mapping and
  visual/deformation review?

The initial/final root depth is 0.2 m below fixed mean sea level, not an anatomical
clearance guarantee. M4 must inspect actual asset geometry relative to the waves.
Pitch follows the trajectory tangent; roll is zero. A plotted root attitude and
phase trace are not evidence of coordinated local body animation. The accepted
water preset's underwater-camera limitations remain unchanged.

Approval will be recorded in a new named acceptance record bound to the technical
manifest and this packet. The sealed technical results and initial pending status
will be preserved, rather than retroactively rewritten as an earlier approval.
