# M5 reproduction and rollback

## Verify the preserved campaign

From `/home/madil/kit-app-template`:

```bash
/usr/bin/python3 -B experiments/gama_dolphin_behaviour_v1/qa/m5/verify_package.py
```

This is read-only. It requires the retained local artifact/checkpoint store,
source assets/licences and the prior sealed sprint evidence. The native Kit,
Blender/USD and GAMA runtimes and vendor libraries were not redistributed or
claimed to be entirely byte-pinned. Actual M3 GAMA output, current source pins,
native build/driver/settings and dependency manifests provide the recorded
provenance. No newly generated GAMA trajectory was substituted.

## Media and snapshots

Full normal-speed movie:
`/home/madil/kit-app-template/artifacts/gama_dolphin_behaviour_v1/m5/primary02/full_sequence_74s.mp4`.

The movie contains all 370 0.2-second presentation frames from t=0 through 73.8,
played at 5 fps for 74 seconds. Terminal t=74 is preserved as a frozen snapshot.
`qa/m5/frozen_state_index.json` locates all 23 primary frozen states and binds
their scene, evaluated skin and sidecar bytes. Each capture retains native
`hdr.npz`, `hdr.exr`, effective camera/product settings, actual root/joint state
and fixed derived displays. No native PNG qualification was inferred.

The static USD includes resolved pose and scene geometry. To resume/seek the
experimental actor, restore the preserved baseline, acquire one animated v3
owner, reset its buffer and deliver the retained contiguous M3 prefix up to the
selected bracket before evaluating the desired time. Retain source sequence,
buffer samples, phase/weight and camera/ocean/lighting controls. Do not import an
old ownership token or call this stateless reconstruction. The native frozen
audit verifies the four SDK-provided lighting defaults that generic USD cannot
expand; their effective values remain in each sidecar.

## Re-execution rules

Completed output directories and immutable records deliberately refuse overwrite.
For another campaign, create a versioned protocol and new allowlisted run IDs,
save the current scene first, and retain failures and amendments. Reuse
`native_m5.py` with the accepted actor and `capture_hdr`; never run completed
`host_launch.py` identities in place or overwrite current review media.

The final finite entry point was `qa/m5/entry_audit.py`; it ended after checking
the saved files. No general HTTP code executor, external web framework, global
timeline animation controller or permanent QA poller was introduced. Canonical
runtime source was unchanged. Known Kit launcher execution was the only use of
the generated build; no generated runtime/cache files were inspected or edited.

## Rollback

The pre-work baseline was `checkpoint_a45rjwei`.
Its copied USD and metadata are under `qa/m5/live_before`. Final restored state
was `checkpoint_9h35bd4l`, copied under `qa/m5/live_final`. The final
normal MARLIN GUI on port 8011 retained the same stopped ocean/chase/swimmer/
gallery controllers and original water selection. The complete 38-prim scene and
settings matched exactly, so no further rollback is required.

For a later operation, checkpoint any newer user work before restoring a recorded
checkpoint through `/debug/scene/checkpoint/<id>/restore`. A frozen checkpoint
does not restore arbitrary Python controller histories. Do not start controllers
that were stopped in the pre-work record. M6 and Gate D remain separate work.
