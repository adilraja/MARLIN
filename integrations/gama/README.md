# MARLIN–GAMA: optional state-exchange foundation

Status: **deterministic GAMA fixture and optional single-actor control; not ecology**.
No existing app, render-service code, camera, ocean, animal, asset or controller
is modified. The bridge is not enabled in the normal MARLIN launch. This first
increment implements the supplied manual's exchange boundary (sections 1–3).

GAMA 2025.6.4 is installed at `/opt/gama-platform`; `/usr/sbin/gama-headless`
points to its headless launcher. The fixture uses its legacy headless XML runner:
https://gama-platform.org/wiki/HeadlessLegacy . No download was needed.

## Contract and explicit assumptions

`step_v1.schema.json` describes the JSON structure. `examples/step_v1.json`
uses the user's example values; these are **not biological calibration**.
The receiver additionally checks finite numbers, duplicate IDs, and redundant
depth/altitude consistency. Unknown fields are rejected, including pixel positions,
asset paths and commands. Species identifiers are syntactically checked only;
asset availability and valid species/state combinations are not yet checked.

- `schema_version` defaults to `1.0` for compatibility with the manual's example.
- Positions are metres in MARLIN's **local Y-up frame**, not native GAMA/GIS
  coordinates. A future GAMA adapter must explicitly map its own coordinates.
- This v1 contract chooses mean sea plane **Y=0** as the depth/altitude datum.
  `depth_m=max(0,-y)` and `altitude_m=max(0,y)`, tolerance 1e-6 m. Neither is
  measured from moving waves. These are integration assumptions, not ecology facts.
- Heading: 0°=+Z, 90°=+X, 180°=-Z, 270°=-X, range [0,360).
- The pure conversion helper requires explicit metres-per-scene-unit; eventual
  rendering must read the actual stage metadata, never silently assume centimetres.
- Full snapshots, strictly increasing simulation time within a buffer run.
  Identical latest-step retries are idempotent. Seed is fixed until explicit reset.
  Agent order is significant for retry equality. Empty snapshots are allowed.
- No species changes for IDs present in consecutive steps. Absent agents have no
  retained history here; lifecycle/ID reuse policy must be established before rendering.
- Seed range [0,2^53-1] is a JSON interoperability bound; the eventual GAMA adapter
  must verify how its RNG accepts/seeds values. Max 1000 agents is a transport guard.
- One producer/run per receiver. The buffer holds only the latest step in memory;
  it is not an archival replay log. Reset/unload loses that buffer, not scene data.
- Validation-only routes never move anything. The separate `/actor` routes require
  explicit ownership and load just one allowlisted asset. Missing updates hold the
  last position: no timer, autonomous swimming, capture or renderer-setting writes.

## CPU-only verification (safe with MARLIN running)

```bash
cd /home/madil/kit-app-template
python3 -B tools/test_gama_exchange.py
```

## Optional Kit receiver smoke test

Do not start a second Kit instance or discard an in-memory scene to try this.
Use the following opt-in launch when Kit is stopped:

```bash
cd /home/madil/kit-app-template/_build/linux-x86_64/release
./cris.madil.kit.sh --enable cris.madil.render_service \
  --ext-folder /home/madil/kit-app-template/source/extensions \
  --enable cris.madil.gama_bridge
```

In another terminal:

```bash
curl --fail-with-body -sS -X POST http://localhost:8011/integration/gama/steps \
  -H 'Content-Type: application/json' \
  --data-binary @/home/madil/kit-app-template/integrations/gama/examples/step_v1.json
curl --fail-with-body -sS http://localhost:8011/integration/gama/status
```

Inspect JSON `ok`: domain validation failures currently use `ok:false` in the
response (HTTP success alone does not establish acceptance). `rendered:false`
is intentional. No animal moves when a step is accepted.

To return to standalone, release the test actor, then omit
`--enable cris.madil.gama_bridge` on the next normal launch (or disable just that
extension). No GAMA dependency was added to MARLIN's app or render service.
Disabling the bridge removes its private actor layer; existing scene data remains.
Use on a trusted local interface, as with the existing MARLIN API; multi-client
authentication/session ownership is not implemented.

