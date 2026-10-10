# Post-M8 M7 engineering completion recipe

This is a prospective procedure, not an acceptance result. The new capture
attempts, actual inspection and final checks must finish before any completion
claim. All commands below operate on retained evidence except the separately
authorized single-state capture client; that live work is outside this recipe.

## Exact accepted origins

The declared workload remains five original actual GAMA runs, steps 8/16/32,
five GSDs, and present/physically removed counterparts. Its original declaration
SHA256 remains `4955284fe067ce9e69b5d47d8381e6a5f82f3e00e3453d2459858189e431e557`.

| Original attempt | Original overall status | Groups selected for the accepted set |
| --- | --- | --- |
| `qa/m7_live_02` | failed | 12 accepted groups, seeds 1/42/184729/20261008 |
| `qa/m7_supplement_01` | failed | max-seed step 8 only |
| `qa/m7_supplement_step_016` | must pass | max-seed step 16 only |
| `qa/m7_supplement_step_032` | must pass | max-seed step 32 only |

The first supplement's exhausted no-render step-16 refusals stay retained.
Original step-8 images are never recaptured or replaced. The four attempt
statuses remain `[false, false, true, true]`; the accepted aggregate is explicitly
an offline copy of selected passed groups, not an uninterrupted successful live
campaign. Per-source run statuses and cleanup checks remain visible, including
the failed max-seed run in the first supplement.

## Required sequence

1. Require final accepted group manifests **and** client group/run/results
   records for the two isolated continuations, with every restoration,
   coexistence, release and resumed-demo/ocean check passed. Revalidate their
   saved plans, exact prior-attempt source trees, source-state and frozen source
   pins through the unchanged `capture_one_pending_snapshot.py` helpers.
   Counts of probes and state checks must be read from actual records.

2. Run the new transparent copy aggregator, retaining its exact command,
   return code, real combined stdout/stderr log and source/result hashes:

   ```bash
   /usr/bin/python3 -B experiments/gama_marlin_v1/qa/m7_completion_01/aggregate_capture_set.py \
     --output experiments/gama_marlin_v1/qa/m7_capture_set
   ```

   Require all 15 distinct declared keys and 150 images, 75 physically present
   and 75 removed, with exact per-file original/copy hashes and explicit four
   source-attempt provenance. Every source attempt tree remains unchanged.

3. Genuinely rerun the unchanged retained-USD verifier on **all 15 copied
   groups**, retaining each new result/log/execution in
   `qa/m7_scene_validation_set`. Do not relabel the old 12 source proofs:

   ```bash
   /usr/bin/python3 -B experiments/gama_marlin_v1/qa/m7_completion_01/verify_aggregate_groups.py \
     --aggregate experiments/gama_marlin_v1/qa/m7_capture_set
   ```

   Require all 150 camera/projection/annotation checks, actual positive and
   negative USD identities, zero time samples, exact owned-root removal,
   unchanged common background identities, correct GAMA pose/depth and current
   local dependency hashes. Runtime/unresolved shader paths remain explicit
   and must not be opened.

4. Generate a separate source preview for each new original max-seed group
   using `qa/build_m7_review.py --group <actual original group> --output <new
   preview directory>`. All three preview directories use stems under
   `qa/m7_supplement_01_visual_preview`; their source paths must identify their
   **actual** originating attempt from the table above. Preserve generator
   commands/logs/hashes. Generating a sheet does not inspect it.

   Inspect all ten full-frame views on each of these three sheets after they
   exist. Retain actual observations in each preview directory's
   `visual_inspection.json` and `per_view_visibility_observations.json`. Bind
   the exact ordered ten image IDs, run/seed/step, physical presence, GSD,
   RGB/annotation/YOLO paths and hashes, visual-index SHA and reviewed-sheet SHA.
   Record meaningful per-view observations, including ambiguous or obscured
   positives. Keep machine `rendered_visibility: unknown`, biological approval
   false and observations explicitly separate from machine visibility labels.
   Do not drop, replace or threshold-select images by visibility. The old 120
   source-bound observations in `qa/m7_live_02_visual_preview` stay unchanged.

5. After the 15 fresh proofs and all 150 original observations exist, create
   the final review exclusively through the new four-origin finalizer:

   ```bash
   /usr/bin/python3 -B experiments/gama_marlin_v1/qa/m7_completion_01/finalize_review.py
   ```

   It verifies original-to-copy provenance, generates 15 final sheets in new
   `qa/m7_review`, and requires their PNG bytes to equal the actual inspected
   previews. It transfers observations through explicit byte-copy provenance.
   Require `review_complete_artifacts.json`, `generation_execution.json` and
   all 150 final observations. The generator's initial
   `visual_inspection_completed:false` flag is preserved; the separate actual
   manual-review record documents completed inspection and its scope.

