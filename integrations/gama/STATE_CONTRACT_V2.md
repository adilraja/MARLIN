# GAMA MARLIN state contract and ownership rules

Sprint: GAMA–MARLIN Behavioural Integration and Validation.
Milestone 2: Define the state contract and ownership rules.

Version 2.0 defines one harbour porpoise controlled by one external GAMA run.
The exchange carries SI coordinates and simulation time, never camera parameters,
asset paths, executable commands or a second independent vertical coordinate.
Existing v1 routes, example, validator and bottlenose fixture remain compatible.

This milestone implements validation, ordered buffering, current-stage inspection
and read-only transform previews in the existing optional Kit Services extension.
It does not spawn a v2 porpoise or implement its pose mapping. Actual GAMA model
execution belongs to M3, faithful scene application to M4, and biological review
to M5. The JSON example is explicitly a hand-authored contract test fixture.

## Payload

The structural schema is [step_v2.schema.json](step_v2.schema.json), using JSON
Schema draft 2020-12. [examples/step_v2.json](examples/step_v2.json) is a complete
example. Every listed field is required; all unlisted fields are rejected,
including nested fields. There are no implicit version, time, unit or datum defaults.

| Field | Interpretation and validation |
| --- | --- |
| `schema_version` | Exact string `2.0`. |
| `run_id` | Producer-assigned run identifier, fixed until explicit buffer reset. Different executions use different IDs even if they share a seed. |
| `step_index` | Nonnegative integer; index of the originating GAMA state. |
| `simulation_time_s` | Nonnegative elapsed GAMA seconds since index zero. Not wall-clock time, Kit timeline time or a USD time code. |
| `simulation_step_s` | Positive, fixed GAMA step duration in seconds. |
| `seed` | Actual producer seed, fixed within a run. Transport validity does not prove GAMA used it; execution provenance must do so in M3. |
| `agents` | Full snapshot containing exactly one agent. An empty array is invalid and never means deletion. |
| `agents[0].agent_id` | Identity of the externally controlled animal, fixed within a buffered run. This is not a USD path. |
| `species` | Exact string `harbour_porpoise`. No new species or registry is introduced. |
| `behavioural_state` | One of `surface`, `shallow_swim`, `descent`, `submerged_swim`, `ascent`. Semantic labels for deterministic MARLIN pose mapping; not biological approval. |
| `horizontal_position_m` | Two numbers `[x, z]` in metres, in MARLIN's local horizontal frame. |
| `heading_deg` | Horizontal bearing in degrees, in `[0,360)`, increasing from +Z towards +X. |
| `speed_mps` | Nonnegative instantaneous horizontal speed in metres/second; metadata from GAMA, never an instruction for MARLIN to integrate motion. |
| `vertical_reference` | Exact string `mean_sea_level`; the fixed contract datum is world Y=0. |
| `depth_m` | Nonnegative metres below that datum, measured at the animal's motion-root origin. This is the only vertical position input. |

Identifiers match `[A-Za-z_][A-Za-z0-9_]{0,127}` over the complete string.
Integer fields exclude booleans and floating representations and are bounded by
`2^53-1` for JSON interoperability. All numerical fields exclude booleans,
strings, NaN, infinities and values that overflow conversion. Structural JSON
Schema checks alone do not enforce every runtime rule: the Python validator is
authoritative for finite arithmetic, clock consistency and buffered-run semantics.

No biological ranges, speed/depth relationships or state duration requirements
are invented here. For example, the label `surface` alone does not force root
depth to zero: anatomical reference points, asset pose and appropriate clearance
need explicit mapping and review. State/depth suitability is distinct from an
unambiguous transport representation.

## Coordinates and vertical interpretation

The boundary uses MARLIN's local Cartesian frame, with Y vertical, X/Z horizontal
and no geographic origin, GIS transform or native GAMA heading assumed.
The GAMA model/exporter must produce this frame explicitly. +Z is heading 0°,
+X is 90°, -Z is 180°, and -X is 270°. The horizontal forward vector is
`[sin(heading), 0, cos(heading)]`. MARLIN uses a positive Y rotation for this
bearing, with asset orientation correction applied separately to the model child.
Pitch, roll, skeletal animation and animation phase are not independent GAMA
commands in v2. MARLIN owns their eventual deterministic state-to-pose mapping.

