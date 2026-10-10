# GAMA–MARLIN completed sprint reproduction

The completed engineering sprint used actual GAMA trajectories, deterministic MARLIN replay and a verified 150-image capture set. This is the current guide as of **10 October 2026**, Europe/Dublin. The [sprint closeout](/home/madil/kit-app-template/experiments/gama_marlin_v1/GAMA_MARLIN_SPRINT_CLOSEOUT.md) and [current status](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/sprint_closeout_01/current_status.json) define its accepted scope. The original [M8 reproduction instructions](/home/madil/kit-app-template/experiments/gama_marlin_v1/M8_REPRODUCTION.md) preserve the earlier capture-pending state.

Run commands from `/home/madil/kit-app-template`. Use Python `-B` and a fresh result filename for each execution. Retain the actual command, stdout/stderr log, return code and source hashes. Existing reports, capture attempts, datasets and seals remain immutable. Generated directories and bytecode caches remain outside inspection.

## Verify the completed evidence

The new evidence verifier reads retained files, checks source and output hashes, and writes an exclusive result. It verifies the complete M7 seal and later execution receipts, the historical M8 seal, retained regression and Pilot results, and the old review's input pins. The historical temporary recipe is checked through its sealed byte-identical retained copy. Verification uses no live Kit, rendering, GAMA or detector execution.

```bash
/usr/bin/python3 -B experiments/gama_marlin_v1/qa/sprint_closeout_01/verify_existing_evidence.py \
  --output experiments/gama_marlin_v1/qa/sprint_closeout_01/existing_evidence_reproduction_01.json
```

Choose another unused filename if this result already exists. The [closeout validation result](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/sprint_closeout_01/existing_evidence_validation.json) and [recorded execution](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/sprint_closeout_01/existing_evidence_execution.json) provide the first completed check and its exact command.

The original M7 seal checker also supports a fresh result directly inside its own completion directory:

```bash
/usr/bin/python3 -B experiments/gama_marlin_v1/qa/m7_completion_01/check_finalization_seal_retry_02.py \
  --output experiments/gama_marlin_v1/qa/m7_completion_01/seal_check_closeout_reproduction_01.json
```

This command rehashes all 4,827 sealed outputs and binds the seal's own hash and completed finalizer receipts. Its output-directory restriction is part of the unchanged checker contract.

## Trace the actual capture workflow

The [record-first procedure](/home/madil/kit-app-template/integrations/gama/PORPOISE_RECORD_FIRST.md), [state contract](/home/madil/kit-app-template/integrations/gama/STATE_CONTRACT_V2.md), [replay procedure](/home/madil/kit-app-template/integrations/gama/PORPOISE_REPLAY_V2.md) and [frozen paired-capture procedure](/home/madil/kit-app-template/integrations/gama/PAIRED_CAPTURE_V2.md) explain the engineering demonstration. GAMA supplies position, heading, speed and depth; MARLIN applies the static pose mapping and renders the frozen scene through NVIDIA Kit Services.

The retained runtimes were GAMA 2025.6.4 with JDK 21.0.7+6, installed Blender 5.0.1 USD Python 3.11 for saved-scene checks, and the recorded Pilot environment for the read-only detector-transform audit. Exact executable paths, runtime versions and source hashes remain in each execution record.

The completed set reused five actual M5 trajectories, with seeds 1, 42, 184729, 20261008 and 2147483647, and snapshots at steps 8, 16 and 32. Five GSD conditions produced 75 present/removed pairs and a 90/30/30 train/validation/test split. The [M7 completion report](/home/madil/kit-app-template/experiments/gama_marlin_v1/M7_COMPLETION_REPORT.md) records the actual four-origin continuation and its memory constraints. The old single-supplement recipe describes the earlier plan; the actual continuation used three ten-image contributions and preserved failed overall attempt statuses.

The exact accepted offline commands, logs and hashes are retained in the [aggregate execution](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_completion_01/aggregate_execution.json), [fresh fifteen-group verification execution](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_completion_01/campaign_verifier_execution.json), [review execution](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_completion_01/review_execution.json), [export execution](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_completion_01/export_execution.json), [acceptance execution](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_completion_01/acceptance_retry_02_execution.json) and [completion execution](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_completion_01/finalize_retry_02_execution.json). Those commands used exclusive output directories; their already completed destinations must not be overwritten.

The retained dataset and [all fifteen contact sheets](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_review/index.md) are the accepted bounded set. New capture generation is a separate workload with a new declaration and output space. Each render still requires at least 768 MiB free GPU memory at the guarded pre-render check. Restarts used for the completed continuation reset animation phases and did not establish a permanent memory fix.

## Interpret the regression and Pilot evidence

The [M8 regression execution](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m8_offline_01/results.json) retains 360 passing unittest cases with zero skips and a passing metric contract self-check. The complete historical batch retained `passed: false` because its additional packaging command asserted the obsolete 1.6.0 specification version. The [disposition](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m8_offline_01/historical_package_disposition.json) explains its mismatch with the preserved completed 1.7.0 specification. That batch is not an all-green closeout verifier, and its failed outcome remains unchanged.

The [Pilot audit execution](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m8_pilot_audit_02_execution.json) binds the read-only audit of the detector's full input path, AP convention and annotation semantics. The [detailed audit](/home/madil/kit-app-template/experiments/gama_marlin_v1/M8_READ_ONLY_PILOT_AUDIT.md) preserves its limitations. No training, inference or replacement performance result was needed for this closeout.

The latest retained [marine demonstration result](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_completion_01/final_live_demo/results.json) passed 14 restoration/movement checks and four API route checks after the final captures on 9 October 2026 UTC. It is a dated executed observation; this offline closeout does not certify a new live session.

Engineering acceptance applies to the traceable static-pose test set. Biological suitability remained provisional; MAR's review accepted engineering use only. Direct amodal labels, unknown rendered visibility, unlabelled background wildlife, uncalibrated refraction and observed paired-background differences remain explicit. Scientific use or larger biological expansion requires its own supported review scope.
