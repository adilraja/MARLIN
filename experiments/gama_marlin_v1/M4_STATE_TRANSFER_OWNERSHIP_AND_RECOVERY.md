# GAMA–MARLIN Behavioural Integration and Validation

## Milestone 4 — Verify state transfer, control ownership and recovery

**Outcome: passed for engineering state transfer using the existing static
porpoise proxy. Biological suitability and animated dive poses remain unapproved.**

MARLIN applied all **41 actual GAMA-generated states** retained from
`trajectories/m3_seed_184729_a`, covering 0–20 simulation seconds and all five
state labels. Four manually constructed cardinal-heading fixtures were tested
separately and were not described as GAMA execution evidence.

## Numerical acceptance

The limits were declared in `integrations/gama/PORPOISE_REPLAY_V2.md` and the
acceptance tools before execution. Expected positions were independently
calculated as `[x, -depth, z]`; actual positions and headings came from
`ComputeLocalToWorldTransform` on the live MARLIN USD actor root. The real stage
explicitly declared Y-up and 0.01 metres per scene unit.

| Check | Declared limit | Largest live error |
|---|---:|---:|
| Euclidean world position | 0.00001 m | 1.2561 × 10⁻¹⁵ m |
| Circular heading | 0.0001° | 3.6398 × 10⁻⁶° |

These results covered four cardinal headings and all 41 retained states. Root
depth was relative to the contract's fixed mean-sea-level plane Y=0. It did not
measure anatomical water clearance or follow the animated waves.

## Ownership, failure and recovery

The v2 animal lived at `/MarlinGamaPorpoise/Porpoise_001` in a removable private
USD layer. It reused the existing bridge ownership, spawning and release
lifecycle; the original v1 actor retained its behavior. The autonomous gallery
controllers targeted `/World/Cetaceans` and never enrolled the bridge actor.
The bridge had no update subscription, speed integration or autonomous fallback.

- Identical retries preserved the composed transform and accepted-step count,
  refreshed connectivity, and kept exactly one actor.
- Old steps, malformed data, unknown agents, wrong tokens and a second acquire
  were rejected without advancing state.
- Actor reset preserved the token, layer and composed pose while clearing replay
  ordering. The earlier validation-only reset remained independent of ownership.
- A three-second replay interruption held the exact pose and reported
  `frozen_updates_missing`. A fresh HTTP connection retried the last state with
  the same token, then continued the ordered replay without duplicate advancement.
- Capture gates, stage replacement, changed coordinate metadata, missing layers,
  inherited parent transforms and stronger actor-transform overrides were covered
  by automated tests. USD composition that prevented a new requested pose caused
  a rollback instead of a false successful update.
- Scoped cleanup rejected defined prims, foreign children, variants, other
  attributes, connections, time samples and invalid metadata/defaults.

The two-second missing-update threshold was an engineering diagnostic. This
record-first workflow tested HTTP client reconnection, not restoring ownership
tokens after a crashed Kit process or a live GAMA Server connection.

## Coexistence and clean removal

The previously empty live stage was populated with MARLIN's existing marine
demonstration APIs. During replay and after release, all eleven original animals
continued moving with their controller configurations intact, and the animated
ocean advanced. Camera, renderer settings, stable lighting/material attributes
and ocean configuration were unchanged. Release restored the original layer
stack and left neither the owned animal nor its private root on the active stage.
Kit stayed running throughout; no scene-destroying restart was used.

## Visual evidence and capture correction

`qa/m4_live_03/porpoise_replay_demo.gif` is a **12-second, six-keyframe** diagnostic
demonstration with actual Kit frames and plots of the measured composed path and
depth. Its JSON sidecar records raw-image hashes, camera projection metadata and
frame timing. The camera followed the animal; the plots exposed its movement.
The six raw frames and GIF layout were visually inspected, as recorded in
`qa/m4_visual_review.json`.

The first run's numeric/coexistence assertions passed, but visual inspection
rejected its gallery-overview images. They were preserved with an explicit
rejection note. A subsequent acquire exposed RTX camera exposure placeholders
outside the owned layer. Camera delivery now waits for app updates and rendered
frames, validates the actual render-product camera before/after RGB capture, and
removes only newly created allowlisted diagnostic overrides. The original
placeholder repair was separately recorded. Failed attempts were preserved;
`m4_live_03` is the accepted live run.

The final offline checks also strengthened rejection of variant-bearing private
roots. That maintenance-only predicate refinement followed the accepted live
replay and was verified by the final offline suite; it did not change pose
application or camera capture.

## Verification and preservation

The final offline suite passed **86 tests**, including 24 new actor tests and
the existing v1 actor, v1/v2 exchange, stage/router, protocol and GAMA-export
tests. The final report is `qa/m4_final2_offline_results.json`; earlier reports
remain immutable development evidence.

The protected baseline's **914 files** remained unchanged. The two intentional
source deltas were the shared actor lifecycle hooks and additive extension routes.
All protected M2/M3 evidence and all 18 retained real GAMA record files remained
unchanged. The original checkpoint, its separate backup and the baseline archive
matched their stored hashes. Source syntax and Git whitespace checks passed.

The porpoise asset, textures, calibration record, registry, rendering service,
ocean and autonomous motion implementations were not modified. Existing recorded
asset/dependency hashes, rotation and metric conversion were reused. All five
labels used `static_pose_proxy_v1`; breathing, body animation, dive pitch and
biological review belong to later work. Milestone 5 was not started.
