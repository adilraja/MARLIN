# M4 reproduction and rollback

Use `qa/m4/verify_package.py` to verify the sealed candidate without acquiring an
actor, starting Kit or regenerating evidence. This requires the retained local
artifact store and asset dependencies. The package does not redistribute Kit,
Blender or vendor material libraries.

```bash
/usr/bin/python3 -B experiments/gama_dolphin_behaviour_v1/qa/m4/verify_package.py
```

## CPU and service checks

Run the CPU suite with the installed USD interpreter and a new result filename:

```bash
/home/madil/opt/blender-5.0.1-linux-x64/5.0/python/bin/python3.11 -B \
  tools/test_gama_animated_v3.py /tmp/m4_new_cpu_result.json
```

The live lifecycle test uses the actual accepted reference trajectory and always
releases its private actor. It requires an idle MARLIN service with the optional
bridge loaded. Choose a new output name:

```bash
/usr/bin/python3 -B experiments/gama_dolphin_behaviour_v1/qa/m4/live_contract_test.py \
  --name live_contract_new_run
```

The animated API prefix is `/integration/gama/v3/animated_actor`. Acquire with
`{"agent_id":"Bottlenose_001"}`, then retain the returned `ownership_token`.
Submit complete accepted v3 steps in order, or query a timestamp inside the
retained two-step bracket. Pause/reset/release retain M2 semantics. The static
v3 and animated owners share an exclusive namespace; neither may acquire over
the other. Never run a legacy autonomous swimmer on this private instance.

## Preserved visual evidence

The final dry clip is:

```text
/home/madil/kit-app-template/artifacts/gama_dolphin_behaviour_v1/m4/dry02/review_30s.mp4
```

The final above-water-camera marine clip is:

```text
/home/madil/kit-app-template/artifacts/gama_dolphin_behaviour_v1/m4/review01/review_30s.mp4
```

Both have 300 encoded frames at 10 fps. The labelled simulation-time windows are
edited excerpts, played at one second per simulation second within each window.
Original PNGs, per-frame JSON, pose USD snapshots, camera settings, subtitle files
and capture results remain beside them. Contact sheets are under `qa/m4/figures`.

The raw sidecars predate a descriptive mapping-label correction. Their numeric
TRS/root/phase state was verified against the final evaluator for every candidate
frame; the capture-source snapshot and correction are retained. Original sidecars
were not edited to appear as later output.

## Native harness and display recovery

The native worker was an audited local QA script with fixed smoke/review/dry jobs,
not an HTTP code-execution endpoint. It retained the live stage, attached one
disposable frozen copy, captured on one viewport and restored the original stage
in `finally`. All original source asset/material/calibration bytes were preserved.

The workstation's XWayland display reported 0×0 and no active outputs. Attempts
to create a GUI swapchain failed with 65k dimensions; explicit window settings
alone were insufficient. `--no-window` with rendering enabled recovered native
captures. The user confirmed Ubuntu 26.04 with Wayland and an active display.
A later XWayland check returned a valid 1366×768 output. The final service was
then restored with its normal window and has no polling QA worker. No desktop,
SDK or driver change was needed. The zero-sized XWayland observation was a
transient session condition; it did not establish that the monitor was off.

Do not rerun completed worker jobs or restore scripts in place: their output IDs
and evidence files deliberately refuse overwrite. If further native captures are
needed, use new output/job identities and retain the current live checkpoint first.
The final GUI command is preserved in `qa/m4/live_restore_gui_final/launch.json`;
the earlier offscreen command remains in `qa/m4/live_restore_final/launch.json`.

## Exact original-scene rollback

The pre-work scene was already stationary, with ocean/chase and swimmer/gallery
controllers stopped and the original water selection. Its checkpoint is
`checkpoint_4fde7e3u`. The original and final USD/metadata copies are in
`qa/m4/live_before` and `qa/m4/live_gui_final`. Final GUI checkpoint ID:
`checkpoint_crnswl_g`. The interim offscreen checkpoint `checkpoint_cgp8owp0`
remains in `qa/m4/live_final`.

The temporary ocean controller was stopped, the pre-work checkpoint was restored
and both v3 owners were released. The final 38-prim scene matched every composed
attribute and relationship without an ocean exception. Viewport and renderer
settings also matched. No further rollback is currently required.

When a separate future operation needs recovery, checkpoint any new work, release
an active owner, stop competing controllers and use the existing checkpoint
restore endpoint with the recorded ID. Preserve the source checkpoints; a frozen
scene does not serialize arbitrary Python subscriptions or controller history.

Gate C is still a human decision. This package does not complete M5's full
sequence/reload/recovery work or certify biological, optical or survey validity.
