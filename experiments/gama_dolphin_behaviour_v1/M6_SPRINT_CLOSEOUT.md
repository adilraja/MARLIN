# M6 — Bottlenose sprint closeout candidate

Sprint: **MARLIN — GAMA–Omniverse Bottlenose Dolphin Behaviour and Animation**.
Prepared 5 November 2026. Evidence version: **bottlenose_engineering_demo_v1**.
**Engineering checks passed. Gate D visual acceptance remains pending; M6 and the sprint are not yet closed.**

## Declared result and evidence map

The sprint produced a bounded, reproducible engineering demonstration of one
existing Model 61A dolphin. Actual recorded GAMA progression controlled world
movement; an opt-in MARLIN instance evaluated the preserved local body cycle
from simulation time. Original asset/material/calibration and accepted water
work were retained. No biological or research-capture validation was inferred.

| Milestone | Current evidence and acceptance |
| --- | --- |
| M1 audit/baseline | [Audit](M1_ASSET_AND_CONTROLLER_AUDIT.md), `baseline_manifest.json`; MAR accepted Gate A. |
| M2 ownership/time | [Contract](M2_STATE_OWNERSHIP_AND_TIME_CONTRACT.md), `m2_manifest.json`; committed `ac9022d`. |
| M3 GAMA movement | [Movement/provenance](M3_MOVEMENT_MODEL_AND_PARAMETER_REGISTER.md), eight actual runs/2,376 samples and `m3_manifest.json`; MAR accepted Gate B; committed `4af84ab`. |
| M4 body mapping | [Mapping](M4_STATE_TO_ANIMATION_MAP.md), `m4_manifest.json` and [Gate C acceptance](M4_GATE_C_ACCEPTANCE.md); committed `143d404`. |
| M5 full/reproducible sequence | [Demonstration](M5_INTEGRATED_DEMONSTRATION.md), `m5_manifest.json`; committed `3c6e263`. |
| M6 closeout | This report, `qa/m6/`, final manifest and [Gate D packet](reviews/GATE_D_REVIEW.md); technical work passed, new named review pending. |

Historical reports/README and gate packets retain their original dated status.
Separate acceptance records and the current Gate D state provide the later
decisions; old evidence was not rewritten to appear post-review.

## Regression, coexistence and rollback

The 26 relevant suites covered bridge/exchange/legacy actors, this sprint's
M2/M3/M4 tests, camera/projection/checkpoint math, movement/body motion, gallery,
ocean enclosure/material/cue and fixed HDR conversion. **188 effective tests
passed, zero unresolved skips and zero failed commands**. The first run passed
187 and skipped one authored-USD Sony check under system Python. The same
six-test module passed in Blender USD. Both attempts remain; raw execution
counts were 194 tests, 193 passing executions and one initial skip. Five repeated
Sony passes were not double-counted in effective coverage. No source or tolerance
was changed. See [regression summary](qa/m6/regression_summary.json).

The current native wave/controller regression passed five wave phases and two
20-step original-versus-engineering controller trajectories, including boundary
and dive/surface paths. Existing wave/sampler/controller code supplied these
checks, with zero sampler/controller discrepancy. This was geometry/controller
regression, not new underwater-camera optical qualification.

The public-API coexistence transaction passed **54 assertions**. A nonzero
private GAMA pose held exactly while the standard ocean phase, existing dolphin
position and chase camera actually advanced. An explicit next simulation query
then advanced only the private actor. Releasing it preserved the unrelated
running controllers. The shared private namespace still refused a competing
static owner. The transaction then stopped its temporary controllers and restored
the pre-work checkpoint. No Kit restart was needed.

Every original scene prim/property matched after rollback: **38 prims, zero
missing/extra prims and zero composed attribute/relationship differences**, with
no exceptions. Camera, resolution, renderer/display settings, original water,
existing endpoints and original stopped ocean/swimmer/gallery/chase states
matched. Final normal-GUI checkpoint: `checkpoint_9zoknw14`. No private
actor, temporary chase camera, active QA poller or shared-asset deletion remained.

