# M1 evidence verification and next-run restoration rules

The audit did not change production source, start controllers, restore a checkpoint, enable native annotators or render images. The API was unreachable at port 8011. The isolated metadata process returned its query and then required deadline cleanup; host checks after cleanup found no `kit` process. No live marine-state restoration is claimed or required by this audit.

From `/home/madil/kit-app-template`, verify this new packet read-only:

```bash
/usr/bin/python3 -B experiments/above_water_annotation_v1/qa/m1/verify_audit.py
```

The verifier checks the M1 file manifest, current canonical source/preset/asset pins, declaration counts/coverage, historical image copies, proposed framing and actual pending gate state. It does not launch Kit, change a scene, execute a new rendering campaign or grant Gate A.

To check the later accepted bottlenose package independently:

```bash
/usr/bin/python3 -B experiments/gama_dolphin_behaviour_v1/qa/m6/verify_gate_d_acceptance.py
```

The earlier ocean verifier still reports three superseded source pins, as documented in `qa/m1/ocean_preservation_verification.json`. Do not change old manifests or revert accepted bottlenose source to force it to pass. Use the separate M1 immutable ocean/preset pin audit and retain that distinction.

`qa/m1/prepare_gate_a.py` is the audit-only declaration/image-copy builder. It is **not** an implementation or capture entry point. It rewrites proposed local preparation files and must not be rerun on an accepted/sealed packet identity. For a revised proposal, use a versioned copy and a new manifest/review record.

The raw runtime query and executed command/log are retained for inspection. Do not automatically rerun that launch: it required timeout termination, and a later user may have opened MARLIN or other GPU work. No new source files, installed dependencies or annotation providers are needed for offline packet verification.

## Rules for a later authorised implementation/capture run

1. Recheck the currently running applications/API, GPU and free disk. Checkpoint any current user scene and record actual controller owners, stopped/running state, timeline time, camera/product, renderer settings and selection. Confirm the checkpoint bytes and external asset dependencies. A frozen USD checkpoint does not serialize Python controller histories.
2. Save explicit source prefixes, current controller/animation state and water/ocean configuration where resume is required. Use the existing ownership guards. Do not reconstruct a stopped controller as running merely because an old report did so.
3. Prefer private scene/layer transactions. Keep the current live stage attached/recoverable in the supported stage cache while private work runs. Keep accepted source assets/preset immutable and all output identities new.
4. On success or failure, detach/destroy only owned annotation products, release ownership and restore the recorded pre-work scene, settings, activity and camera. Verify actual composed state and relevant API status independently of a successful restore call.
5. A fresh-process test needs current checkpoint protection, explicit controller reconstruction and a reviewed finite lifecycle. If it requires closing a user's current application, obtain specific permission once the exact operation and restoration packet are ready. M1's completed isolated probe is not permission to close future user work.
6. Preserve failed captures and output incompleteness. Do not delete evidence, clear unrelated caches, disable resource guards or modify generated runtime/cache files. Recheck all protected pins after cleanup.

The CurrentSprint README identifies the new active specification. The old dolphin filename is an archive compatibility symlink needed by immutable historical acceptance records. Preserve its target bytes and resolution.
