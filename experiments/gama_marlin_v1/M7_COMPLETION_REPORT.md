# Milestone 7 engineering completion

Sprint: **GAMA–MARLIN Behavioural Integration and Validation**.

Milestone: **Produce a small GAMA-driven capture and annotation test set**.

Recorded at UTC `2026-10-09T19:44:48.672961+00:00`. The declared bounded engineering test set was
completed, independently verified, reviewed and exported. All 150 declared
images were retained: 75 physically target-present and 75 explicit
target-removed images in 15 snapshot groups and 75 camera-condition pairs.
This report recorded the later M7 completion; it did not alter the earlier
incomplete-M7 progress record or the sealed M8 review.

## Actual sources and split

The set used five already executed fresh-process M5 GAMA trajectories, with
seeds **1, 42, 184729, 20261008 and 2147483647**. M7 reused and reparsed their
retained actual GAMA outputs; no new GAMA simulation or synthetic replacement
trajectory was created. Steps 8, 16 and 32 supplied simulation times 4, 8 and
16 seconds: shallow swimming at 0.5 m, descent at 1.9 m and ascent at 1.6 m.
The pre-inspection declaration remained SHA256
`4955284fe067ce9e69b5d47d8381e6a5f82f3e00e3453d2459858189e431e557`.

Every snapshot used the same five nominal GSD conditions, **0.5, 1, 2, 3 and
4 cm/px**, and a 1024 × 768 ideal nadir perspective camera. Only camera height
varied within each frozen snapshot/pair; actual matrices, optics, exposure and
projection checks were retained. Physical target absence was produced by
removing only `/MarlinGamaPorpoise` from a private frozen counterpart. The
positive and absent scenes retained their common background identities and
source context; an absent target was neither hidden nor merely submerged.

The exported split contained **90 train, 30 validation and 30 test images**.
Seeds 1/42/184729 stayed in train, 20261008 in validation and 2147483647 in test.
Whole trajectories/encounter families, selected snapshots, all GSDs,
present/removed counterparts and related repeat identifiers remained in one
partition. This grouping did not establish ecological independence or
statistical generalization.

## Transparent capture history

| Attempt | Original overall status retained | Accepted contribution |
| --- | --- | --- |
| `qa/m7_live_02` | failed | 12 groups / 120 images |
| `qa/m7_supplement_01` | failed | max-seed step 8 / 10 images |
| `qa/m7_supplement_step_016` | passed | max-seed step 16 / 10 images |
| `qa/m7_supplement_step_032` | passed | max-seed step 32 / 10 images |

The earlier `qa/m7_live_01` attempt also remained failed. It retained
20 images in 2 passed groups, and
those images were **excluded** from the accepted set. Thus the selected four
origins preserved statuses `[false, false, true, true]`; the wider history also
included that earlier failed attempt. No failed campaign or failed source run
was relabelled as successful. The accepted set was an explicit byte-identical
offline aggregation, not one uninterrupted successful capture campaign.

The original 120 images and the first supplement's accepted step-8 images were
not recaptured. After another exhausted pre-render GPU refusal, authorized
Kit-only restarts enabled the two remaining snapshots to run as separate
single-state attempts. The unchanged guard required 768 MiB free before
rendering. A restart provided memory for bounded capture work; **a permanent
GPU memory fix was not established**. The controller/ocean phases restarted,
and an uninterrupted animation phase was not preserved. Each later snapshot
was independently frozen and verified; cross-snapshot background animation
continuity was not claimed. Desktop applications were not restarted by these
Kit-only procedures. Final read-only demo evidence observed `546` MiB free;
that observation did not authorize further rendering or prove sufficient
headroom for another capture.

## Verification, actual inspection and export

All 15 copied groups received fresh executions of the unchanged retained-USD
verifier, rather than relabelled old source proofs. Actual saved positive and
negative scenes, exact owned-root removal, zero time samples, background and
state identities, GAMA pose/depth, camera conditions and direct mesh
annotations were checked. All **150** projections passed;
the maximum retained projection-matrix error was
`0.0`. Actual records contained
**1680 frozen-state checks**, **450
settling probes**, **180 restoration checks** and
**135 coexistence checks**. Local dependency hashes
were rechecked; unresolved runtime shader dependencies remained explicit and
their generated/cache bytes were not opened.

All 150 contact-sheet views received source-bound Codex engineering
presentation observations: the original 120 notes remained unchanged, and the
new 30 were inspected after capture. Final sheets had exactly the same PNG
bytes as the inspected source previews; observations were transferred through
explicit original/copy hashes. Generating sheets alone was not treated as
inspection, and no visibility threshold was used to select, discard or
replace frames. Ambiguous physically present positives remained present and
labelled by their direct amodal geometry.

The export copied 150 PNGs, 150 YOLO labels and 150 annotation JSONs unchanged
and retained 453 dataset artifacts plus its separately pinned manifest.
Class **0, harbour_porpoise**, labelled only the bridge-owned target. Removed
counterparts had no target box and empty target labels; other demonstration
wildlife remained unlabelled background. The dataset descriptor recorded the
declared partitions and was not a training command. No detector training,
inference, replacement performance result or generalization study was run.

Retained review/export/acceptance evidence:

- [Accepted aggregate results](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_capture_set/results.json)
- [Fresh fifteen-group retained-scene proofs](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_scene_validation_set/results.json)
- [All fifteen final contact sheets](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_review/index.md)
- [All 150 source-bound observations](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_review/visual_inspection.json)
- [Dataset export manifest](/home/madil/kit-app-template/experiments/gama_marlin_v1/datasets/m7_engineering_v1/manifest.json)
- [New acceptance result](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_completion_01/acceptance_retry_02.json)
- [Final read-only marine check](/home/madil/kit-app-template/experiments/gama_marlin_v1/qa/m7_completion_01/final_live_demo/results.json)

## Preservation and retained limits

Current preservation passed Pilot914, archive1, checkpoints2, M2 17, M3 27,
M4 55, M5 175 and M6 98 protected inventory entries, plus the two exact archived
M6 source copies. The inventory count-sum was 1289; these inventories can
overlap. All 1355 historically sealed incomplete-M7 output entries and all
119 sealed M8 output entries remained unchanged, including the historical
manifest bytes and disposition. The new completion seal inventoried
4827 unique current artifact paths. Original Kit logs could
continue appending; only verified fixed initial-prefix snapshots were sealed,
with subsequent appended bytes explicitly outside those snapshots.

The earlier M8 status `complete_review_with_blocked_milestone_7` remained the
historical disposition at its recorded time. Its reports and expansion
decision were not rewritten or silently promoted by this later M7 completion.

The animal still used a static upright mesh proxy and provisional engineering
behavior assumptions. Biological pose, dive pitch, body/rig animation,
breathing, anatomical water clearance and biological suitability were not
approved. Boxes remained direct **amodal evaluated-mesh projections**, not
exact visible or refracted outlines; machine rendered visibility remained
**unknown**. Underwater refraction and water optics remained uncalibrated.
Some paired background animals differed in RGB shading/detail; their cause
was unestablished. Matching physical identities did not certify pixel-identical
or photometrically equivalent backgrounds. Coarse GSD and overlay borders
limited anatomical inspection, and unlabelled background wildlife remained
outside the owned-target class scope.

Completion applied to this bounded engineering capture/review/export
milestone. Biological approval and inferred human M7 acceptance remained
false; no automatic approval for broader biological expansion or a scientific
behavior-conditioned study was created.
