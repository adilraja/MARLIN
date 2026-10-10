# GAMA–MARLIN reproduction and pending capture continuation

Run commands from `/home/madil/kit-app-template`. Python `-B` prevents bytecode-cache creation. Use a fresh exclusive output directory or stem on every execution; never replace retained attempts, Pilot results or existing seals. Canonical edits belong under `source/`; generated/cache directories remain outside inspection.

The recorded evidence uses GAMA 2025.6.4 / JDK 21.0.7+6, installed Blender 5.0.1 USD Python 3.11 for actual USD tests, and the retained Pilot environment for version-specific CPU detector-transform inspection. Exact executable/version/command pins are in each execution record. These instructions do not imply that the following commands were rerun after M8's final seal.

## Reproduce the M8 review checks

The already running Kit instance must expose HTTP at `http://localhost:8011`, with the original eleven-animal demonstration and ocean active. The read-only monitor checks movement, owner/root absence, configuration, camera/layers and API route presence without acquiring an actor or rendering:

```bash
/usr/bin/python3 -B tools/verify_gama_m8_demo.py \
  --output experiments/gama_marlin_v1/qa/m8_live_demo_reproduction_01
```

The M8 offline batch executes the canonical service, camera, bridge, capture and Pilot reconstruction tests with the recorded system/Blender runtimes:

```bash
/usr/bin/python3 -B experiments/gama_marlin_v1/qa/run_m8_offline_checks.py \
  --output experiments/gama_marlin_v1/qa/m8_offline_reproduction_01
```

The retained M8 execution passed all 360 unittest cases and the metric self-check. Its additional historical Pilot packaging command failed on an obsolete 1.6.0 specification assertion against the preserved final 1.7.0 specification. The batch consequently returns a failure status for that command. Review individual results and the [disposition](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m8_offline_01/historical_package_disposition.json); do not rewrite the historical script or Pilot output to hide the failure.

The [Pilot audit execution record](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m8_pilot_audit_02_execution.json) supplies its exact CPU-only command and exclusive output arguments. The checker loads no weights and performs no training/inference. The [audit document](/home/madil/kit-app-template/experiments/gama_marlin_v1/M8_READ_ONLY_PILOT_AUDIT.md) records installed library source hashes, input padding/transform details, exact metric recomputation and amodal annotation semantics.

Historical preservation can be checked into a new stem:

```bash
/usr/bin/python3 -B experiments/gama_marlin_v1/qa/run_m8_preservation.py \
  --stem m8_preservation_reproduction_01 --phase final
```

The wrapper deliberately preserves the existing historical checker's result schema; its separate execution record identifies M8 context. This checks historical protection, not a new final-report acceptance seal.

## Trace and reproduce actual numerical behavior

The [record-first procedure](/home/madil/kit-app-template/integrations/gama/PORPOISE_RECORD_FIRST.md), [M3 actual execution report](/home/madil/kit-app-template/experiments/gama_marlin_v1/M3_ACTUAL_GAMA_EXECUTION.md) and [M5 reproducibility report](/home/madil/kit-app-template/experiments/gama_marlin_v1/M5_REPRODUCIBILITY_AND_BEHAVIOURAL_REVIEW.md) describe the runnable GAML model, fixed configuration, raw GAMA export and canonical comparison.

For a new ten-seed/three-repeat numerical campaign, declare a fresh safe prefix before execution:

```bash
/usr/bin/python3 -B tools/run_gama_porpoise_m5.py \
  --campaign m5_m8_reproduction --declare-only
/usr/bin/python3 -B tools/run_gama_porpoise_m5.py \
  --campaign m5_m8_reproduction
```

These commands create new numerical execution evidence; they do not replace M7's immutable source selection or constitute a new biological review. The installed GAMA runtime must be available. Network/runtime permissions may be required on this host. Failed seeds or differing raw/canonical state must remain recorded.