## Full demonstration and numerical reproducibility

The [complete 74-second movie](../../artifacts/gama_dolphin_behaviour_v1/m5/primary02/full_sequence_74s.mp4)
contains 370 normal-speed frames at 5 fps and 512×384, without edited windows.
The [23-state sheet](qa/m5/figures/frozen_state_contact_sheet.png) covers the
principal states and manoeuvre boundaries. [Motion/phase plots](qa/m5/figures/motion_and_phase.png)
and the [frozen-state index](qa/m5/frozen_state_index.json) retain traceability.

M5 passed 381 matched cadence queries, 13 reordered seeks and six fresh-process
comparisons. Maximum measured root, joint, phase and repeated/reopened skin
errors were zero under the locked criteria. All 35 frozen files reproduced
21,504-vertex skin and their complete ocean/lighting state. Seeking used explicit
prefix replay and the retained two-state bracket, not hidden stateless history.
The native SDK audit verified four lighting fallbacks missing in generic USD.

## Separate assessments and next-use proposal

| Assessment | Status at this technical seal | Scope |
| --- | --- | --- |
| Engineering correctness | **Passed** | Declared bounded movement/ownership/body/reproducibility and preservation checks. |
| Visual plausibility | **Provisional; Gate D pending** | MAR previously accepted the limited M4 map. New named review of the complete sequence is required here. |
| Biological support | **Provisional; no expert biological acceptance** | All movement/timing values remain engineering assumptions. The asset and inherited cycle do not validate natural behaviour or anatomy. |
| Research-capture readiness | **Not approved by this sprint** | A later specified-use review must address biology, optics, visibility, labels and the target experiment. |

[Updated parameter/pose provenance](qa/m6/parameter_and_pose_provenance.json)
retains every M3 parameter's source/status plus the asset, engineering transform
and M4 visual-amplitude policy. No physiological speed, natural activity rate,
propulsion, breathing or specimen calibration was invented. No new empirical
biological sources were claimed. The prior provenance supports an engineering
test, not a biological study.

The proposed next use is the **exact bounded engineering/visual demonstration,
subject to Gate D acceptance**. No dataset generation, ML training, species/pod
expansion, or biological/survey study begins automatically after closeout.

## Explicit limitations and retained unsuccessful work

- Turns, descent and ascent continue the existing local cycle with trajectory
  root attitude. Bespoke banking, asymmetric steering, dive-body and breathing
  poses remain unsupported; MAR accepted this bounded map at Gate C.
- M5 used frozen ocean phase zero. M6 demonstrated independent live controller
  coexistence; it did not change the recorded movie into a dynamic-wave sequence.
- Review video is bounded to 5 fps/512×384. HDR/EXR and fixed derived displays
  remain the supported route. Native LDR, radiometric/sensor qualification and
  actual accumulated sample counts were not established.
- Equal state did not establish RGB identity; twelve M5 RGB comparisons retained
  observed differences without a fitted RGB pass threshold.
- M5's sampled free GPU minimum was 1,636 MiB above its 768 MiB guard. These were
  samples, not an exact memory peak or a survey-resolution qualification.
- Original failures, skips, metadata/camera comparison amendments, rounded-bake
  quaternion correction and generic-USD schema limitations remain preserved in
  the respective milestone packages. No locked tolerance was relaxed to pass.
- The separate ocean-material inside-camera attenuation issue remains open.
  This bottlenose closeout does not close that NVIDIA support case.

All earlier package/source/asset/water acceptance pins verified unchanged through
the M5 verifier and its historical checks. The final manifest binds M6 findings,
prior technical seals, source/model/configuration pins, licensed dependencies,
restorable checkpoints and permitted media references. Large raw captures, logs
and SDKs remain in their recorded local stores; hashes accompany retained files
and are not substitutes for retaining them.

See [reproduction and rollback](REPRODUCTION_AND_ROLLBACK.md). Technical work is
ready for [Gate D review](reviews/GATE_D_REVIEW.md). **No named Gate D acceptance
has been recorded, no M6 commit was made and the sprint remains open at this seal.**
