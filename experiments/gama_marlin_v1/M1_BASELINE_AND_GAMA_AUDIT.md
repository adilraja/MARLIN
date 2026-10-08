# GAMA MARLIN baseline and integration audit

Milestone 1 executed on 8 October 2026. Pilot v1 is preserved, its selected
checkpoint matches recorded provenance, and the existing optional GAMA bridge is
the basis for this sprint. Existing behaviour is an engineering circle fixture
for a bottlenose dolphin. It does not yet implement the requested harbour
porpoise behavioural sequence. No runtime source or Pilot output was changed.

## Baseline preservation

Command, from the repository root:

```bash
python3 -B experiments/gama_marlin_v1/qa/preserve_baseline.py
```

[Preserved-output manifest](qa/preserved_output_manifest.json) records 916 files,
their byte lengths and SHA-256 values, the repository commit and observed working
changes. All 51 checks against the Pilot M8 manifest, provenance file hashes and
eight asset dependencies passed. Every archived member was read back and hashed;
all source files were checked again after copying.

The backup includes the complete Pilot experiment folder, canonical application
and extension source, tools, GAMA integration files, existing local GAMA evidence,
the current sprint specification and the Pilot's eight recorded asset dependencies.
Generated directories and Python bytecode were excluded without traversal.

Local backup archive:
`artifacts/gama_marlin_v1/baseline_2026_10_08/pilot_and_source.tar`
(738,846,720 bytes). The checkpoint has a separate verified copy:
`artifacts/gama_marlin_v1/baseline_2026_10_08/checkpoint/best.pt`
(76,006,241 bytes). Its SHA-256 is
`bc2ccc63ddf4ddab2c6523ca60fee1cd2ea5a88ae3f833a3097cb5ba01510f5d`,
matching `experiments/gsd_pilot_v1/qa/m8_provenance.json`.
The backup directory also contains a copy of the preservation manifest.
These are local, Git-ignored copies on the same disk, not off-host backups.
The archive contains the recorded Pilot asset dependencies, not every asset or
installed software dependency needed by the entire MARLIN demonstration.

Pre-existing document moves/deletions, the new sprint specification and the
Pilot AI handoff were left untouched. The preservation script refuses an existing
backup destination rather than replacing evidence.

## Installed runtime and previous execution evidence

`/usr/sbin/gama-headless` resolves to the installed GAMA headless launcher.
`/opt/gama-platform/configuration/config.ini` declares `gama.version=2025.6.4`
and branch `2025-06-4`; the launcher also identifies 2025.6.4.
No GAMA execution or version migration was performed during this audit.

Existing actual GAMA work comprises:

- `integrations/gama/trajectory.gaml`: GAMA global reflex that generates a circle,
  using a random initial phase, 12 m radius, 3 degrees/s, fixed Y=-0.8 m and
  fixed engineering speed. This is executable GAML, not a hand-authored state file.
- `integrations/gama/trajectory.xml`: legacy headless experiment with seed 184729,
  20 steps and exported time, position, heading and speed variables.
- `integrations/gama/trajectory_live.gaml`: existing model import with a dedicated
  step-controlled experiment and explicitly reset RNG.
- `tools/gama_trajectory.py`: fixed-fixture XML conversion and geometric validation,
  followed optionally by HTTP replay. It hardcodes the fixture identity/seed and
  shallow-swim state; it is not a general behavioural experiment importer.
- `tools/gama_live.py`: single-flight GAMA WebSocket coordinator, with correlated
  step acknowledgements and fail-closed handling of uncertain command completion.

`artifacts/gama/trajectory_validation.json` records two equal 20-step actual GAMA
outputs, seed 184729, with canonical state-sequence hash
`61e3b8401d65548f336aee6f79bd7f355f3947fd81cdb660f3e2dbf5419ef143`.
`live_replay_validation.json` records their applied composed USD transforms.
The raw `/tmp/marlin-gama-fixture-final1` and `final2` XML files referenced by those
reports are no longer present. Therefore the saved record alone is historical
evidence; fresh execution with retained raw outputs remains necessary in M3.

`artifacts/gama/live_step_verification_02.json` records two equal live GAMA
trajectories, correlated command traces, actor pose checks and scene restoration.
Both GAML file hashes in that report match the current source. The failed first
attempt remains preserved separately. Historical evidence also records populated
scene coexistence, freeze on disconnect, actor release, a frozen capture audit and
actor-on/off pixel contribution. See the existing `integrations/gama/VERIFICATION.md`,
`LIVE_COMMUNICATION.md`, `CAPTURE_VERIFICATION.md` and
`COUNTERFACTUAL_VERIFICATION.md` for their bounded interpretations.

No recognisable-species, calibrated behaviour, visible-outline or five-GSD pairing
claim follows from the old few-pixel bottlenose preview.

## Component classification

"Implemented and tested" below distinguishes fresh offline checks from historical
live checks. "Fixture/mock" describes engineering scope, not an assertion that
the actual GAMA execution was fabricated.

