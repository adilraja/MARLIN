# Gate D — Final bottlenose engineering/visual review

Prepared 5 November 2026. Evidence: **bottlenose_engineering_demo_v1**.
Proposed reviewer: **MAR**. **Status: pending; no final acceptance recorded.**

## Decision requested

Accept the exact bounded engineering/visual demonstration and close this
bottlenose sprint, retaining provisional biological support and no research-
capture qualification; or identify a required refinement before closeout.

This is a new final review of the complete sequence. Gate C's accepted limited
animation map is retained. No new bank/steering/dive/breathing pose, biological
validation, survey readiness or inside-camera optical fix is being claimed.

## Material to review

1. [Full 74-second reference video](../../../artifacts/gama_dolphin_behaviour_v1/m5/primary02/full_sequence_74s.mp4):
   370 frames at 5 fps and 512×384, normal simulation speed, no time-window cuts.
2. [23-state contact sheet](../qa/m5/figures/frozen_state_contact_sheet.png),
   [motion/phase plots](../qa/m5/figures/motion_and_phase.png) and
   [traceable frozen-state index](../qa/m5/frozen_state_index.json).
3. [M4 dry diagnostic](../../../artifacts/gama_dolphin_behaviour_v1/m4/dry02/review_30s.mp4)
   for supplementary body inspection. This edited dry clip is not the full M5
   movie or evidence of underwater optics.
4. [Closeout](../M6_SPRINT_CLOSEOUT.md),
   [reproduction/rollback](../REPRODUCTION_AND_ROLLBACK.md),
   `qa/m6/regression_summary.json`, `qa/m6/assessments_at_gate_d.json` and
   `m6_manifest.json`.

Absolute full-video path:
`/home/madil/kit-app-template/artifacts/gama_dolphin_behaviour_v1/m5/primary02/full_sequence_74s.mp4`.

## Concrete review questions

- Does the full steady/turn/descent/submerged/ascent/steady sequence read as a
  coherent engineering demonstration with the documented existing-cycle limits?
- Does local trunk/tail/fluke motion remain coherent through the manoeuvres,
  without unexplained snapping, disconnected geometry or gross distortion?
- Are state joins at 10, 22, 38, 48 and 64 s and the initial/final holds acceptable
  at this bounded frame rate and fixed ocean phase?
- Do the traceable snapshots and repeated-state evidence support this exact
  demonstration, with RGB appearance assessed separately from state equality?
- May this version be used for bounded engineering/visual demonstrations while
  biological support remains provisional and research capture remains unapproved?

## Technical results and scope

188 effective regression tests passed. One initial system-Python skip was
resolved in the USD interpreter; both attempts were retained. The current native
regression passed five wave phases and two controller trajectories. All 54 live
coexistence/rollback assertions passed. The original 38-prim scene and settings
were restored exactly, with no Kit restart for M6.

M5 passed 381 cadence comparisons, 13 reordered seeks and six fresh-process
comparisons. All 35 full frozen files reproduced skin and native ocean/lighting
state; measured root/joint/phase/skin discrepancies were zero. The original
source asset, fixed calibration, water and historical acceptance pins remained
unchanged. Raw media and runtime dependencies remain explicitly recorded.

Biological parameter values, inherited poses and specimen calibration have not
received expert biological acceptance. Full-sequence dynamic-wave coupling,
native LDR/sensor calibration, label/survey validity and the separate
ocean-material underwater-camera issue remain outside this acceptance.

Engineering is **passed**; final visual acceptance is **pending**; biological
support is **provisional**; research-capture use is **not approved by this sprint**.
No dataset, ML or species expansion begins automatically after approval.

The pending technical seal and packet will remain preserved. A subsequent named
review record will bind the actual decision, date and comments to these exact
files. Codex has not supplied a human or biological approval.