For inspected stage scale `u` metres per scene unit:

```text
position_m = [x, -depth_m, z]
position_scene_units = [x/u, -depth_m/u, z/u]
speed_scene_units_per_s = speed_mps/u
```

These are resolved previews, not movement integration. MARLIN never advances the
animal between received snapshots or applies speed a second time. Instantaneous
speed need not equal a straight-line finite difference between selected snapshots,
particularly for curved paths, acceleration or skipped capture steps.

Depth is relative to the fixed mean sea plane, not the instantaneous wave surface.
It describes the asset motion root, not its dorsal surface, nose or centre of mass.
The representation implies no breathing clearance, anatomical landmark or optical
visibility. No ocean sample is used in resolution, so no ocean phase can change Y.
The experiment environment must place its nominal mean sea plane at world Y=0;
an environment with a shifted nominal sea level needs an explicit contract
revision or coordinate adapter, not a silent offset.

`position_m`, absolute Y, `height_m`, `altitude_m`, a wave-relative datum and extra
orientation/pose fields are rejected in an incoming v2 agent. `position_m` may
appear only in the receiver's resolved preview output.

## Stage units are inspected

The application source does not declare a universal metres-per-unit value.
Calibration stages explicitly author their unit/axis metadata; some existing
marine capture functions require 0.01 m/unit. These requirements must not be
mistaken for evidence about every newly opened stage.

The read-only `GET /integration/gama/stage` reports the current composed USD
`metersPerUnit` and `upAxis`, whether each was authored, the root-layer identifier,
and suitability/rejection reasons. It does not traverse animals, sample the ocean,
create a stage, acquire an actor, stop a controller or change metadata.

V2 previews require a present Y-up stage with explicitly authored finite positive
`metersPerUnit` and explicitly authored `upAxis`. USD fallback values remain
visible in diagnostics but do not silently satisfy that requirement. Missing or
unsuitable stages reject conversion; the bridge never repairs their units.

Both 0.01 m/unit and 1 m/unit stages are supported by conversion tests. A later
owned-actor acquisition must save the inspected stage identity and units and
reject subsequent stage/unit/axis changes before any writes, as the existing
isolated v1 actor already does. A preview is read again on each call and creates
no persistent scene ownership.

## Simulation clock and update ordering

GAMA owns the clock. The zero origin is explicit:
`simulation_time_s = step_index * simulation_step_s`, with absolute comparison
tolerance `1e-9` seconds and zero relative tolerance. The multiplication itself
must remain finite. Export precision must preserve strict time progression.

A fresh validation buffer can begin at any valid index. Subsequent unique
snapshots must strictly increase both index and represented simulation time.
Index gaps are allowed for record-first replay of preselected GAMA snapshots;
the receiver neither fills gaps nor invents intermediate behaviour. This rule
does not prove that an omitted segment was generated by GAMA; the retained
trajectory and execution provenance must establish that separately.

An identical latest-snapshot retry is accepted with `duplicate:true`, without
incrementing the accepted count. Equality is over validated content, not JSON key
order. Conflicting latest retries, older snapshots (even if historically valid),
run changes, seed changes, step-duration changes and agent identity changes are
rejected without changing the buffer. Species changes fail the schema itself.
The same run ID cannot silently reset time; explicit reset is required.
The buffer stores a detached latest snapshot, not an archival trajectory.

`POST /integration/gama/v2/reset` clears only the v2 validation buffer. It neither
removes a scene animal nor resets GAMA, the v1 buffer, ocean, renderer or another
controller. Future scene replay reset/release must remain explicit ownership
operations; validation reset must not bypass a scene actor's run guard.

## Ownership rules

