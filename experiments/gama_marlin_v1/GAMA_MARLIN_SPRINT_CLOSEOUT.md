# GAMA–MARLIN sprint closeout

Sprint: **GAMA–MARLIN Behavioural Integration and Validation**. Closeout date: **10 October 2026**, Europe/Dublin.

**The sprint was completed for its bounded engineering scope. Milestones 7 and 8 were closed.** The declared 150-image capture and annotation set was completed, independently verified, reviewed and exported. The regression review, Pilot audit and expansion decision were completed. Biological suitability remained provisional; MAR's review accepted engineering use only.

This addendum provides the current status required by the [sprint specification](/home/madil/kit-app-template/Codex-Instructions/Current-Sprint/GAMA_MARLIN_SPRINT_SPECIFICATION.md). The [original M8 sprint report](/home/madil/kit-app-template/experiments/gama_marlin_v1/GAMA_MARLIN_SPRINT_REPORT.md) and [original reproduction instructions](/home/madil/kit-app-template/experiments/gama_marlin_v1/M8_REPRODUCTION.md) remain dated historical records. Their earlier M7 blocker and incomplete sprint status describe the evidence available before the final 30 captures. Those reports, seals and failed outcomes were preserved unchanged.

The [current machine-readable status](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/sprint_closeout_01/current_status.json) records engineering sprint acceptance as complete. Historical M7 and M8 seals retain their original `sprint_acceptance_complete: false` values; this later closeout supplies the current decision.

## Current milestone status

Every passed outcome below applies to its stated engineering or review scope. Earlier unsuccessful attempts remain part of the evidence.

| Milestone | Current outcome | Executed evidence |
| --- | --- | --- |
| 1 — Preserve Pilot and audit GAMA | Implemented and executed; baseline preservation and audit passed. | [Baseline test commands and results](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m1_test_results.json), [preserved inventory](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/preserved_output_manifest.json) |
| 2 — State contract and ownership | Implemented and executed; contract, units, ownership and invalid-state rejection passed. | [Offline commands and results](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m2_offline_results.json), [live HTTP results](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m2_live_results.json) |
| 3 — Actual GAMA trajectories | Implemented and executed; actual generation and repeatability passed. Biology remained provisional. | [Validation and command links](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m3_validation.json), [fresh run A execution](/home/madil/kit-app-template/experiments/gama_marlin_v1/trajectories/m3_seed_184729_a/execution.json), [fresh run B execution](/home/madil/kit-app-template/experiments/gama_marlin_v1/trajectories/m3_seed_184729_b/execution.json) |
| 4 — State transfer and recovery | Implemented and executed; composed-transform accuracy, failure handling, ownership and recovery passed. | [Offline commands and results](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m4_final2_offline_results.json), [accepted live replay](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m4_live_03/results.json) |
| 5 — Reproducibility and behavioural review | Engineering reproducibility passed and named human review was completed. Biological suitability remained provisional, engineering use only. | [Analysis and actual executions](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m5_analysis.json), [MAR review](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m5_human_review.json) |
| 6 — Frozen five-GSD captures | Implemented and executed; frozen pairing, capture-order and delay checks, and restoration passed. | [Accepted live results](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m6_live_03/results.json), [independent saved-scene verification](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m6_scene_validation_03.json), [executed capture report](/home/madil/kit-app-template/experiments/gama_marlin_v1/M6_FROZEN_STATE_PAIRED_CAPTURES.md) |
| 7 — Small capture and annotation set | **Complete.** All 150 declared images passed traceability, scene verification, presentation review, grouped split and export acceptance. | [Acceptance result](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_completion_01/acceptance_retry_02.json), [actual acceptance command](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_completion_01/acceptance_retry_02_execution.json), [independent seal check](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_completion_01/seal_check_retry_02.json), [completion report](/home/madil/kit-app-template/experiments/gama_marlin_v1/M7_COMPLETION_REPORT.md) |
| 8 — Regression review and expansion decision | **Complete.** The retained regression and Pilot review, current reproduction guidance and explicit expansion decision satisfied the engineering closeout. | [Regression commands and results](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m8_offline_01/results.json), [Pilot audit execution](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m8_pilot_audit_02_execution.json), [historical review validation](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m8_final_review_validation.json), [current reproduction guidance](/home/madil/kit-app-template/experiments/gama_marlin_v1/SPRINT_CLOSEOUT_REPRODUCTION.md) |

## Completed capture set

