# M2 — Movement ownership and simulation time

Sprint: **MARLIN — GAMA–Omniverse Bottlenose Dolphin Behaviour and Animation**.
Milestone: **Define and test movement ownership and simulation time**.
Completed: **5 November 2026**. Gate A was accepted by MAR before this work;
the signed M1 evidence and original baseline manifest were preserved.

## Result and scope

M2 established one explicit state-to-scene mapping for an isolated Model 61A
bottlenose. It added a v3 contract to the existing optional NVIDIA Kit Services
bridge, with a removable USD ownership layer, explicit simulation-time queries,
pause/reset/release controls and failure guards. Existing v1/v2 endpoints remained
compatible. No render-service, ocean, swimmer, gallery, asset or GAMA-model source
was changed.

The inputs in this milestone are **hand-authored engineering fixtures**. This
is not an actual new GAMA behaviour run. The existing skinned body stays at rest;
phase is evaluated and recorded, but no animation clip or procedural body motion
is bound. M3 supplies the constrained GAMA model and actual execution evidence;
Gate B precedes M4 body-animation integration. No biological acceptance, water
attenuation fix, RGB identity, dataset or trained model is claimed.

## Boundary state

The structural schema is [state_schema_v3.json](state_schema_v3.json). The complete
semantic validator is `exchange_v3.validate_step` plus `StepBuffer`; JSON Schema
alone does not express all the clock, continuity and finite-arithmetic rules.
Two complete valid fixtures and fourteen invalid fixtures are under
[fixtures/m2](fixtures/m2).

| Required field | Meaning |
| --- | --- |
| `schema_version` | Exact `3.0`; no implicit version conversion. |
| `model_version`, `run_id` | Explicit producer/model identities, fixed until reset. Actual model/configuration hashes and execution commands belong to M3 provenance. |
| `step_index`, `simulation_time_s`, `simulation_step_s` | Nonnegative integer index, elapsed simulation seconds and positive fixed step duration. `t = index × dt` within 1e-9 s. A run starts at index/time zero. |
| `seed` | Explicit integer, fixed within a run. A fixture seed does not establish GAMA execution. |
| `agents` | Exactly one full bottlenose snapshot; empty does not mean deletion. |
| `agent_id`, `species` | Safe identifier bound at acquisition; exact species `bottlenose_dolphin`. No arbitrary USD path or asset input. |
| `behavioural_state` | `steady_swim`, `turn`, `descent`, `submerged_swim`, `ascent`. Engineering labels, not biological validation. |
| `horizontal_position_m` | `[x,z]` metres in the declared MARLIN local horizontal frame. |
| `heading_deg`, `pitch_deg`, `roll_deg` | Degrees; heading [0,360), pitch [-90,90], roll [-180,180]. These are mathematical domains, not animal movement limits. |
| `speed_mps`, `vertical_velocity_mps` | Nonnegative horizontal speed and signed vertical speed (up positive), reported by the producer. They do not integrate translation a second time. |
| `vertical_reference`, `depth_m` | Exact `mean_sea_level` and nonnegative metres below fixed world Y=0, at the motion-root origin. |
| `state_entry_time_s`, `transition_duration_s` | Entry within elapsed simulation time and nonnegative blending duration. Derived progress is `clamp((t-entry)/duration,0,1)`; duration zero means progress one. |
| `animation_clock` | Required version, epoch time, epoch phase and rate, as defined below. |

Identifiers match `[A-Za-z_][A-Za-z0-9_]{0,127}` over the entire string. Integers
exclude booleans/floating representations and are bounded by `2^53-1`. Numerical
fields exclude booleans, strings, infinities, NaN and overflowing derived clocks.
Unknown or missing fields are rejected, including an independent absolute Y.

## Coordinates and fixed asset calibration

The boundary is a right-handed Cartesian frame: X/Z horizontal, **Y up**.
The exporter must explicitly supply `x_m,z_m,depth_m` in this frame; native GAMA
`location`, GIS axes, angle conventions and display pixels are not silently
reinterpreted. Existing GAMA fixtures already name `x_m,z_m`; M3 must export and
verify its own variables against this contract with actual GAMA execution.

Heading 0° points +Z, 90° +X, 180° -Z and 270° -X. Its horizontal forward vector
is `[sin(h),0,cos(h)]`. If derived from a nonzero horizontal displacement, heading
is `atan2(dx,dz)` in degrees, normalized modulo 360. A stationary producer retains
an explicit heading rather than deriving an undefined bearing.

For inspected, explicitly authored stage units `u` metres per unit:

```text
position_m           = [x, -depth, z]
position_scene_units = [x/u, -depth/u, z/u]
root rotation        = Rz(roll) * Rx(-pitch) * Ry(heading)   # USD row vectors
```

