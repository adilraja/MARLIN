# M5 — Integrated demonstration and reproducible frozen snapshots

Sprint: **MARLIN — GAMA–Omniverse Bottlenose Dolphin Behaviour and Animation**.
Milestone: **Demonstrate the full sequence and reproducible frozen snapshots**.
Prepared 5 November 2026. **M5 technical acceptance passed. M6 and Gate D have not started.**

## Outcome and review material

The complete 74-second accepted reference sequence was replayed from actual M3
GAMA output through the unchanged, MAR-accepted M4 animation map:
steady swim → gradual turn → descent → submerged swim → ascent → steady swim.
One private experimental dolphin used the preserved Model 61A asset, rig, bake,
material and fixed calibration, with the unchanged `engineering_v1` water preset.
No production source, behaviour model, asset, accepted preset or historical seal
was changed. This was a new bounded verification campaign, not a new dataset.

- [Full 74-second video](../../artifacts/gama_dolphin_behaviour_v1/m5/primary02/full_sequence_74s.mp4): 370 frames at 5 fps, normal simulation speed, no edited time windows.
- [23-state contact sheet](qa/m5/figures/frozen_state_contact_sheet.png).
- [Motion and phase plots](qa/m5/figures/motion_and_phase.png).
- [Traceable frozen-state index](qa/m5/frozen_state_index.json).
- [Numerical comparison](qa/m5/state_comparison_final.json), [native frozen-scene audit](qa/m5/native_frozen_audit.json) and [resource summary](qa/m5/resource_summary.json).

The original 297 GAMA states were retained, including seed/run/step provenance;
5 fps presentation did not create independent behavioural samples. The 23 snapshot
times were declared before acceptance capture, including states on both sides of
the 10, 22, 38, 48 and 64 second boundaries. The terminal 74-second stopped state
was separately preserved. Exact times are in `qa/m5/locked_plan.json` and its
retained, justified protocol amendments.

## Timing, seeking and frozen state

Schedule A captured the monotonic union of video and snapshot times. Schedule B
queried the same **381 timestamps** with extra 0/1/5 Kit update waits. Thirteen
additional reordered seeks passed. Seeking explicitly reset and replayed the
actual contiguous GAMA prefix through ceil(t/0.25), then evaluated within the
retained two-step bracket. This is deterministic reconstruction, not stateless
random access or resumed hidden controller history.

The primary process PID was 1592768; a fresh Kit process, PID
1624932, recreated six representative states in reverse order. All six
fresh-process comparisons passed. Their times were 6, 16, 30, 42, 56 and 70 s.

Every capture held resolved root, all 20 composed joint poses, phase, weight,
two-state buffer, accepted-prefix index, authored capture-camera/frustum, ocean
geometry and lighting while the renderer settled and copied HDR. Full snapshot
USD, native HDR/EXR, evaluated 21,504-vertex skin arrays and complete JSON state
were retained at the declared times. The source trajectory and prefix rule
provide the controller reconstruction path; a frozen USD is not a serialized
Python subscription or transport token.

Across the independent replay, schedule and frozen-scene checks, maximum measured
root-matrix, root-position, joint-matrix, phase and repeated/reopened skin errors
were **zero**. Criteria remained the original M4 values: root matrix 1e-8,
root position 1e-5 m, joint matrix 2e-6, phase 1e-9 cycles and skin 2e-6 m.
All **35** full frozen files (23 primary, six reordered and six fresh) reopened
and matched evaluated skin. They also matched complete ocean/lighting state in
the native Kit runtime. Pause, resume without a jump, missing-update freeze,
rejected missing-step delivery, reset hold and owned-actor removal passed in
both the primary and fresh processes.

## Capture domain and limitations

All 393 primary/reordered/fresh captures used the existing native `HdrColor`
float-buffer and EXR path. The original fixed scale-12000 gamma display and fixed
log1p display were retained. Ordinary marine HDR was much lower than the bright
emitter fixture's scale, so a separately declared, fixed Reinhard review display
was added before the successful full run:
`round(255 * (max(rgb,0)/(1+max(rgb,0)))**(1/2.2))`.
It was identical for every frame; there was no per-image normalization, light,
material or camera-exposure fitting. The video/contact sheet are derived HDR
displays, not newly qualified native LDR or radiometrically calibrated imagery.

The ocean used deterministic frozen phase zero for this campaign, matching the
accepted M4 diagnostic policy. Dynamic wave/animal coupling during full-sequence
playback was not demonstrated. Cameras remained above the wave-height bounds.
The accepted turn/descent/ascent limits remained: the existing local cycle ran
with trajectory root attitude, without bespoke bank, steering, dive-body or
breathing poses. Biological/optical/survey approval was not granted; the separate
ocean-material inside-camera attenuation case remained open.

Twelve matched HDR comparisons retained actual RGB differences separately;
state equality did not establish pixel identity. Configured 512 spp and frame
settling did not establish actual accumulated sample count. Final named visual
and biological assessments remain for M6/Gate D.

## Retained failures and audit amendments

`smoke01`, `smoke02` and partial `primary01` were preserved. Their overly broad
freeze assertions included the asynchronously updated UI viewport view matrix.
Retained operand comparisons isolated the change to that UI cache; commanded
root/joints/phase and authored capture-camera/frustum remained exact. Protocol v3
consistently distinguished these presentation fields and retained both raw UI
metadata and comparison results. No numeric tolerance or original scene data
was changed. The successful campaign used new output `primary02`.

An external generic-USD audit could not resolve four unauthored NVIDIA dome-light
schema fallbacks. Its source and diagnosis were retained. All 35 frozen files
were then reopened inside native Kit and matched the complete recorded lighting
state exactly, including those defaults. The external skin audit accepted those
specific missing schema values only with the corresponding successful native
file-hash-bound proof. This remains an explicit SDK dependency, not a claim of
identical lighting under a generic USD installation.

## Resources, restoration and next boundary

Primary wall time was 381.05 s; fresh-process capture/check time
was 40.30 s, excluding launches and later offline packaging.
Minimum sampled free GPU memory was **1636 MiB**, above the unchanged 768 MiB
guard. The bounded image workload was 512×384 with 5 fps video. Six checkpointed
Kit launches covered retained smoke/capture fixes, fresh replay and the native
schema audit. No system reboot or driver/SDK installation change occurred.

The original live scene was restored exactly: **38 prims, zero missing/extra prims
and zero composed attribute/relationship differences**, without exceptions.
Camera, resolution, renderer/display settings, original water and controller
states matched pre-work. Ocean/chase/swimmer/gallery had already been stopped
and were restored stopped. The final normal-window checkpoint was
`checkpoint_9h35bd4l`. No experimental actor or QA poller remained.

The M4 technical seal, MAR's Gate C decision and historical M1–M3/water M5–M6
evidence verified unchanged. Their dated pre-M5 statuses were not rewritten.
See [reproduction and rollback](M5_REPRODUCTION_AND_ROLLBACK.md) and
`m5_manifest.json`. M5 is complete for this engineering scope. The next milestone
is M6 closeout/regressions and named Gate D review; no Gate D acceptance, Git
commit, dataset generation or additional species work was performed here.
