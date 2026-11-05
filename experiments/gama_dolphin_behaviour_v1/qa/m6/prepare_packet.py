"""Prepare M6 findings and the pending named Gate D packet from actual evidence."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parents[1]
REPO=ROOT.parents[3]


def load(path):return json.loads(path.read_text())


def write(path,value):
    with path.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')


def text(path,value):
    with path.open('x') as stream:stream.write(value)


def pin(path):
    data=path.read_bytes()
    return dict(path=str(path.relative_to(REPO)),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def main():
    first=load(ROOT/'regression_summary_attempt01.json')
    retry=load(ROOT/'regressions_retry01/sony_camera.json')
    assert first['passed'] and first['discovered_tests']==188 and first['skipped_tests']==1
    assert retry['returncode']==0 and 'Ran 6 tests' in retry['stderr'] and 'skipped' not in retry['stderr']
    summary=dict(passed=True,effective_suites=26,effective_tests_passed=188,unresolved_skips=0,
        failed_commands=[],raw_command_runs=27,raw_test_executions=194,raw_passed_executions=193,raw_skipped_executions=1,
        initial=pin(ROOT/'regression_summary_attempt01.json'),retry=pin(ROOT/'regressions_retry01/sony_camera.json'),
        resolution='The unchanged six-test Sony suite was rerun in Blender USD; its previously skipped authored-USD case passed. Five repeated passing cases were not counted twice in effective coverage.',
        source_or_tolerances_changed=False)
    write(ROOT/'regression_summary.json',summary)
    live=load(ROOT/'live_attempt01/results.json')
    baseline=load(ROOT/'baseline_scene_comparison.json')
    final=load(ROOT/'final_restoration.json')
    assert live['passed'] and len(live['checks'])==54 and baseline['passed'] and final['passed']
    previous=subprocess.run(['/usr/bin/python3','-B',str(BASE/'qa/m5/verify_package.py')],cwd=REPO,
        capture_output=True,text=True,check=True)
    preservation=json.loads(previous.stdout);assert preservation['passed']
    write(ROOT/'earlier_evidence_verification.json',preservation)
    params=load(BASE/'config/m3_parameters_v1.json')
    assert set(params['parameters'])==set(params['provenance'])
    assert all(v['status']=='engineering_test_assumption' for v in params['provenance'].values())
    profile=load(REPO/'source/extensions/cris.madil.gama_bridge/config/model61a_engineering_v1.json')
    animation=load(BASE/'animation/m4_controller_v1.json')
    source_files=[REPO/'integrations/gama/bottlenose_constrained_v1.gaml',REPO/'tools/gama_bottlenose.py',
        REPO/'tools/analyze_gama_bottlenose.py',BASE/'config/m3_parameters_v1.json',BASE/'animation/m4_controller_v1.json',
        REPO/'source/extensions/cris.madil.gama_bridge/config/model61a_engineering_v1.json',BASE/'qa/asset_provenance.json']
    provenance=dict(schema_version=1,reviewed_utc=datetime.now(timezone.utc).isoformat(),sources=[pin(p) for p in source_files],
        behaviour_parameters=params['parameters'],behaviour_parameter_evidence=params['provenance'],
        asset_profile=profile,animation_policy=animation,
        biology=dict(status='provisional',expert_biological_acceptance=False,
            behavioural_literature_values_claimed=False,anatomical_pose_validation_claimed=False,
            assessment='All behavioural values and timing were declared engineering assumptions. The inherited asset/cycle and engineering transform do not establish specimen dimensions, natural manoeuvres, propulsion, activity frequencies or survey validity.'),
        asset_provenance='Preserved DigitalLife3D Model 61A source/model/texture/licence and original compatible bake; M1 source-equivalence/rig inspection and subsequent byte pins retained.',
        calibration='Fixed orientation and engineering scale were preserved; no biological or specimen calibration was inferred.',
        manoeuvre_limits='The same local cycle continues through turns, descent and ascent; no bespoke bank, asymmetric stroke, dive-body or breathing pose was added.',
        stochastic_provenance='Eight actual M3 runs and 2376 samples; retained reference/repeat and seeds 1,42,184729 with their realised choices. M6 replayed existing records and did not generate a new animal-behaviour dataset.')
    write(ROOT/'parameter_and_pose_provenance.json',provenance)
    assessments=dict(evidence_version='bottlenose_engineering_demo_v1',
        engineering=dict(status='passed',scope='Declared one-animal reference/seeded movement, ownership/time mapping, existing body cycle, M5 reproducibility and M6 regressions/coexistence/rollback',
            effective_regression_tests_passed=188,live_assertions_passed=54),
        visual=dict(status='provisional',review_status='pending_gate_d',proposed_reviewer='MAR',
            gate_c='MAR accepted the limited M4 map; full-sequence final acceptance is a new Gate D decision',accepted=False),
        biological=dict(status='provisional',expert_review_received=False,approved_for_biological_study=False,
            basis='Explicit engineering assumptions and preserved asset/cycle; no new biological support was inferred'),
        research_capture=dict(status='provisional',approved=False,
            basis='A later specified-use decision must address biology, optics, visibility and labels; no dataset/ML/species expansion starts automatically'),
        next_use=dict(status='planned',decision='pending_gate_d',
            proposed_use='Bounded engineering and visual demonstrations of the exact reviewed version only',
            automatically_authorized_new_work=[],sprint_closed=False))
    write(ROOT/'assessments_at_gate_d.json',assessments)
    scope=subprocess.check_output(['git','diff','--name-only','--','source','tools','integrations/gama'],cwd=REPO,text=True)
    assert not scope.strip()
    write(ROOT/'source_scope.json',dict(passed=True,base_commit='3c6e2630ea3cc091b2de9604c5a6c9972bc14232',
        production_source_changed=False,source_assets_changed=False,kit_restarts=0,system_reboots=0,
        historical_evidence_rewritten=False,git_commit_created=False))

    text(BASE/'M6_SPRINT_CLOSEOUT.md',f'''# M6 — Bottlenose sprint closeout candidate

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
matched. Final normal-GUI checkpoint: `{final['final_checkpoint']}`. No private
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
''')
    text(BASE/'REPRODUCTION_AND_ROLLBACK.md',f'''# Bottlenose sprint reproduction and rollback

## Verify the final technical candidate

From `/home/madil/kit-app-template`:

```bash
/usr/bin/python3 -B experiments/gama_dolphin_behaviour_v1/qa/m6/verify_package.py
```

This performs read-only manifest/preservation checks. It requires the retained
local artifact/checkpoint store, asset/licence files and historical Git source
versions. Kit/Blender/GAMA/vendor libraries are not bundled or asserted entirely
byte-pinned. The new M6 live test used the running Kit build and existing public
HTTP endpoints without a restart or installed dependency edits.

## Reproduce the same bounded demonstration

Use the actual retained M3 reference sequence and unchanged animated v3 owner.
GAMA owns root movement; local joint animation consumes simulation-time phase.
Deliver contiguous states, retain the two-state bracket, reset and replay the
prefix before an out-of-bracket seek. Do not reuse an old ownership token or
advance the shared timeline as an independent animal clock.

The [M5 reproduction guide](M5_REPRODUCTION_AND_ROLLBACK.md),
`qa/m5/frozen_state_index.json` and the full native HDR/EXR/scene/skin sidecars
specify camera, exposure, render settings, phase, weight, buffer, ocean geometry
and lighting. The 23 primary frozen states and 35 total reopened scenes were
tested. Four native lighting defaults require the recorded NVIDIA schema/runtime
and were checked by the native audit; generic USD alone cannot expand them.

Full movie:
`/home/madil/kit-app-template/artifacts/gama_dolphin_behaviour_v1/m5/primary02/full_sequence_74s.mp4`.
It is 74 seconds at 5 fps, with derived fixed HDR display. No native LDR or
biological/survey qualification follows. Ocean phase zero and existing-cycle
manoeuvre limits are part of the accepted technical protocol.

## Repeat tests without overwriting evidence

`qa/m6/locked_plan.json` records the 26 regression commands and module paths.
Use new result paths/attempt identities for any re-execution. The system Python
Sony skip was resolved by the unchanged six-test suite in Blender USD; retain
both the first attempt and retry. The current native wave regression and public
API coexistence transaction are in `qa/m6/live_attempt01`.

Completed scripts intentionally refuse to overwrite output identities. Before
another live transaction, checkpoint the current user scene, verify controller
and ownership state, version the output identities and keep the existing guards.
Do not run completed launch/capture jobs in place. Canonical source under
`source/` remains authoritative; generated builds/caches are not edit targets.

## Rollback already demonstrated

M6 preserved `{load(ROOT/'live_before/checkpoint.json')['checkpoint_id']}` before
testing and restored that exact frozen scene after stopping its temporary
controllers and releasing the private actor. Final checkpoint was
`{final['final_checkpoint']}`; copied USD/metadata and API states are in
`qa/m6/live_before` and `qa/m6/live_final`. All 38 composed prims/properties and
the original settings/controller states matched without exceptions.

The current original scene was already stationary: ocean, swimmer, gallery and
chase controllers were stopped, with original water selected. They were restored
stopped. No further rollback is required. For a later recovery, save any newer
work first, release the bridge-owned actor, stop the operation's temporary
controllers, and use `/debug/scene/checkpoint/<id>/restore` with the recorded ID.
Frozen checkpoints do not serialize arbitrary Python histories; reconstruct only
controllers documented as running in that operation's pre-work state.

Gate D remains a named human decision. This guide and the final technical seal
do not record visual/biological acceptance or authorize a new research use.
''')
    text(BASE/'reviews/GATE_D_REVIEW.md','''# Gate D — Final bottlenose engineering/visual review

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
''')
    print(json.dumps(dict(prepared=True,effective_tests=188,live_assertions=54,gate_d='pending')))


if __name__=='__main__':main()
