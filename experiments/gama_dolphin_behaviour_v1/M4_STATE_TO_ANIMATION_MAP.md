# M4 — State and movement to visible body animation

Sprint: **MARLIN — GAMA–Omniverse Bottlenose Dolphin Behaviour and Animation**.
Milestone: **Map behaviour and movement to visible body animation**.
Prepared 5 November 2026. **Gate C remains pending.**

## Candidate and scope

The candidate reused the accepted Model 61A USD, 20-joint rig and preserved
31-sample, 1.25 s rest-relative swim bake. A new opt-in instance controller
evaluated the existing trunk, tail, fluke and flipper motion at explicit phase
from accepted M3 state. It authored default joint transforms, with no shared
timeline advancement or autonomous update subscription. The M2 static endpoint
and earlier v1/v2 interfaces remained available.

This is coordinated cyclic body motion during the trajectory, with explicitly
limited manoeuvre-specific support. It does not add a biologically validated
bank, asymmetric steering stroke or special dive posture. Root attitude alone
does not satisfy the body-motion requirement: actual UsdSkel skin deformation,
native views and the review sequences are the evidence for the cyclic body motion.

The original asset, texture, licence and bake files were not edited. No rig,
skinning, mesh, joint-rest pose, source material or fixed calibration was replaced.
No working-asset derivative was required. The fixed Model correction remained
[-90,0,0] with equivalent 1/u engineering scale. Existing source provenance and
biological-calibration limitations remain in the accepted M1 audit.

## Implementation

| Canonical source | Role |
| --- | --- |
| `source/extensions/cris.madil.gama_bridge/config/animation_model61a_m4_v1.json` | Versioned existing-clip mapping and amplitude policy. `animation/m4_controller_v1.json` is the identical execution-evidence snapshot. |
| `simulation_pose.py` in the bridge | Validated joint ordering, explicit phase sampling, periodic cubic interpolation and local-pose conversion. |
| `actor_animated_v3.py` | Opt-in subclass of the M2 ownership lifecycle, with atomic root/body writes and composed pose guards. |
| `routes_animated_v3.py` and bridge extension registration | A bounded animated lifecycle on existing NVIDIA Kit Services. |
| `skeletal_animation.py` in the render service | Shared rest-relative-to-joint-local conversion, also reused by the existing timeline binder. |

The new API prefix is `/integration/gama/v3/animated_actor`; acquire, step,
evaluate, pause, reset, release and status retain M2's token/clock/failure rules.
The original `/integration/gama/v3/actor` remains static. Both use the same
exclusive private `/MarlinGamaBottlenose/Bottlenose_001` namespace, so either
owner refuses a competing acquisition. Existing demonstration animals remain
under `/World/Cetaceans` and are not controlled by this actor.

The actor layer contains one `UsdSkelAnimation` with default TRS values and an
allowlisted animation-source relationship. There are no joint time samples or
global timeline writes. Each root/body update validates first and rolls back its
layer and recorded pose on failure. Guards retain the source geometry, rest data,
materials and calibration fingerprint, and separately compare the composed owned
joint attributes/binding. A foreign joint writer, binding, sample or root opinion
is reported and refused on the next guarded call; there is no claim of policing
arbitrary code continuously between calls.

## State-to-pose capability matrix

| State or capability | Candidate response | Status and limitation |
| --- | --- | --- |
| Steady swimming | Existing cyclic trunk, tail, fluke and flipper motion at recorded phase; speed-based amplitude fade at startup/stop. | Supported engineering cycle; visual acceptance pending Gate C. |
| Submerged swimming | Same local swim cycle while M3 holds depth and heading. | Supported cyclic motion; underwater optical appearance retains the water preset's limitations. |
| Gradual turn | Existing local cycle continues; the owned root follows M3 heading. | Limited: no new asymmetric steering stroke or manoeuvre-specific torso curve. |
| Descent | Existing local cycle continues; root follows M3 negative trajectory pitch and increasing depth. | Limited: no separate dive-specific local joint offsets. |
| Ascent | Existing local cycle continues; root follows positive trajectory pitch and decreasing depth. | Limited: no separate surfacing/breathing posture or anatomical clearance guarantee. |
| Zero speed and recovery | Amplitude fades to the original rest pose; recorded rate freezes at zero speed. Pause/resume and reset hold composed root/body/phase until the next explicit state. | Supported technical lifecycle; no independent fallback motion. |
| Banking, sharp evasive turns, novel strokes | None added. | Unsupported by this mapping. Requires a bounded refinement decision before any additional adaptation. |
| Fully airborne/breach animation | No such segment occurs in the accepted M3 trajectory. | Unsupported/unexecuted; dry views expose geometry but are not an airborne water-contact test. |
| Force-generated propulsion or biological tail-beat relation | None inferred from the visual cycle. | Unvalidated and outside this candidate's acceptance. |