| Responsibility | Owner | Consequence |
| --- | --- | --- |
| Behavioural state, trajectory, heading, speed and depth evolution | GAMA | MARLIN applies received states; it does not independently choose or integrate these values. |
| Asset selection and deterministic state-to-pose mapping | MARLIN | Producer cannot supply an asset path, arbitrary transform script, pitch/roll override or alternate renderer. Mapping/version and resolved pose will be recorded. |
| Camera, projection, lighting, water appearance and capture | MARLIN | GAMA state cannot change camera/GSD, ocean parameters or rendering settings. |
| Capture scheduling and snapshot selection | Experiment orchestrator | Orchestrator selects actual recorded run/step states and freezes them; it does not manufacture replacement behaviour. |

The scene-control implementation must retain the existing explicitly owned,
private USD-layer approach. A new porpoise will be created only under the bridge's
private root, outside `/World/Cetaceans`, after collision checks; it will never
take over an arbitrary existing prim or reuse a demonstration animal ID/path.
The current swimmer and gallery controllers target recorded paths under
`/World/Cetaceans`; the private actor must never be enrolled with either controller.
Their diving and wave-following logic therefore cannot also own its position.
No global swimmer, gallery or ocean stop is required to claim this actor.
Unrelated demonstration animals retain their controllers.

Future scene apply must validate the whole payload, clock ordering, token,
run/agent binding, supported pose mapping, active stage, coordinate metadata and
capture gate before authoring. Invalid states must leave both the scene and
accepted-run buffer unchanged. USD authoring failures must roll back edits before
committing the accepted state, following the existing isolated actor pattern.
Release must remove only the bridge-owned layer from the saved stage.

When external updates stop, the owned animal must freeze at the last accepted
state and report that held state/run/step. No automatic handoff to autonomous
swimming, interpolation, extrapolation or autonomous diving is allowed. Explicit
disconnect/stale reporting and recovery will be exercised in M4. Duplicate
application must not spawn another animal, advance animation or count as a new
biological step. Capture pause must prevent state/ownership mutation.

## HTTP behaviour in Milestone 2

All routes use NVIDIA Kit Services in `cris.madil.gama_bridge`; no second server
or transport is introduced. MARLIN is normally served at port 8011. The optional
GAMA WebSocket coordinator remains a separate existing transport, unchanged.

| Route | Behaviour |
| --- | --- |
| `POST /integration/gama/v2/validate` | Validates and returns a detached v2 snapshot; no buffered state or stage access. |
| `POST /integration/gama/v2/steps` | Validates and buffers ordered v2 snapshots; no stage access or scene writes. |
| `GET /integration/gama/v2/status` | Reports latest snapshot/count, `mode:validation_only`, `scene_control_enabled:false`, `rendered:false`. |
| `POST /integration/gama/v2/reset` | Clears only the v2 validation buffer. |
| `GET /integration/gama/stage` | Read-only current stage coordinate report, including unavailable/unsuitable state. |
| `POST /integration/gama/v2/preview` | Validates first, then resolves position/forward/speed from inspected stage units. No prim or buffer changes; `mode:conversion_preview_only`. |

Domain rejection retains the existing bridge's `ok:false` convention; clients
must check JSON `ok`, not merely HTTP success. Kit handles malformed JSON and
request-body type errors at its HTTP boundary. V2 route acceptance means validation
only. It does not mean an animal was spawned, moved, rendered or biologically
approved. V2 payloads are rejected by v1 scene routes, and v1 payloads are rejected
by v2 routes. This prevents accidental use of the old bottlenose binding.

## Verification and limits

Run the pure boundary tests and real-USD/read-only route tests:

```bash
python3 -B tools/test_gama_exchange_v2.py -v
/home/madil/opt/blender-5.0.1-linux-x64/5.0/python/bin/python3.11 -B tools/test_gama_v2_stage.py -v
```

Tests cover missing/unknown/contradictory fields, nonfinite values, integer bounds,
clock consistency, fixed run identity, atomic rejection, duplicate/gap/reset
semantics, SI conversion, conversion overflow, cardinal headings, stage defaults,
stage-unit changes, axis rejection, version isolation, no actor acquisition and
unchanged USD layers. Route unit tests mock Kit Services and do not alone establish
that live HTTP registration succeeded. The M2 report records separate live evidence
and the inspected stage configuration without substituting saved-stage metadata
for live-stage observations.
