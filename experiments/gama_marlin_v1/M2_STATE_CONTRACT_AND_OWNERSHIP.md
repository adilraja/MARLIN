# Milestone 2 state contract and ownership report

Sprint: GAMA–MARLIN Behavioural Integration and Validation.
Milestone: Define the state contract and ownership rules.
Executed on 8 October 2026. Status: **Passed** for the defined M2 contract scope.

Defined a strict version 2.0 exchange for one harbour porpoise, implemented
validation and read-only conversion in the existing optional Kit Services bridge,
and verified both offline tests and live HTTP behaviour. A received state now has
explicit run identity, simulation clock, coordinate interpretation and behavioural
ownership. No porpoise actor, GAMA behavioural model or pose mapping was implemented
in this milestone; these remain M3/M4 work as specified by the sprint sequence.

## Delivered contract

- [Coordinate and ownership specification](../../integrations/gama/STATE_CONTRACT_V2.md)
  defines units, headings, depth, clocks, retries, reset, ownership and route semantics.
- [Versioned exchange schema](../../integrations/gama/step_v2.schema.json) and
  [hand-authored contract fixture](../../integrations/gama/examples/step_v2.json)
  define the boundary without claiming actual GAMA generation or biological validity.
- [Pure validator and ordered buffer](../../source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge/exchange_v2.py)
  reject invalid states before any stage access, preserve detached snapshots and
  make identical latest retries idempotent.
- [Read-only coordinate helper](../../source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge/stage_coordinates.py)
  inspects composed USD metadata and resolves previews without authoring a prim.

The payload includes `schema_version`, `run_id`, `step_index`,
`simulation_time_s`, `simulation_step_s`, `seed`, and exactly one agent with
`agent_id`, `species`, `behavioural_state`, `horizontal_position_m`,
`heading_deg`, `speed_mps`, `vertical_reference` and `depth_m`.
Unlisted fields, unsupported species/states, invalid numeric values and conflicting
vertical inputs are rejected. Runtime validation additionally enforces finite
arithmetic, the declared clock equation and run ordering; structural JSON Schema
alone is not claimed to enforce these semantic constraints.

Chose fixed mean sea level at world Y=0. Incoming horizontal position is `[x,z]`
in SI metres, and root Y is resolved as `-depth_m / meters_per_scene_unit`.
There is no incoming absolute Y or second vertical command, and no wave sample
affects the result. Heading remains 0=+Z, 90=+X, 180=-Z and 270=-X.
Speed is instantaneous horizontal metadata, not a second motion integrator.

GAMA owns behavioural state, trajectory, heading, speed and depth evolution.
MARLIN owns allowlisted asset selection, deterministic state-to-pose mapping,
camera, lighting, water and capture. The orchestrator owns snapshot selection
and capture scheduling. The contract requires bridge-private actor paths and
forbids enrolling them with autonomous swimmer/gallery controllers or stopping
unrelated animals globally. The current bridge's isolated actor ownership remains
intact. Future porpoise application must follow the same isolation and validate
all state/ownership gates before scene writes.

V2 routes are explicitly validation/preview only and cannot feed the v1 bottlenose
actor. Their buffer/reset is separate from v1. Behavioural pose suitability,
controller coexistence for the new porpoise and freeze/recovery demonstration
remain subsequent acceptance work, not implied by a valid v2 message.

## Actual current stage configuration

After the user confirmed Kit was stopped, launched the existing application once:

```bash
cd /home/madil/kit-app-template/_build/linux-x86_64/release
./cris.madil.kit.sh --enable cris.madil.render_service \
  --ext-folder /home/madil/kit-app-template/source/extensions \
  --enable cris.madil.gama_bridge
```

Used the documented runtime launcher without inspecting or editing generated
files. No existing in-memory scene was discarded. Kit reported app ready, RTX
ready and startup of both the render-service and optional bridge extensions.
Its already documented asset-converter native dependency error appeared during
default application startup; neither the contract nor the tests used that converter.
It did not prevent the live M2 routes or preview from passing.

Live `GET /integration/gama/stage`, recorded at 14:16:28 UTC, reported:

| Property | Observed value |
| --- | --- |
| Stage available | true |
| Metres per scene unit | 0.01 |
| Up axis | Y |
| `metersPerUnit` explicitly authored | true |
| `upAxis` explicitly authored | true |
| Suitable for v2 conversion | true |

This is current live evidence, separate from the previously inspected saved
Pilot stages. The example `[1.25,-2.5]` m horizontal position and 0.8 m root depth
resolved to `[125,-80,-250]` scene units. The bridge read the metadata rather
than assuming the scale. The fixed mean-plane datum is a contract choice, not
a measurement of an animated ocean surface.

MARLIN was left running on `http://127.0.0.1:8011` with the optional bridge enabled
and its initial empty stage. No marine setup, actor acquisition, asset spawn,
camera change, render or controller mutation was performed by the M2 verifier.

## Verification evidence

[Offline test results](qa/m2_offline_results.json) record **51 passing tests**:
23 new pure exchange tests, 8 new real-USD/mocked-route tests, and 20 existing
exchange, WebSocket protocol and USD actor regression tests. Each suite's command,
exit code and log hash are included; complete logs are stored beside the results.

```bash
python3 -B experiments/gama_marlin_v1/qa/run_m2_checks.py
```

Tests cover strict fields/version, numeric/identifier bounds, mean-plane-only
depth, clock equation and strict time progression, fixed run/seed/duration/identity,
gaps, duplicates, reset and atomic rejection. Conversion checks cover all four
cardinal headings, multiple stage scales, overflow, explicit metadata requirements,
wrong axes, unavailable stages and unchanged USD layers. Route tests additionally
verify v1/v2 separation, no stage access for invalid data, no actor acquisition and
no buffer mutation during previews. The touched/new bridge modules passed Python
AST syntax checks; `service.py` was not modified.

[Live HTTP results](qa/m2_live_results.json) record requests, HTTP status codes,
responses and source hashes from:

```bash
python3 -B experiments/gama_marlin_v1/qa/verify_m2_live.py
```

Live checks verified all six added routes, valid-state acceptance, read-only
conversion, latest duplicate handling, three invalid vertical payloads and an
out-of-order step. Rejections left the accepted snapshot/count intact. Before/after
scene inspection and stage metadata were identical; v1 state remained identical.
The initially empty v2 validation buffer was reset to empty after verification.
This live test did not invoke the scene actor APIs or start a GAMA process.

## Baseline preservation and scope

The offline evidence rehashed all **915 protected baseline files** other than the
one deliberately extended bridge router module. None changed. Both the original
Pilot checkpoint and its separate M1 backup retained their recorded SHA-256.
Pilot code, images, labels, splits, predictions, metrics and manifests remained
intact. Existing v1 schemas, fixtures and behaviour were unchanged.

Only the existing bridge's `extension.py` changed among previously preserved
source files; the validator/helper, schemas, specification, tests and M2 evidence
were added. No rendering-service implementation, ocean, autonomous movement,
camera, asset, biological parameter or ML result was modified.

Acceptance outcome: **Passed**. States have one declared interpretation and
owner, invalid/contradictory inputs fail before scene mutation, actual live units
were inspected, and executable tests cover the boundary. Actual porpoise scene
ownership and composed-transform recovery testing remain M4; a contract pass
does not award biological approval or complete later milestones.