Gate C is asked to accept this bounded supported/limited map for the integrated
engineering demonstration, or request a specific local refinement. Unsupported
manoeuvres are not included in a blanket pass claim. Substantial asset or rig work
still requires the separate scope decision retained by Gate A.

## Deterministic pose and blending

M3's recorded `animation_phase_cycles` controls phase. The existing closing sample
duplicates the first, so the controller evaluates the 30 unique loop knots using
periodic cubic interpolation. Quaternion control points are normalized and
hemisphere-aligned before the periodic component cubic is normalized. Translation
and scale use the corresponding periodic cubic. This produces a continuous loop
and matching seam derivative without rewriting the bake.

For horizontal speed v, u is clamped to [0,1] from `v / 0.7 m/s` and the visual
amplitude weight is `6u^5-15u^4+10u^3`. Relative translations and scale deltas fade
from rest; relative rotations blend from identity. This is an explicit engineering
display policy, not a physiological speed/frequency law. All five state labels
reuse the same cycle, avoiding an unrecorded label-triggered pose change. M3's
smooth root orientation remains separate from local body animation.

The synthetic root is locked to identity after confirming the preserved bake has
no synthetic-root locomotion. `MAIN_18` retains the existing cyclic trunk rotation
and constant near-zero local translation. The motion-root matrix is still exactly
the M2 mapping of GAMA position/depth/attitude; animation never adds its own
horizontal motion or heading. Root, local TRS, phase and weight are retained in
native frame sidecars and CPU pose records.

## Numerical checks and retained failures

`animation/m4_acceptance_v1.json` and `qa/m4/locked_plan.json` fixed the applicable
root, joint, skin, loop and gross-deformation criteria before pose acceptance.
The original M2 tolerance record and accepted M3 trajectories were unchanged.

- Eight composed-USD/UsdSkel tests passed in `qa/m4/cpu_attempt05.json`.
- Sixty-one loop phases evaluated all 21,504 vertices and 40,208 triangles.
  Maximum vertex movement from rest was about 0.4143 m, demonstrating deformation.
  Edge ratios stayed approximately 0.778–1.323, area ratios 0.733–1.380 and the
  minimum rest/deformed face-normal dot product was 0.710; no sampled gross guard
  failed and no rest triangles were excluded as degenerate.
- Loop probes across 1→0 differed by about 0.000150 degrees, below 0.001 degrees;
  the derivative discrepancy was about 0.000260 degrees/cycle, below 0.05.
- The shared timeline binder and explicit instance pose agreed at all 30 bake
  knots within the original 2e-6 joint-matrix component criterion after the
  quaternion correction described below.
- The original static v3 suite passed 12 tests, and both existing baked-data
  checks passed. Live opt-in API checks applied all 297 accepted M3 snapshots
  and passed 341 lifecycle/composed-state checks, including reordered nonzero
  poses, pause/resume/reset, ownership exclusion, source immutability and release.

All 681 candidate native frames were compared with the final evaluator:
root-matrix and phase/weight errors were zero, and maximum joint-matrix component
error was 1.1921e-7 against 2e-6. Six reopened native pose snapshots spanning the
principal states matched all 21,504 CPU-evaluated skin vertices with zero measured
discrepancy. See `qa/m4/native_pose_comparison.json`.

Failures were retained rather than overwritten. The first CPU attempt used a
non-public Python constructor for `UsdSkel.AnimQuery`; the corrected harness used
`UsdSkel.Cache.GetAnimQuery`. A later added legacy compatibility check exposed
rounded bake quaternions with scalar exactly 1 and a small nonzero vector. Direct
`Gf.Rotation` conversion discarded some intended small rotations. The shared
converter now normalizes finite, nonzero quaternions first. The failed maximum
matrix discrepancy was 0.00062077; no tolerance or bake/asset file was changed.

The gross guards do not prove exhaustive absence of nonlocal self-intersection.
Close/native views and the named review must inspect skin continuity, flipper and
fluke attachment, distortion, collisions and contact. These engineering metrics
are not numerical biological-realism scores.

## Native review capture and environment

The native harness uses one existing viewport and NVIDIA's capture utility on a
disposable frozen stage copy. It uses the unchanged `engineering_v1` material and
fixed ocean phase zero for inspection. Wet cameras remain above the frozen wave
height bounds. A separate dry geometry diagnostic hides the ocean to expose local
deformation; it is clearly labelled and supplies no underwater-optics evidence.
Background demonstration animals are hidden only in the disposable diagnostic
copy. The original live stage is reattached after every job, with camera, settings,
resolution, timeline and selection restored.

