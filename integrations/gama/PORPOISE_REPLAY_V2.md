# M4 — Owned porpoise replay

The M2 validation-only endpoints retain their original semantics. M4 adds an
explicit, separate scene owner using NVIDIA Kit Services and the existing
removable private-layer lifecycle. No GAMA server is needed for recorded replay.

## Acceptance limits declared before execution

- Euclidean world-position error: at most **0.00001 m**.
- Circular heading error: at most **0.0001 degrees**.
- Duplicate, rejected update and interrupted replay: exactly unchanged composed
  transform and accepted-step count; one owned animal, no extra layer.
- Release: original layer stack, camera, renderer, lighting and materials restored;
  existing gallery/ocean controllers retain their configuration and advance.

Expected coordinates are calculated independently from the input:
`[x, -depth_m, z]`, divided by the explicitly authored positive stage
`metersPerUnit`. Heading is measured from the **composed USD root matrix** using
`atan2(forward.x, forward.z)`. Mean sea level is the contract's fixed Y=0 plane,
not the instantaneous wave surface or anatomical clearance.

## Scene API

All routes below are under `/integration/gama/v2/actor`:

| Method/path | Body | Effect |
|---|---|---|
| POST `/acquire` | `{"agent_id":"Porpoise_001"}` | Bind one safe agent ID and return an ownership token. |
| POST `/step` | `{"ownership_token":"…","step":{…v2…}}` | Validate, order-check, then atomically author the one root transform. |
| GET `/status` | — | Report composed pose, one-actor count, accepted count and transport state. |
| POST `/reset` | `{"ownership_token":"…"}` | Clear replay ordering/count; hold pose, layer and ownership while awaiting a new explicit run. |
| POST `/release` | `{"ownership_token":"…"}` | Remove only the saved owned layer, even after active-stage replacement. |
| POST `/capture` | `{"ownership_token":"…"}` | Temporarily view the actual actor with an owned diagnostic camera; restore camera/layer/gate afterward. |
| POST `/cleanup-empty-root` | `{}` | Explicit unowned repair limited to an empty private root and allowlisted diagnostic RTX exposure placeholders; refuses defined cameras, animals and other authored content. |

Check JSON `ok`, including when HTTP status is 200. Wrong tokens, extra envelope
fields, unknown agents, invalid states/clocks, changed run identity and old steps
are rejected without changing the animal. Identical latest-step retries refresh
connectivity but never author USD again or advance the accepted count. Acquire
refuses an existing owner/root. No automatic creation occurs on `/step`.

## One owner, freeze and recovery

The actor is `/MarlinGamaPorpoise/Porpoise_001`, outside the autonomous gallery's
`/World/Cetaceans` targets. It has no simulation/update subscription, speed
integration, wave following, dive controller or autonomous fallback.

`awaiting_first_update` holds the initial/last pose. After receipt, status reports
`holding_last_state`; after **2 wall-clock seconds** without a valid update it
reports `frozen_updates_missing`. This diagnostic threshold is an engineering
assumption independent of GAMA simulation time. Status checks detect capture
gates, changed active stage/coordinate metadata, missing layer/actor, inherited
parent transforms and stronger composed-pose overrides as
`frozen_guard_failure`. An unchanged valid retry or the next ordered state
reconnects using the same token; release/reacquire requires a new token. No HTTP
connection owns the actor, so closing/reopening a client does not relinquish it.
Extension shutdown removes its layer rather than persisting tokens across process
restarts. M4 tests reconnecting the HTTP client, not recovery of a crashed Kit process.

## Asset and pose scope

The fixed allowlisted porpoise asset and dependencies must match the existing
pilot calibration hashes. Existing rotation `[-90,0,0]` and metric conversion
are reused; source assets and registry remain unchanged.

`static_pose_proxy_v1` maps all five state labels to that same static upright
mesh, with root depth/heading supplied by GAMA. It does not invent dive pitch,
rig motion, breathing or new biological calibration. Diagnostic close-ups are
for state-transfer inspection, not the later calibrated survey-capture workload.

## Repeat the checks

Run `tools/test_gama_actor_v2.py` with Blender's USD-enabled Python and `-B`.
Run `python3 -B tools/verify_gama_porpoise_live.py --prepare-demo --output <new-directory>`
against the running Kit app with both MARLIN extensions enabled. The latter
constructs the existing demonstration only if it is empty, rejects partial
non-running scenes, compares four manual cardinal fixtures separately from all
41 retained actual M3 GAMA states, exercises failure/recovery, captures actual
frames, and releases only its actor in `finally`. Do not reuse an evidence directory.