6. Export the verified artifacts into an exclusive new dataset directory:

   ```bash
   /usr/bin/python3 -B tools/export_gama_dataset_v2.py \
     --campaign experiments/gama_marlin_v1/qa/m7_capture_set \
     --scene-verifications experiments/gama_marlin_v1/qa/m7_scene_validation_set \
     --visual-review experiments/gama_marlin_v1/qa/m7_review/visual_inspection.json \
     --output experiments/gama_marlin_v1/datasets/m7_engineering_v1
   ```

   Retain command/log/execution and require 450 byte-identical PNG/YOLO/JSON
   copies. The split is 90 train, 30 validation, 30 test images; whole source
   trajectories, all snapshots/GSD/presence views and related repeats stay in
   their declared partition. There are 75 camera-condition pairs. Class 0
   labels only the owned harbour porpoise; negatives have no owned-target box
   and empty target labels. Other demo animals remain unlabelled background.
   The descriptor is not a training command.

7. Run new exclusive preservation proofs, then the new completion validator.
   `check_m7_preservation.py` must reproduce protected counts Pilot914,
   archive1, checkpoints2, M2 17, M3 27, M4 55, M5 175 and M6 98 (count-sum1289),
   plus the exact two historical M6 source copies. The unchanged
   `check_m8_m7_progress_preservation.py` must still verify all 1355 historical
   incomplete-M7 outputs; its historical M8-kind label is not relabelled.

   ```bash
   /usr/bin/python3 -B experiments/gama_marlin_v1/qa/m7_completion_01/validate_completion.py \
     --campaign experiments/gama_marlin_v1/qa/m7_capture_set \
     --scene-verifications experiments/gama_marlin_v1/qa/m7_scene_validation_set \
     --review experiments/gama_marlin_v1/qa/m7_review \
     --dataset experiments/gama_marlin_v1/datasets/m7_engineering_v1 \
     --execution-record <actual aggregate execution JSON> \
     --execution-record <actual export execution JSON> \
     --preservation <new original protected-output preservation JSON> \
     --history-preservation <new partial-history preservation JSON> \
     --output experiments/gama_marlin_v1/qa/m7_completion_01/acceptance.json
   ```

   Each supplied command record must retain a command list, return_code0 and
   actual log path plus log_sha256; nested `execution`/`executions` records are
   accepted. The checker also requires all 15 exact Blender Python `-B`
   invocations/log/result/source pins, strict scene proof checks, review binding
   and new dataset inventory. It rechecks the original protected inventories,
   historical1355 outputs and sealed M8's119 outputs with before/after input
   pins. It must not run before final readiness; a failure stays retained and
   any corrected later run uses a fresh output name.

## New completion report and seal

Only after actual engineering acceptance passed, write a new dated M7
completion report and an exclusive new completion seal. Include the successful
new acceptance result and its command/log/execution, new helpers and review
tests, all four original attempt results and complete source inventories,
aggregate/copy provenance, all 15 fresh scene proof triplets and batch records,
original manual notes/previews, final review artifact inventory, dataset
manifest/453 outputs, new preservation proofs/executions and new report. Pin
the dataset manifest itself as well as its listed outputs. The seal must bind
all output sizes and SHA256s, reject duplicate/escaped/generated paths, and be
checked after writing. Avoid self-hash cycles: the seal inventories artifacts,
and a separate later seal-check record pins the seal's own bytes.

Do not alter `M7_CAPTURE_PROGRESS.md`, `qa/m7_progress_manifest.json`, sealed
M8 outputs, `M8_REPRODUCTION.md`, `GAMA_MARLIN_SPRINT_REPORT.md` or
`qa/milestone_8_manifest.json`. The historical M8 status
`complete_review_with_blocked_milestone_7` remains correct for its recorded
time. Its own SHA remains
`16a51dbd84bbe4ca31f0ad26dcbce318722072dd0cb12f6adc2fc872d244adfa`.
The historical incomplete-M7 seal SHA remains
`a480bd2ac0624ab6cc8ff2d6873bb68c355f6a73f9adcb3ad66ec53e242635d9`.
The new report explains the later completion, two failed capture attempts,
isolated continuation/restart provenance and the absence of any image
substitution. It must not rewrite historical GPU failures into successes.

Completion applies to the bounded engineering capture/export milestone.
Static upright proxies, provisional behavioral assumptions, unvalidated body
animation/breathing/anatomical water clearance/refraction, direct amodal boxes,
unknown machine visibility, unlabelled background wildlife and observed paired
RGB shading/detail differences of unestablished cause remain explicit. Pair
physical identities do not establish photometric or pixel equivalence. No new
training, detector performance, scientific generalization, biological approval,
human approval or automatic expansion approval follows from image counts.