Five actual retained M5 GAMA trajectories supplied three declared snapshots each, at steps 8, 16 and 32. Every snapshot used five nominal GSD conditions: 0.5, 1, 2, 3 and 4 cm/px. The set contained **75 target-present and 75 physically target-removed images**, in 15 groups and 75 camera-condition pairs. The exported split contained **90 train, 30 validation and 30 test images**. Related trajectories, snapshots, GSD views and removed counterparts stayed in one partition.

The original 120 images remained unchanged. The remaining 30 were captured with controlled Kit restarts between bounded attempts. The accepted set combined valid groups from four source attempts with preserved overall statuses `[false, false, true, true]`. It retained byte-identical original-to-copy provenance. The earlier failed 20-image attempt remained excluded. The complete set was accepted as an explicit aggregation of valid groups; failed campaigns were not relabelled as successful.

All 15 saved scene groups received fresh independent USD verification. All 150 projections passed, with maximum projection-matrix error zero. The evidence retained 1,680 frozen-state checks, 450 settling probes, 180 restoration checks and 135 coexistence checks. All 150 views had source-bound presentation observations. The export copied the 150 RGB images, 150 YOLO labels and 150 annotation JSON files unchanged.

The [dataset manifest](/home/madil/kit-app-template/experiments/gama_marlin_v1/datasets/m7_engineering_v1/manifest.json), [contact sheets](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_review/index.md) and [M7 completion seal](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/milestone_7_manifest.json) contain the detailed provenance and acceptance scope.

## Regression and preservation

The retained M8 regression execution passed **360 unittest cases with zero skips**, together with the metric contract self-check. Its additional historical packaging command failed because it asserted specification version 1.6.0 against the preserved completed Pilot version 1.7.0. That failed command and batch outcome remained unchanged, with the [version disposition](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m8_offline_01/historical_package_disposition.json) retained. Engineering closeout did not imply that every historical command passed.

The [read-only Pilot audit](/home/madil/kit-app-template/experiments/gama_marlin_v1/M8_READ_ONLY_PILOT_AUDIT.md) documented the detector input-resizing path, AP aggregation and direct amodal-box interpretation. The latest retained [marine demonstration check](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_completion_01/final_live_demo/results.json), executed on 9 October 2026 UTC, passed all 14 checks and four API route checks after the final captures. All eleven original swimmers and the ocean advanced, and configuration, camera, layers and actor cleanup checks passed.

The new [offline evidence validation](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/sprint_closeout_01/existing_evidence_validation.json), with its [actual command and log receipt](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/sprint_closeout_01/existing_evidence_execution.json), rechecked all 4,827 M7 sealed outputs and 119 historical M8 outputs, the retained regression and Pilot evidence, and historical report inputs. It preserved 4,859 unique input pins before and after. This closeout used those retained test and live results; it performed offline integrity verification without a new regression, rendering, GAMA or ML workload.

## Expansion decision

| Decision | Current outcome and basis |
| --- | --- |
| Further bounded engineering tests | **Ready.** Actual GAMA execution, faithful state transfer, deterministic replay, frozen pairing and the complete declared capture/export set were demonstrated. |
| Limited behaviour-conditioned research study | **Not established.** Supported rendered states and behavioural assumptions still require acceptance for a stated scientific use. MAR's review remained provisional, engineering use only. |
| Larger biological experiment | **Not ready for expansion.** Material pose, optical, annotation and biological-evidence limits remained. |

The animal used a static upright pose proxy. Biological body pitch, rig animation, breathing, wave and anatomical water clearance, and underwater refraction remained unvalidated. Labels represented direct amodal evaluated-mesh rectangles; rendered visibility remained unknown. Only the owned harbour porpoise was labelled as class 0. Demonstration wildlife remained unlabelled background, including in target-removed images. Some paired backgrounds differed in shading or detail for an unestablished reason, so photometric equivalence remained unclaimed.

Kit restarts supplied enough headroom to complete the bounded captures. A permanent GPU memory fix was not established, and controller/ocean animation phases restarted. The last retained observation was 546 MiB free at 9 October 2026, 19:25:31 UTC, against the unchanged 768 MiB pre-render guard. That dated observation does not describe current GPU headroom.

Engineering sprint acceptance was complete. Biological approval, approval for a limited research study, and approval for larger biological expansion remained false. The [current reproduction guidance](/home/madil/kit-app-template/experiments/gama_marlin_v1/SPRINT_CLOSEOUT_REPRODUCTION.md) describes verification of the completed evidence and preserves the limits on future work.