Roll acts about local +Z, followed by nose-up positive pitch and then heading.
Double-precision USD matrix ops carry the dynamic root transform. All four
cardinals, both unit scales (0.01 and 1 m/unit), pitch/roll order and actual
composed forward/right vectors were checked. The live stage is Y-up, 0.01 m/unit.
Missing explicit metadata, coordinate changes, foreign stages or non-finite
resolved transforms are refused.

The model child separately retains the M1 engineering correction: rotation
`[-90,0,0]`, scale `1/u`, unchanged Model 61A asset and textures. The profile
`config/model61a_engineering_v1.json` pins all four asset/licence dependencies.
It does not invent an anatomical length or claim final biological calibration.
The only shared actor-lifecycle adjustment permits a profile without the legacy
`axial_length_m` field; the old v1/v2 profiles still report their original fields.

Depth uses **fixed mean sea level**, not an ocean-wave sample. There is one
vertical input and no wave-following callback. It locates the motion root, not the
animal's dorsal surface or centre of mass. Positive pitch/depth does not establish
biological diving, surfacing clearance or breathing behaviour.

## Ownership and lifecycle

The experimental root is `/MarlinGamaBottlenose/Bottlenose_001`, outside existing
autonomous controllers' `/World/Cetaceans` namespace. The accepted demonstration
dolphin is not taken over. No swimmer, dive controller, ocean follower, timeline
clip or update subscription is attached to the test instance. The owner registers
**zero** update subscriptions. Consequently no global controller shutdown or
unrelated animal disable is needed to acquire it.

Acquisition validates coordinates, asset hashes and an empty private namespace,
constructs the reference off-stage and attaches one anonymous session sublayer.
It returns a required capability token; a second acquisition is refused. Every
mutation checks token, active stage, capture busy gate, units, owned-layer bytes,
composed parent/root matrices and the complete composed model/body fingerprint.
Time-sampled root/body attributes and bound skeletal animation are refused.
The fingerprint includes transforms, geometry, skeleton data and relationships;
array buffers are hashed in full. Static body equality is exact within each
runtime, not inferred from a frame label.

Guards detect persistent competing opinions on the next status/mutation call and
report `frozen_guard_failure`. They do not overwrite the foreign writer or claim
to police arbitrary code continuously between calls. The actual composed-USD
tests injected both root and model-child overrides. Duplicate acquisition and
subscription prevention are enforced by exclusive namespace/layer ownership and
the absence of any callback registration.

`pause=true` holds root, body and phase, rejecting step/evaluate calls. Resume
does not advance simulation time or alter the held frame; the client explicitly
requests the next state. Reset clears accepted history but holds the last pose
and phase until a new explicit index-zero state. Reset preserves pause state.
Release removes only the owner's layer from its saved stage and clears token,
buffer and phase; extension shutdown performs the same cleanup. It never removes
content from a replacement/foreign stage. Capture busy blocks lifecycle changes.
After release the original session/other actors remain; no new autonomous writer
is silently started for the removed private actor.

## Simulation clock and delivery

`animation_clock` has exact version `constant_rate_v1`, `epoch_time_s <= t`,
`epoch_phase_cycles` in [0,1), and nonnegative `rate_hz`. Evaluated phase is:

```text
phase(t) = (epoch_phase_cycles + (t - epoch_time_s) * rate_hz) mod 1
```

This version uses no speed-dependent accumulator. Rate is an explicit engineering
input; zero horizontal speed requires zero rate. Rate changes must re-anchor
continuously at the new snapshot time within 1e-9 circular cycles. A clock reset
requires explicit run reset. Phase is independent of wall clock, HTTP delays,
Kit timeline, rendering rate and capture/query order. This is a future animation
control, not evidence that a body pose has already been animated.

Only two contiguous producer snapshots are retained. Explicit queries are allowed
inside that bracket, never extrapolated. Position, depth, pitch, speed and vertical
velocity interpolate linearly. Heading and roll use the shortest circular arc;
an exact 180° tie selects the negative arc. State, entry/duration and clock use the
left snapshot until the exact right endpoint. Phase continuity is checked at that
endpoint. Linear interpolation reconstructs this declared presentation curve;
it does not recreate unrecorded acceleration or certify movement bounds.

An identical latest duplicate refreshes connectivity but performs no USD write
and does not increment the accepted-step count. Stale, reordered, altered-duplicate,
gap, wrong-agent, changed-run/model/seed/dt and discontinuous-clock messages are
rejected with the last valid scene held. A missing step must be delivered before
later steps, or the client explicitly resets and replays. After two wall-clock
seconds without a valid delivered state, status reports `frozen_updates_missing`;
this timeout never changes simulation phase or starts fallback motion. Historical
queries inside the retained bracket remain available. Invalid inputs are checked
on a detached buffer before USD changes; composition failure rolls back the layer
and leaves accepted history unchanged.

## API and reproduction

All routes use existing Kit Services on port 8011. The bridge remains optional;
this session enabled it at launch without changing the main app dependency list.

