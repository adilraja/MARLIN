# Harbour porpoise record first demonstration

Milestone 3 of the GAMA–MARLIN Behavioural Integration and Validation sprint
executed [porpoise_behaviour.gaml](porpoise_behaviour.gaml) with installed GAMA
2025.6.4. One GAMA `porpoise` agent used its finite-state-machine architecture
to generate a complete timed sequence and continuous SI position, heading,
horizontal speed and mean-sea-level depth outputs.

The [configuration](../../experiments/gama_marlin_v1/porpoise_model_config.json)
is versioned as `engineering_porpoise_v1`. All behavioural numbers are explicitly
engineering assumptions for a short software demonstration. The output labels
and motion have no biological approval. In particular, `surface` describes a
model state and does not certify that the existing static mesh is breathing or
correctly intersecting water.

## Execute and retain a fresh run

From `/home/madil/kit-app-template`, choose a run ID that has never been used:

```bash
python3 -B tools/gama_porpoise.py --run-id porpoise_record_001 --seed 184729
```

The runner launches the installed `gama-headless` executable with 1024 MB of
requested heap, a dedicated workspace, one generated XML experiment plan and
a fresh output directory. It does not start a GAMA WebSocket server or contact
MARLIN. Kit may remain running throughout this operation.

Default run directory:
`experiments/gama_marlin_v1/trajectories/<run_id>/`.
An optional `--output /absolute/new/directory` changes that destination.
Workspaces are isolated under
`artifacts/gama_marlin_v1/workspaces/<run_id>/` and are local/Git-ignored.
Existing run outputs or workspaces are refused. After a failed attempt, retain
its files and choose a fresh run ID; do not overwrite its evidence.

Each successful run contains:

- `model.gaml`: exact self-contained model copy executed by GAMA.
- `configuration.json`: pinned engineering configuration, run ID and requested seed.
- `experiment.xml`: actual experiment plan, including seed, parameters and outputs.
- `launcher.log`: combined launcher/runtime console stream.
- `raw/simulation-outputs0.xml`: original GAMA per-step output, retained permanently
  with the experiment evidence rather than placed only in `/tmp`.
- `raw/console-outputs-0.txt`: GAMA simulation console output, which may be empty.
- `trajectory.json`: v2 exchange snapshots converted directly from the exported
  values, with no Python-generated substitute states or inferred state labels.
- `validation.json`: observed transitions and numerical acceptance errors.
- `execution.json`: command, runtime version/commit/JDK, model/configuration/plan
  hashes, launcher hash, actual exported seed, output hashes, times and exit status.

The existing Pilot harbour porpoise calibration record identifies the selected
MARLIN asset. Its USD hash is checked and recorded before GAMA launch. GAMA owns
behaviour generation; MARLIN will load the USD reference during scene integration.
No USD asset, calibration or licence is modified by this recorder.

## Model schedule and parameters

| Interval in simulation seconds | Exported state | Root depth in metres |
| --- | --- | --- |
| 0 ≤ t < 2 | `surface` | 0.2 |
| 2 ≤ t < 6 | `shallow_swim` | Smooth transition from 0.2 to 0.8 |
| 6 ≤ t < 10 | `descent` | Smooth transition from 0.8 to 3.0 |
| 10 ≤ t < 14 | `submerged_swim` | 3.0 |
| 14 ≤ t < 18 | `ascent` | Smooth transition from 3.0 to 0.2 |
| 18 ≤ t ≤ 20 | `surface` | 0.2 |

The 0.5-second step produces 41 samples, including both t=0 and t=20.
Depth uses the cubic easing function `u²(3−2u)` between declared endpoints,
with matching endpoint depths and zero endpoint vertical slopes. Horizontal
movement follows an 8 m-radius circle at constant 0.5 m/s instantaneous speed.
GAMA draws one initial angular phase after explicitly setting its RNG seed.
The seed affects that phase only. The animal moves horizontally in every state.

Every number above is an **engineering assumption**. The short durations bound
execution and exercise all contract states; the modest circular path keeps
motion continuous and straightforward to verify; the distinct depth levels
exercise vertical transfer without making a wildlife dive-profile claim.
The root depth datum is fixed mean sea level, world Y=0, under the M2 contract.
These choices are not species norms, behavioural frequency estimates, specimen
measurements or reviewed anatomical poses.

The FSM has separate initial and final surface states internally; both export
the contract label `surface`. At a sampled state boundary, the exported label
identifies the state body that generated that sample. A transition decision made
using `simulation_time_s + step` selects the body executed at the next sample.
The final surface body continues motion until the headless step limit ends the run.

GAMA's documented [FSM architecture](https://gama-platform.org/wiki/ControlArchitecture)
provides state bodies and transitions. Its documented
[legacy headless runner](https://gama-platform.org/wiki/HeadlessLegacy) accepts
an XML experiment plan with parameters and monitored outputs. The `gui` experiment
type in this model is required by that existing legacy route; no graphical
display or GAMA UI was needed for the recorded runs.

## Acceptance and replay boundary

Python reads the original XML variables, verifies effective model parameters,
checks exactly one agent and the actual seed/run ID, and passes every snapshot
through the existing v2 validator and ordered buffer. It independently checks
the declared state timing, depth curve, circle radius, seeded position, tangent
heading and per-step horizontal chord length. No raw value is repaired to force
a pass. Failed runs retain an execution error record and available raw evidence.

Numerical tolerances were declared before execution in the configuration:
position/depth 1e-8 m, heading 1e-8 degrees, speed 1e-10 m/s and clock 1e-9 s.
Effective constant speed/configuration values are checked exactly; tolerance
allows floating arithmetic in derived geometry and clocks.

For the two completed same-seed executions, all canonical state contents matched
exactly after excluding only their deliberately different `run_id` values.
Wall-clock times and paths are stored separately in execution records and never
enter the state comparison. This is a two-process, one-seed check; M5's ten seeds
and three repeated seeds remain outstanding.

The `trajectory.json` list is the record-first input for later replay through
the existing MARLIN bridge. M2 v2 routes currently validate and preview only;
the v1 actor route still owns its bottlenose fixture. Do not send these porpoise
states to that v1 actor route. M4 must add the porpoise ownership/mapping and prove
composed transforms, recovery and coexistence before scene replay is certified.

## Evidence and verification

Executed run IDs: `m3_seed_184729_a` and `m3_seed_184729_b`, both seed 184729.
The [M3 report](../../experiments/gama_marlin_v1/M3_ACTUAL_GAMA_EXECUTION.md)
links their retained records and measured outcomes.

```bash
python3 -B tools/test_gama_porpoise.py -v
python3 -B experiments/gama_marlin_v1/qa/verify_m3.py
```

The first command runs explicitly synthetic XML rejection tests; those fixtures
are not actual GAMA evidence. The second command independently reparses both
retained real outputs, verifies hashes and exact state equality, checks preserved
M1/M2 artifacts and checkpoint copies, and records the tests in new M3 evidence.
It refuses to overwrite an existing verification result. The completed result is
`experiments/gama_marlin_v1/qa/m3_validation.json`.
