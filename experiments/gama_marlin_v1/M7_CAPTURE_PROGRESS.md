# Milestone 7 capture progress — incomplete

Sprint: **GAMA–MARLIN Behavioural Integration and Validation**.

Milestone: **Produce a small GAMA-driven capture and annotation test set**.

The implementation and partial engineering checks passed, but Milestone 7 is **not complete**. The declared set requires 150 images. Twelve snapshot groups produced 120 verified images; the three remaining test-split groups require 30 more images. Both original capture attempts retained their failed campaign status. No final dataset, complete split manifest or Milestone 7 acceptance seal has been issued.

## Captured and outstanding work

| Component | Required | Verified so far | Outstanding |
|---|---:|---:|---:|
| Actual GAMA trajectory sources represented by rendered images | 5 | 4 | 1 |
| Snapshot groups | 15 | 12 | 3 |
| Target-present images | 75 | 60 | 15 |
| Matched target-absent images | 75 | 60 | 15 |
| Total images | 150 | 120 | 30 |

The [immutable selection declaration](/home/madil/kit-app-template/experiments/gama_marlin_v1/m7_capture_declaration.json) was saved at `2026-10-09T11:56:19.444912+00:00`, before any M7 image inspection. Its SHA-256 is `4955284fe067ce9e69b5d47d8381e6a5f82f3e00e3453d2459858189e431e557`.

The declaration selects five already executed, independent fresh-process M5 GAMA runs, with seeds 1, 42, 184729, 20261008 and 2147483647. M7 reparsed and hashed their actual raw GAMA outputs; it did not manufacture trajectories or execute new GAMA simulations. Each run contributes steps 8, 16 and 32, at simulation times 4, 8 and 16 seconds. These states are shallow swimming at 0.5 m, descent at 1.9 m and ascent at 1.6 m. Initial angular phase supplies the seed variation; statistical or ecological independence is not claimed.

Every snapshot has five fixed GSD conditions: 0.5, 1, 2, 3 and 4 cm/px. The camera remains a 1024 × 768 ideal nadir perspective camera. Only camera height varies within a frozen snapshot. Seeds 1, 42 and 184729 belong to train, seed 20261008 to validation and seed 2147483647 to test. Related repeat-run identifiers are assigned to the same encounter family and partition. All snapshots, GSD versions and physical-removal counterparts in a family stay together.

The current 120-image evidence therefore contains 90 train and 30 validation images, with **no test images yet**. The [partial split manifest](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_partial_split_manifest.json) records the existing views and declared families with an explicit incomplete status. The missing groups are exactly `m5_positive_seed_2147483647_a` at steps 8, 16 and 32. No different seed, state, time or visually attractive frame was substituted.

## Implementation and verification

The existing NVIDIA Kit Services bridge now exposes `POST /integration/gama/v2/actor/dataset-capture`. The [protocol](/home/madil/kit-app-template/integrations/gama/DATASET_CAPTURE_V2.md) documents its fixed workload and source, camera, annotation and ownership checks. The existing paired-capture transaction is shared with the dataset endpoint; the original M6 paired interface remains covered by regression tests.

The transaction freezes a positive scene and creates its negative counterpart by removing only the owned `/MarlinGamaPorpoise` root from a private copy. Both retained USD scenes, their resolved identities, common background, source state, actual camera parameters, annotations, labels and image hashes remain available. Settling probes are retained. A negative is physically target-absent, rather than submerged or hidden. Existing demonstration animals remain unlabelled background.

The [second live attempt](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_live_02/results.json) contains the 12 valid groups and 120 source-traceable image records. Its groups passed 1,344 frozen-state checks and retained 360 settling probes. Twelve [independent retained-USD verification reports](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_scene_validation_02) reopened the actual positive and absent scenes, verified removal, background identities and actual GAMA poses, and rebuilt all 120 annotation/camera checks. Recomputed mesh annotations and YOLO text matched exactly; the maximum recorded camera projection-matrix error was zero.

The verifier retained one explicit dependency limitation: runtime `OmniSurface.mdl` metadata was recorded, but its bytes were not opened under the restriction on generated/cache directories. Local source assets and inspected dependencies were hashed. Matching frozen state is not a claim of bit-identical RGB output or complete verification of that unopened runtime dependency.

The [partial visual review](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_partial_review/index.md) links all 12 contact sheets and retains [120 per-view observations](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_partial_review/visual_inspection.json) bound to original image, annotation, label and sheet hashes. These are Codex engineering presentation observations; no human M7 acceptance or biological approval is recorded.

Latest relevant offline tests passed **121 cases**:

| Check | Cases | Retained execution evidence |
|---|---:|---|
| Actual USD state/removal/annotation helpers | 18 | [state result](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_01_dataset_state_execution.json) |
| Dataset transaction and existing paired transaction | 11 + 13 | [transaction results](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_01_transaction_results.json) |
| Fixed dataset route | 4 | [route result](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_01_dataset_routes_execution.json) |
| Capture client and bounded headroom retries | 42 | [client result](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_03_dataset_client_results.json) |
| Collection before the unchanged GPU guard | 2 | [preflight boundary result](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_02_capture_preflight_execution.json) |
| Pending-only selection, provenance and immutable copy validation | 31 | [pending result](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_05_dataset_pending_results.json) |