| Route suffix under `/integration/gama/v3` | Payload |
| --- | --- |
| `POST /validate` | Complete state; validates without owning or rendering. |
| `POST /actor/acquire` | `agent_id` only. |
| `POST /actor/step` | `ownership_token`, complete `step`. |
| `POST /actor/evaluate` | `ownership_token`, `simulation_time_s`. |
| `POST /actor/pause` | `ownership_token`, boolean `paused`. |
| `POST /actor/reset` or `/actor/release` | `ownership_token` only. |
| `GET /actor/status` | Composed matrix, retained state, evaluated frame/phase, transport/guard status and static-body fingerprint. |

Run CPU checks with the installed USD interpreter, choosing an unused JSON result
path because acceptance outcomes must not be overwritten:

```bash
/home/madil/opt/blender-5.0.1-linux-x64/5.0/python/bin/python3.11 -B \
  tools/test_gama_v3.py /tmp/m2_new_cpu_result.json

/usr/bin/python3 -B experiments/gama_dolphin_behaviour_v1/qa/m2/verify_package.py
```

The host live test is `qa/m2/live_contract_test.py <unused-output-directory>`.
It requires the bridge enabled, restored scene and no active v3 owner; it applies
fixtures to the private actor and releases in `finally`. It is a mutation test,
not a read-only package verifier. The retained HTTP calls record its real results.

## Acceptance evidence

The unchanged [acceptance_tolerances.json](acceptance_tolerances.json) was locked
before execution; `qa/m2/locked_plan.json` records its SHA-256. Limits are 1e-5 m
position, 1e-4° circular heading, 1e-8 orientation matrix components, 1e-9 s time,
1e-9 circular phase cycles, 1e-9 transition progress and 1e-7 relative fixed scale.
Paused/rejected USD layer/pose and static body fingerprints require exact equality.
M3 must lock scenario speed/acceleration/turn/depth limits before its runs.

| Evidence | Outcome |
| --- | --- |
| `qa/m2/cpu_attempt_02.json` | 12 protocol/composed-USD tests passed. Cardinal position and heading errors were zero at both unit scales; pitched forward-vector error was 1.11e-16. |
| `qa/m2/legacy_regressions.json` | 72 tests passed across v1/v2 exchange, actor and stage mapping suites. |
| `qa/m2/live_attempt_01/results.json` and `http_calls.json` | 67 live checks passed, including composed matrices, wrapping/interpolation, reordered query equality, invalid atomic holds, zero speed, pause/resume/reset, missing reports, coexistence and release. |
| `qa/m2/schema_verification.json` | Draft 2020-12 schema and both valid structural fixtures verified; semantic rejection cases tested separately. |
| `qa/m2/restored_stage_comparison_attempt02.json` | Same 38 prims, no additions/deletions. Every composed attribute/relationship matched except the running ocean's recalculated points, normals and extent. |
| `qa/m2/preservation_disposition.json` | Historical water M5/M6/preset/driver evidence and dependencies unchanged; original source hashes verified at the M1 Git commit. |

The first CPU attempt was stopped after its per-element geometry fingerprint
proved slow; full buffer hashing replaced that expansion and the retry passed.
The aborted outcome is retained. The first restoration comparison omitted ocean
normals from its declared restart exception and failed. Its result and exact source
were retained; `stage_comparison_amendment.json` explains the narrow correction
from the existing ocean update implementation. No numerical tolerance changed.
The old water M6 verifier fails against current `actor.py` because it pins old
source bytes. Its raw output is retained, with both intentional bridge-file
changes and the preserved original versions verified separately. Historical
manifests were not rewritten to make a current-source check pass.

## Runtime restoration and limits

One graceful Kit restart loaded the optional extension. Fresh pre-work checkpoint
`checkpoint_b00kdhw8` (SHA-256 `60d87c4aac12d373d5700cfb836f529a285e21053b5ec9c546a87bcab4c360fa`)
was verified before closing the old process. The frozen stage was restored
directly, without marine setup or animal respawn. Public ocean/chase controllers
were restarted from saved configuration. Ocean wave height 40 and length 650 came
from the previously recorded standard restoration, since the public status does
not serialize those two settings. Controller accumulators/wave phase were
reconstructed, not resumed exactly. Camera, resolution, fill-frame, renderer and
display settings matched. Scene comparison confirmed the scoped differences.

Final checkpoint: `checkpoint_1j9vou37`; copied scene/metadata are under
`qa/m2/live_final`. MARLIN remained running with its original stationary dolphin,
stopped swimmer/gallery, running ocean/chase and original water selection. The
v3 owner was released. GPU: RTX A2000, driver 595.99.02, 1,824 MiB free at the final
observation. The known asset-converter libxml2 startup problem remains unrelated;
M2 neither used it nor changed the installed runtime.

`m2_manifest.json` pins the package and exact current source/config inputs.
Append-only Kit logs are excluded from that seal; completed acceptance records
and source snapshots are included. No Git commit or push was made by M2.
