# Bottlenose sprint reproduction and rollback

## Verify the final technical candidate

From `/home/madil/kit-app-template`:

```bash
/usr/bin/python3 -B experiments/gama_dolphin_behaviour_v1/qa/m6/verify_package.py
```

This performs read-only manifest/preservation checks. It requires the retained
local artifact/checkpoint store, asset/licence files and historical Git source
versions. Kit/Blender/GAMA/vendor libraries are not bundled or asserted entirely
byte-pinned. The new M6 live test used the running Kit build and existing public
HTTP endpoints without a restart or installed dependency edits.

## Reproduce the same bounded demonstration

Use the actual retained M3 reference sequence and unchanged animated v3 owner.
GAMA owns root movement; local joint animation consumes simulation-time phase.
Deliver contiguous states, retain the two-state bracket, reset and replay the
prefix before an out-of-bracket seek. Do not reuse an old ownership token or
advance the shared timeline as an independent animal clock.

The [M5 reproduction guide](M5_REPRODUCTION_AND_ROLLBACK.md),
`qa/m5/frozen_state_index.json` and the full native HDR/EXR/scene/skin sidecars
specify camera, exposure, render settings, phase, weight, buffer, ocean geometry
and lighting. The 23 primary frozen states and 35 total reopened scenes were
tested. Four native lighting defaults require the recorded NVIDIA schema/runtime
and were checked by the native audit; generic USD alone cannot expand them.

Full movie:
`/home/madil/kit-app-template/artifacts/gama_dolphin_behaviour_v1/m5/primary02/full_sequence_74s.mp4`.
It is 74 seconds at 5 fps, with derived fixed HDR display. No native LDR or
biological/survey qualification follows. Ocean phase zero and existing-cycle
manoeuvre limits are part of the accepted technical protocol.

## Repeat tests without overwriting evidence

`qa/m6/locked_plan.json` records the 26 regression commands and module paths.
Use new result paths/attempt identities for any re-execution. The system Python
Sony skip was resolved by the unchanged six-test suite in Blender USD; retain
both the first attempt and retry. The current native wave regression and public
API coexistence transaction are in `qa/m6/live_attempt01`.

Completed scripts intentionally refuse to overwrite output identities. Before
another live transaction, checkpoint the current user scene, verify controller
and ownership state, version the output identities and keep the existing guards.
Do not run completed launch/capture jobs in place. Canonical source under
`source/` remains authoritative; generated builds/caches are not edit targets.

## Rollback already demonstrated

M6 preserved `checkpoint_cz18f3os` before
testing and restored that exact frozen scene after stopping its temporary
controllers and releasing the private actor. Final checkpoint was
`checkpoint_9zoknw14`; copied USD/metadata and API states are in
`qa/m6/live_before` and `qa/m6/live_final`. All 38 composed prims/properties and
the original settings/controller states matched without exceptions.

The current original scene was already stationary: ocean, swimmer, gallery and
chase controllers were stopped, with original water selected. They were restored
stopped. No further rollback is required. For a later recovery, save any newer
work first, release the bridge-owned actor, stop the operation's temporary
controllers, and use `/debug/scene/checkpoint/<id>/restore` with the recorded ID.
Frozen checkpoints do not serialize arbitrary Python histories; reconstruct only
controllers documented as running in that operation's pre-work state.

Gate D remains a named human decision. This guide and the final technical seal
do not record visual/biological acceptance or authorize a new research use.