## Deterministic engineering trajectory

`trajectory.gaml` generates 20 states: a 12 m circle, 3 degrees/second, Y=-0.8 m,
seed 184729. Seed controls the initial angular phase. These are **engineering test
values, not biological or waterline calibration**. GAMA emits local X/Z horizontal
coordinates explicitly; no GIS transform or implicit GAMA heading conversion is
used. Skeletal animation is not added by this fixture.

Run twice, using unused output directories (do not overwrite earlier evidence):

```bash
gama-headless -m 1024m -ws /tmp/marlin-gama-fixture-workspace \
  /home/madil/kit-app-template/integrations/gama/trajectory.xml /tmp/gama-check-a
gama-headless -m 1024m -ws /tmp/marlin-gama-fixture-workspace \
  /home/madil/kit-app-template/integrations/gama/trajectory.xml /tmp/gama-check-b
python3 -B /home/madil/kit-app-template/tools/gama_trajectory.py \
  /tmp/gama-check-a/simulation-outputs0.xml /tmp/gama-check-b/simulation-outputs0.xml \
  --output /tmp/gama-comparison.json
```

GAMA's installed launcher needs its `/opt` configuration writable to the user.
No sudo is prescribed. `-ws` isolates its workspace and avoids automatic cleanup
by the bundled launcher. The converter is specific to this fixed-seed fixture;
it is not a general GAMA experiment importer. Numerical equality, circle radius,
tangent heading, speed and all 20 timestamps are checked before replay.

With Kit/bridge running, add `--replay` and choose a fresh report filename:

```bash
python3 -B /home/madil/kit-app-template/tools/gama_trajectory.py \
  /tmp/gama-check-a/simulation-outputs0.xml /tmp/gama-check-b/simulation-outputs0.xml \
  --output /tmp/gama-replay.json --replay
```

This uses structured file exchange: GAMA completes the fixture first; Python then
replays its states via Kit HTTP. It is not a live WebSocket co-simulation. One-second
wall-clock delays are viewing aids, not the simulation clock. The script releases
the animal after playback, including ordinary exceptions/Ctrl+C. A killed client
leaves it stationary until explicit release or bridge disable.

Ownership API:

- POST `/integration/gama/actor/acquire`: create exactly
  `/MarlinGamaFixture/Bottlenose_001`; returns `ownership_token`.
- POST `/integration/gama/actor/step`: body `{"ownership_token":"…","step":{…}}`.
  Accepts only ID `Gama_Bottlenose_001`, species `bottlenose_dolphin`, state
  `shallow_swim`. No supplied asset paths or existing-actor takeover.
- GET `/integration/gama/actor/status`: buffer and independently read USD world pose.
- POST `/integration/gama/actor/release`: body `{"ownership_token":"…"}`. Removes
  only the private layer, even if the active stage has subsequently changed.

Repeated acquisition, stale tokens, foreign IDs, changed stage/units, and updates
during MARLIN's capture pause are rejected. Accepted steps author time/seed metadata
on the private root. `applied:true` means a USD transform update, **not** a verified
render or annotation. `rendered:false` remains accurate.

The actor matches the existing provisional gallery orientation/scale. Those values
are not physically calibrated. No camera is selected or reframed; the animal might
be outside the current viewport. The bridge has no effect on other swimming actors,
ocean waves, camera geometry or lighting. The actor is removed on extension unload;
do not disable/reload extensions during capture.

Additional USD tests:

```bash
/home/madil/opt/blender-5.0.1-linux-x64/5.0/python/bin/python3.11 -B \
  /home/madil/kit-app-template/tools/test_gama_actor.py
```

## Remaining work

Before live motion, review the rest of the integration manual, if any. Then:

1. Verify alongside a populated, animated marine scene (the first live replay uses
   a fresh Kit stage); validate capture metadata/annotations with an owned actor.
2. Decide the desired live GAMA transport, run/session lifecycle and disconnect policy.
3. Only then add literature-grounded ecological rules. A valid exchange or an
   installed GAMA runtime does not by itself establish biological realism.