The prescribed root depth starts at 0.2 m. Native sidecars distinguish overlap
with the wave-height band from fully submerged bounds and retain counts of skin
vertices above mean sea level. These are not anatomical contact/collision or
breathing guarantees; actual surface contact must be inspected in the wet views.

The normal-speed review sequences contain explicitly edited windows [2,8),
[12,18), [26,30), [40,44), [52,56), [68,74) seconds, sampled at 10 frames/s and
encoded at the same rate. The cuts and simulation timestamps are labelled. This
is not the complete continuous 74-second M5 demonstration. Per-frame pose and
camera metadata remain the authority; delivery wall time never advances phase.

Native RGB is a visual diagnostic. GPU sample counts, radiometric calibration and
RGB identity were not certified. The diagnostic physical-exposure controls were
explicitly recorded; a frozen pose and timeline prevent a long diagnostic exposure
setting from being presented as an animal motion-blur experiment. Existing camera
contracts and scientific capture records were not rewritten.

The current pre-work scene had both ocean and chase controllers already stopped.
A temporary ocean controller supplied the native preset preparation; it must be
stopped and the exact pre-work `checkpoint_4fde7e3u` restored after the jobs. Earlier
M2/M3 observations of running controllers were not silently substituted for this
new pre-work state.

Exploratory native failures were retained: missing stopped-ocean state, saturated
images, an overly dark exposure, a writer-completion race and startup swapchain
failure. The XWayland display actually reported 0×0 with no active outputs; window
size overrides alone did not fix it. Native `--no-window` mode recovered rendering
without OS display, SDK or driver changes. The shader/asset-converter startup
libxml2 issue remained pre-existing and was not used for conversion.

The final candidates are `dry02` (24 diagnostic snapshots and 300 movie frames)
and `review01` (57 snapshots and 300 movie frames). Their two 30 s, 10 fps videos
and original frames remain in `artifacts/gama_dolphin_behaviour_v1/m4/`; compact
contact sheets and the video/file hashes are retained in this experiment. The
brighter exploratory `dry01` and all smoke attempts were also preserved. Dry and
wet views use separately recorded exposures; no light or animal material was
changed to obtain the diagnostic visibility. Minimum sampled free GPU memory
was 1,636 MiB (dry candidate) and 1,675 MiB (wet candidate), above the reused
768 MiB preflight guard.

A final metadata correction removed an inherited M2 `static_rest_pose_m2` hint
from animated endpoint responses. The raw capture sidecars retain that old hint
as historical evidence; their explicit `pose_controls`, composed joint TRS and
capture source snapshot identify the actual animation. The final subclass reports
`existing_baked_cycle_m4_v1` and `body_animation_evaluated=true`. All 681 retained
numeric poses were verified against that final subclass; this correction changed
no pose math, phase, asset or tolerance.

Eight checkpointed process reloads covered implementation loading, capture
corrections, the unsuccessful GUI/window-size attempt, headless recovery and final
normal-window restoration. The original scene's 38 prims were restored with **zero** composed
attribute/relationship differences; all original controllers, water selection,
camera, resolution, display and renderer settings matched pre-work. The temporary
ocean and diagnostic worker were removed. The interim offscreen checkpoint
`checkpoint_cgp8owp0` is copied under `qa/m4/live_final`. The user confirmed Ubuntu
26.04 with Wayland and an active display. A later XWayland check reported a valid
1366×768 output, allowing the normal MARLIN window to be restored without desktop
or driver changes. Final GUI checkpoint `checkpoint_crnswl_g` is copied under
`qa/m4/live_gui_final`; `final_gui_checks.json` and
`restored_gui_stage_comparison.json` verify the restored scene and settings.
MARLIN remains available on port 8011 with its normal window and no QA worker.
Final sampled free GPU memory was 1,805 MiB, driver 595.99.02. No system reboot
or installation change was performed. The earlier zero-sized display observation
was a transient session condition, not evidence that the physical monitor was off.

The historical M1/M2/M3 and water M5/M6 files and original committed source
versions were verified separately. Literal old current-source verifiers now
detect the intentional extension/converter version changes; their seals were
not rewritten to hide this. See `qa/m4/historical_preservation.json`.

## Review and next boundary

See `reviews/GATE_C_REVIEW.md`, the native contact sheets, review sequences and
machine-readable final verification. Gate C remains pending until a named human
accepts the exact candidate and its explicit manoeuvre limitations. M5 complete
sequence/reload/recovery and final visual/biological decisions remain separate.

Technical references: [OpenUSD skeletal schemas](https://openusd.org/release/api/_usd_skel__schemas.html),
[query cache](https://openusd.org/release/api/class_usd_skel_cache.html) and
[NVIDIA Linux display/headless guidance](https://docs.omniverse.nvidia.com/kit/docs/kit-manual/108.1.0/guide/linux_troubleshooting.html).