These tests combine actual USD/actor checks with fake Kit or injected client boundaries where stated in their execution records. They do not substitute for the missing live captures. The earlier pending-helper test run retained one duplicate-selection failure; after the helper fix, the fresh 31-case run passed. Frozen live02 capture/runtime sources remained unchanged.

The [partial preservation check](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_partial_preservation.json) passed protected inventories for Pilot v1 (914 entries), its archive (1), original and backup checkpoints (2), M2 (17), M3 (27), M4 (55), M5 (175) and M6 (98). These inventories can overlap. Seven historical manifest anchors and both archived historical M6 source files matched. The two deliberate M7 changes to previously sealed M6 source are recorded separately; historical source bytes were recovered from Git and matched to the M6 seal. Earlier manifests were not rewritten.

## Capture failure and GPU blocker

The [first attempt](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_live_01/results.json) produced two seed-1 groups (20 images) before a no-render headroom refusal. Its outputs remain retained as attempt evidence and are excluded from the current 120-image candidate set. The second attempt repeated the declared selection with the frozen, tested protocol and completed all three snapshots for each of the first four seeds.

The second attempt retained 15 exact no-render GPU-headroom refusals across its bounded retries. The first test-seed snapshot exhausted four requests at **503, 687, 687 and 687 MiB free**, below the unchanged **768 MiB** minimum. The response explicitly stated that no render was attempted. Retries used the same owned actor, source run and step, and checked held state and code pins; the policy allowed at most four requests with three 20-second waits. Steps 16 and 32 for that seed were consequently not attempted.

All five second-attempt run cleanup records passed their 12 checks, including the failed test-seed acquisition. The actor was released, its owned root removed, and the original stage, camera, render settings and animation gates restored. The original 11 demonstration animals and ocean remained available. Kit was not restarted. The campaign itself remains `passed: false`.

A subsequent GPU query observed **523 MiB free** alongside UTC `2026-10-09 16:08:45`; another observed **374 MiB free** alongside UTC `2026-10-09 16:54:05`, still below the guard. These are resource observations, not evidence of a memory leak or permission to stop unrelated applications. No threshold reduction or automatic application shutdown was used.

## Remaining execution path

The [pending-only preflight](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_pending_preflight_01/results.json) passed without actor acquisition or rendering. Its [saved plan](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_pending_preflight_01/pending_plan.json) pins the entire original second-attempt tree, accepted groups, immutable declaration and capture protocol, and identifies only the three missing groups. It proves protocol/source/live prerequisites; it does not establish sufficient GPU memory for rendering.

Once enough memory is available while Kit stays running, the prepared continuation is:

```bash
/usr/bin/python3 -B tools/capture_gama_dataset_pending_v2.py \
  --output experiments/gama_marlin_v1/qa/m7_supplement_01
```

It replays the original test trajectory through the three declared snapshots, captures only the missing 30 views with the unchanged guard, and releases the actor in cleanup. The original 120 images are not recaptured. Its output directory is exclusive, and source/capture-code changes cause validation to refuse reuse.

After that supplement passes, the prepared offline aggregation tool can copy the 12 original valid groups and three supplement groups into `qa/m7_capture_set`, recording every source and destination hash and preserving the original failed attempt status. All 15 copied groups must then receive fresh independent retained-USD verification, the three new contact sheets must be inspected, and the final 150-view review must be bound explicitly through byte-identical copy provenance. The exporter refuses a partial or failed set and requires complete scene and review evidence before creating the final dataset and trajectory split manifest.

Aggregation, complete-set verification, final review, dataset export and final M7 acceptance remain outstanding. The [progress manifest](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_progress_manifest.json) records this partial state with `passed: false`; it is not the Milestone 7 completion seal.

## Engineering limitations retained

- Labels are direct amodal boxes from evaluated mesh vertices, including clipped YOLO rectangles. They are not exact visible or refracted underwater outlines; rendered visibility remains `unknown`.
- Seed 42 at step 16 overlaps a large pale background animal in the contact sheets. The owned positive target cannot be separately distinguished at that review scale. It remains physically present in metadata and was retained.
- Some positive/absent rows show differences in background animal brightness or texture, particularly seed 1 at steps 16/32 and seed 42 at step 8. Their cause is unestablished. Frozen background identity does not prove photometric equivalence.
- At coarse GSD, some positive silhouettes are very thin and the drawn box border can dominate the contact-sheet presentation. Some absent frames look uniform blue at contact-sheet scale, although their source RGBs are spatially nonconstant. Neither appearance was used to select replacements or turn physical positives into negatives.
- The live presentation environment is frozen per snapshot. It does not reproduce Pilot v1's flat-water/diffuse-lighting assumptions, and underwater refraction is uncalibrated.
- The animal uses the existing static upright pose proxy. Dive pitch, rig animation, breathing pose and biological suitability remain unverified. MAR's earlier provisional M5 review is not extended into M7 biological approval.
- The set is an engineering demonstration with unlabelled background wildlife. It is not a statistically powered wildlife dataset or a claim that absent-target images contain no animals.

Milestone 8, detector retraining, biological expansion and the final expansion recommendation have not started.
