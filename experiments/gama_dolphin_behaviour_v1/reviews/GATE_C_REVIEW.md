# Gate C — Existing-cycle body-animation candidate

Prepared 5 November 2026. Proposed reviewer: **MAR**.
**Status: pending. No human acceptance has been recorded.**

## Decision requested

Accept the existing-cycle animation map, including its explicitly limited
turn/descent/ascent pose support, as the bounded engineering candidate for M5;
or request a specific local manoeuvre refinement before integration.

This decision does not approve biological realism, physically generated
propulsion, underwater optical qualification or survey/research capture readiness.
The separate ocean-material underwater-camera issue remains open; this is M4 of
the **bottlenose behaviour/animation sprint**.

## Review these files

1. **Dry body inspection:**
   `/home/madil/kit-app-template/artifacts/gama_dolphin_behaviour_v1/m4/dry02/review_30s.mp4`.
   This native textured clip hides the ocean in the disposable diagnostic copy so
   the trunk, tail, flukes, flippers and attachment regions remain visible.
2. **Marine context, above-water camera:**
   `/home/madil/kit-app-template/artifacts/gama_dolphin_behaviour_v1/m4/review01/review_30s.mp4`.
   Inspect surface interaction and submerged visibility with the unchanged
   engineering water material. Optical limitations still apply.
3. [Dry contact sheet](../qa/m4/figures/dry02_native_contact_sheet.png) and
   [marine contact sheet](../qa/m4/figures/review01_native_contact_sheet.png):
   top, oblique and close views of the same labelled states.
   [Native cycle excerpts](../qa/m4/figures/native_cycle_sequence.png) show the
   changing tail/fluke pose at successive recorded times.
4. [Mapping/capability matrix](../M4_STATE_TO_ANIMATION_MAP.md) and
   [reproduction/rollback](../M4_REPRODUCTION_AND_ROLLBACK.md).
5. `qa/m4/native_pose_comparison.json`, `native_media_analysis.json`,
   `restored_gui_stage_comparison.json`, `final_gui_checks.json`, final CPU/API
   checks and `m4_manifest.json`.

Each movie is 30 seconds at 10 fps, with labelled cuts and one-to-one simulation
time inside six selected windows. It is not the complete M5 demonstration.
Raw 512×384 PNGs, pose USD snapshots and root/joint/phase/camera sidecars remain
beside the movies. Bright exploratory and failed capture attempts were retained
and excluded from the final review candidates.

## Supported response and explicit limits

The candidate reuses the inspected 20-joint bake and produces actual cyclic
trunk/tail/fluke motion during all five state labels. Steady and submerged cycling,
startup/stop fading, loop continuity and the single-owner clock/lifecycle passed
technical checks. Source mesh, textures, rest skeleton, fixed scale and material
remained unchanged. No new asset or rig was generated.

**Turn, descent and ascent remain limited:** the existing local swim cycle
continues while M3 controls root heading/pitch/depth. There is no newly validated
asymmetric steering stroke, banking pose, specialised dive-body curve, breathing
or clearance model. Acceptance of these explicit limits is the bounded refinement
decision requested at this gate. A request for substantial rig/asset work would
need the separate scope decision retained by Gate A.

## Concrete visual questions

- Does the visible trunk/tail/fluke cycle read as coherent swimming for this
  engineering demonstration, including the manoeuvre segments?
- Do loop closure, speed fades, state joins and stationary holds avoid visible
  snapping or contradictory motion?
- Do the close views show unwanted stretching, disconnected parts, obvious
  self-intersection, inversion, scale changes or moving helper geometry?
- Are the root trajectory and surface interaction acceptable within the stated
  wave/contact and optical limits?
- Are the unsupported manoeuvre-specific capabilities clearly distinguished
  from the supported cycle, and may this exact candidate proceed to M5?

## Technical evidence and preservation

- Eight CPU composed-pose/skinning tests and 341 final live API checks passed.
- Sixty-one loop phases evaluated 21,504 vertices and 40,208 triangles without
  failure of the predeclared gross stretch/area/normal guards.
- All 681 candidate native frames matched final evaluated root, phase and weight
  exactly; maximum joint-matrix component error was 1.1921e-7 against 2e-6.
- Six reopened native pose snapshots matched every evaluated skin vertex exactly.
- Both review movies encoded 300 frames at 10 fps with a verified 30 s duration.
- The original 38-prim live scene was restored with zero composed attribute or
  relationship differences, and original stopped controllers/settings preserved.
- Display/exposure/writer issues and the quaternion-conversion failure were
  retained with their corrections. No pose tolerance was changed after failure.

The original bake contains slight local scale changes (including the head);
these existing tracks were retained, not presented as anatomical validation.
The geometric guards and visual review do not certify exhaustive absence of all
nonlocal mesh intersections. Biology and final research suitability remain
unresolved. The temporary zero-sized XWayland output recovered to 1366×768 on the
user's Ubuntu 26.04 Wayland desktop. The normal MARLIN window and exact original
scene/settings are now restored; no diagnostic actor/worker remains. No desktop,
driver or SDK change was performed.

Approval will be recorded separately against the exact technical manifest and
this packet. The dated pending review state and unsuccessful evidence will remain
preserved.