| Component | Classification | Evidence and remaining scope |
| --- | --- | --- |
| GAMA headless circle and export | Fixture; historically executed and tested | Real GAML and saved reports exist; raw historical XML absent; fresh execution pending. |
| GAMA WebSocket coordinator | Implemented and tested | Three fresh offline protocol tests; historical actual-server report and matching model hashes. No current reconnect certification. |
| v1 exchange validator and buffer | Implemented and tested | Nine fresh tests, including mocked Kit router lifecycle. Lacks explicit run ID, step index and simulation step duration. |
| Optional Kit bridge endpoints | Implemented; historical live verification | NVIDIA Kit Services router. Current live service unreachable. Router mock tests do not establish live registration. |
| Single owned bottlenose actor | Implemented and tested | Eight fresh real-USD tests; historical Kit replay evidence. Only bottlenose/shallow_swim allowlisted. |
| Populated marine scene coexistence | Implemented; historical live verification | `marine_coexistence_01.json` and live-step report. Must be rerun for the porpoise and current scene. |
| Freeze without updates | Implemented and tested | No autonomous integration in owned actor; fresh unit tests and historical pause/disconnect checks. Explicit stale-update reporting remains to define. |
| Frozen capture and actor-on/off diagnostic | Implemented; historical live verification | Existing optional bridge capture and counterfactual routes. Requested five-GSD snapshot protocol is unverified. |
| Harbour porpoise asset | Implemented; previously verified for Pilot static use | Existing calibration and dependency hashes intact. Biological state/pose suitability remains provisional. |
| Harbour porpoise GAMA ownership and multi-state mapping | Missing | Current bridge rejects this species and all states except shallow_swim. Reuse ownership implementation. |
| Harbour porpoise behavioural GAML sequence | Missing | No existing surface/descent/submerged/ascent sequence in audited GAML files. |
| Ten seeds and fresh-process repetition | Missing | Old single-seed equal trajectories do not satisfy M5. |
| Human biological review | Missing for this sprint | Static Pilot proxy review does not approve dive/surface behaviour. |
| Five-GSD GAMA sets, 150-image acceptance set and trajectory splits | Missing | Pilot images are preserved but are not GAMA-driven acceptance evidence. |

## Existing exchange and control ownership

Canonical implementation is
`source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge/`.
The extension is version 0.1.0, depends on the existing render service and Kit
Services, and is absent from default application dependencies. Do not introduce
another HTTP framework or a second bridge.

Validation routes are `/integration/gama/validate`, `/steps`, `/status` and `/reset`.
Owned actor routes are `/integration/gama/actor/acquire`, `/step`, `/status`,
`/release` and `/capture`; the other diagnostic routes are
`/integration/gama/marine/audit` and `/integration/gama/capture/counterfactual`.
All suffixes here retain the `/integration/gama` prefix. Domain errors use
`ok:false`, so HTTP success alone is insufficient.

Current v1 uses SI metres in a local Y-up frame and heading 0=+Z, 90=+X,
180=-Z, 270=-X. Absolute position is authoritative; redundant depth/altitude must
agree with the fixed mean plane Y=0. The actor reads stage metres-per-unit on
acquisition and rejects later unit/axis changes. It creates an isolated anonymous
USD layer with one private actor and removes only that layer on release.
It does not enlist an autonomous swimmer or diving controller.

Current API status reads on 8 October returned connection refused for
`/integration/gama/status`, `/integration/gama/actor/status` and
`/debug/scene/inspection`. No Kit instance was started, stopped or restarted.
Consequently the actual current stage configuration cannot yet be certified.
The Pilot porpoise calibration requires Y-up and 0.01 m per stage unit; this is a
recorded Pilot requirement, not an assumption to impose on an unknown live stage.
M2 must inspect live metadata and explicitly validate the conversion.

The bridge boundary needs a versioned extension with explicit run identity,
step index, simulation time and step duration. Preserve existing v1 endpoints.
Choose one authoritative vertical input in the new contract, retain explicit
vertical reference, validate before any scene mutation, and define duplicates,
reset, interrupted replay and stale-state reporting. Mean sea level is the
existing bridge convention; any change must be explicit and tested.

## Fresh audit tests

[Machine-readable test results](qa/m1_test_results.json) record these successful
commands. They do not require Kit or change its scene:

```bash
python3 -B tools/test_gama_exchange.py
python3 -B tools/test_gama_live.py
/home/madil/opt/blender-5.0.1-linux-x64/5.0/python/bin/python3.11 -B tools/test_gama_actor.py
```

Results: 9 exchange/router tests, 3 offline WebSocket protocol tests and 8 real-USD
actor tests passed. USD tests check transforms and stage units, ownership, rejected
updates, exact layer restoration and visibility-only counterfactual intervention.
The remaining pixel-analysis and full MARLIN/camera regression suites were not
rerun in M1; historical passing results are preserved rather than relabelled fresh.

## Harbour porpoise selection and sprint gates

Retain the existing Pilot asset
`assets/cetaceans/model_75a_-_harbor_porpoise/working/calibration_v1/usd/harbour_porpoise_static_candidate.usd`.
All four recorded porpoise dependency hashes match. Its Pilot record documents
23,456 evaluated vertices, two meshes, -90 degree X correction and a provisional
publisher-based 1.555 m landmark length. The corrected bounding extent is about
0.419 x 0.433 x 1.601 m. Original source, rig, helpers and licence remain preserved.
Only a static shallow-swim proxy was reviewed; surface, descent, submerged and
ascent appearance are not yet approved. Use clearly labelled rigid pose proxies
only within engineering scope until reviewed, without inventing anatomy or biology.

Proceed in the specified order: contract, actual GAMA execution, transfer tests,
reproducibility and behavioural review, then frozen captures and the small test set.
Live tests require reachable MARLIN with the optional bridge enabled. Biological
suitability needs a named human reviewer and a recorded limited-use decision.
Neither requirement prevents offline contract/model work, but neither may be
silently marked passed.

The old GAMA directory's GEMINI instructions freeze development during the first
GSD sprint. That sprint is complete and the user has now authorized this explicit
GAMA sprint; its preservation constraints remain in force.

Milestone 1 status: **Passed for baseline preservation and offline audit**.
Current live verification remains pending; this is not completion of M2–M8.
