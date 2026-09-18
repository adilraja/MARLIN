# Live step-controlled GAMA coordinator

Status: **live verification passed, 2026-09-18** with installed GAMA 2025.6.4.
Two independent 20-step trials produced identical trajectories. Each step was
acknowledged before reading state and applying its verified USD pose. Pause,
intentional socket disconnect, isolated actor release, and marine-scene preservation
checks all passed. The temporary server was stopped after the test.

Evidence: `artifacts/gama/live_step_verification_02.json`. The initial failed attempt
is retained in `live_step_verification_01.json`; it failed its initial seed check
before acquiring any MARLIN actor. The fix uses a dedicated `live_fixture` experiment
and explicitly simulation-scoped expressions, rather than ambiguous inherited
experiment seed values.

## Isolation and protocol

`tools/gama_live.py` uses the installed GAMA headless WebSocket protocol:
[official server documentation](https://gama-platform.org/wiki/HeadlessServer).
It sends `step` with `nb_step:1, sync:true`, waits for a correlated success response,
reads the simulation variables, validates cycle/time/seed/geometry, and then sends
the state to the existing MARLIN owned-actor endpoint. It never sends `play` and
never retries an uncertain step. Local-only client URLs are enforced.

Two independent connections load the same engineering fixture, run 20 steps each,
and compare the complete resulting trajectories. Both runs test a two-second pause
at step ten and a two-second actor hold after deliberate WebSocket disconnect.
Existing eleven-animal swimming, ocean progression, lighting, cameras and settings
are checked around these events. The owned MARLIN actor is explicitly released.
Reports include command/response traces, applied snapshots and before/after audits.

`trajectory_live.gaml` imports the existing offline fixture and resets the RNG
to 184729 before drawing the initial phase. The original file-replay fixture and
all MARLIN core source remain unchanged. These remain engineering values, not
biological behaviour. No new capture, skeletal animation or visibility claim is made.

## Server binding requires attention

The installed GAMA 2025.6.4 server constructor uses `InetSocketAddress(port)`:
it binds all interfaces. Its installed help lists no loopback-bind option.
Connecting the client to 127.0.0.1 does **not** restrict the server listener.
The service can load models and evaluate expressions; do not expose it to untrusted
networks. Only start this temporary server with explicit approval or appropriate
network isolation. No firewall or installed GAMA changes were made.

## Repeatable commands (after server exposure is approved)

Use a dedicated client environment, not Kit's Python:

```bash
python3 -m venv /tmp/marlin-gama-client
/tmp/marlin-gama-client/bin/pip install -r /home/madil/kit-app-template/integrations/gama/requirements-live.txt
```

In a terminal, start the installed GAMA server with its own workspace; choose an
unused port and do not start over an existing server:

```bash
gama-headless -m 1024m -ws /tmp/marlin-gama-live-workspace -socket 6868
```

With the optional MARLIN bridge enabled and the eleven gallery swimmers/ocean
already running (root `RUN_COMMANDS.md`), use a fresh report filename:

```bash
cd /home/madil/kit-app-template
/tmp/marlin-gama-client/bin/python3 -B tools/gama_live.py \
  --server ws://127.0.0.1:6868 --marlin http://127.0.0.1:8011 \
  --output artifacts/gama/live_step_verification_new.json
```

Stop the temporary GAMA server with Ctrl+C in its own terminal after the test.
The coordinator does not send a global server-exit command or stop other clients.
It closes its own sockets; GAMA documents disposal of client experiments on closure.
This test covers deliberate connection closure, not OS process kill, server crash
or a blackholed network. A killed coordinator can leave the MARLIN animal at its
last state; disable only the bridge to release its layer, outside capture activity.
If release fails, the report/error must be reviewed; do not assume cleanup succeeded.

Offline protocol tests:

```bash
python3 -B /home/madil/kit-app-template/tools/test_gama_live.py
```

Three protocol tests passed, alongside nine exchange tests and five USD actor tests.
The live GAML model compiled and ran successfully in the installed server.
Its JSON transport rounds float values to eight decimal places; engineering checks
allow 1e-6 m/radius and 1e-6 degree/tangent error, and 1e-8 m/s speed error. Repeated
live trajectories were compared exactly; no tolerance was used for repeat equality.

Both trials verified all eleven swimmers advanced without deformation errors and
the ocean advanced during pause/disconnect. Ocean parameters, renderer settings,
lighting/material/camera attributes and the active overview camera were unchanged.
The owned layer was removed on release, restoring the initial layer stack.

This is a bounded live communication milestone, not biological validation,
render visibility certification, continuous unattended streaming, automatic
reconnection, server-crash recovery or network-blackhole testing. No new capture
was taken. MARLIN's existing scene was left running.