The [v2 contract](/home/madil/kit-app-template/integrations/gama/STATE_CONTRACT_V2.md) and [replay procedure](/home/madil/kit-app-template/integrations/gama/PORPOISE_REPLAY_V2.md) govern Kit transfer: Y is vertical, X/Z are horizontal, heading 0° is +Z, and depth is positive below fixed mean sea level. Only the owned porpoise receives GAMA updates. Static pose mapping and engineering assumptions remain explicit. The [accepted M4 command/result](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m4_live_03/results.json) and [M6 capture procedure](/home/madil/kit-app-template/integrations/gama/PAIRED_CAPTURE_V2.md) retain their actual workload and cleanup evidence.

## Finish the immutable M7 selection

M7 still lacks only `m5_positive_seed_2147483647_a` steps 8, 16 and 32. Its [declaration](/home/madil/kit-app-template/experiments/gama_marlin_v1/m7_capture_declaration.json) predates image inspection. The current 120-image source campaign and frozen capture protocol must remain unchanged. Keep Kit running and its current scene in memory. Each capture requires at least **768 MiB free GPU memory** after actor acquisition; a pre-acquisition observation at that exact threshold does not guarantee enough headroom later.

First perform the read-only pending preflight with a fresh output:

```bash
/usr/bin/python3 -B tools/capture_gama_dataset_pending_v2.py \
  --output experiments/gama_marlin_v1/qa/m7_pending_preflight_reproduction_01 \
  --preflight-only
```

Once headroom is available, execute the prepared missing-only supplement:

```bash
/usr/bin/python3 -B tools/capture_gama_dataset_pending_v2.py \
  --output experiments/gama_marlin_v1/qa/m7_supplement_01
```

It replays the original test trajectory, captures only its three declared groups, retains exact bounded no-render retries and releases ownership in cleanup. An already existing output directory must receive a new attempt name. The tool refuses source/protocol changes, arbitrary replacement selections and recapture of the original accepted groups. Original failed campaign outcomes remain unchanged.

After a successful 30-image supplement, create the complete candidate set by immutable offline copying:

```bash
/usr/bin/python3 -B tools/aggregate_gama_dataset_v2.py \
  --supplement experiments/gama_marlin_v1/qa/m7_supplement_01 \
  --output experiments/gama_marlin_v1/qa/m7_capture_set
```

The aggregate retains the original failed source-campaign status and records every original/copy hash. Its own passed status means that all 15 accepted groups were assembled and checked; it does not claim one uninterrupted live campaign passed.

Before export, genuinely reopen and independently verify **all 15 copied groups** into a fresh `qa/m7_scene_validation_set` with `qa/verify_m7_group.py` under the installed Blender USD Python. Retain each actual command, log, return code and input/source hashes. Generate and inspect the three supplement contact sheets using `qa/build_m7_review.py`; its `--help` documents the bounded group/campaign interface. Retain original-source per-view observations. Use `qa/finalize_m7_review.py` only after complete copied-scene evidence and reviewed original sheets exist; it requires explicit byte-identical copy provenance rather than silently relabelling the original 120 proof or review records.

The strict exporter then requires complete 150-view capture, split, scene and manual-review evidence:

```bash
/usr/bin/python3 -B tools/export_gama_dataset_v2.py \
  --campaign experiments/gama_marlin_v1/qa/m7_capture_set \
  --scene-verifications experiments/gama_marlin_v1/qa/m7_scene_validation_set \
  --visual-review experiments/gama_marlin_v1/qa/m7_review/visual_inspection.json \
  --output experiments/gama_marlin_v1/datasets/m7_engineering_v1
```

The exporter copies images, labels and annotations, verifies source/copy hashes and preserves trajectory-family partitions. It performs no detector training. Final M7 QA/report/seal must be issued only after full acceptance. A later resource completion must be recorded as a new outcome without overwriting M8's historical decision or its sealed report.

Annotations remain direct amodal mesh boxes with unknown rendered visibility. Physical target absence does not mean wildlife-free background. Biological suitability, static pose, underwater refraction and observed paired-background shading differences require their own stated review scope before expansion.
