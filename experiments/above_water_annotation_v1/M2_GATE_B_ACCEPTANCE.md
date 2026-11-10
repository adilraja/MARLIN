# M2 — Gate B acceptance

**MAR accepted `above_water_m2_dry_validation_v2` on 10 November 2026**, explicitly replying: “Accept Gate B as MAR”. Milestone 2 — Validate dry-scene geometry and native annotations — is complete for the reviewed bounded dry engineering scope.

The [named decision](reviews/MAR_GATE_B_2026_11_10.json) binds the acceptance to the sealed [V2 review packet](reviews/GATE_B_REVIEW_V2.md), [technical report](reports/M2_DRY_ANNOTATION_VALIDATION_V2.md), original evidence manifest, sixteen validated dry rows, frozen-pose and alternating-state checks. The selected development native-ID API and its native SDK identity mapping were included in the review.

The standard instance API remains unqualified because of its empty prim paths. Completely geometry-empty products remain unsupported; the target-absent controls used a distinct non-target background. The weaker immutable-state/native-time assurance, unavailable per-AOV frame IDs and vendor compatibility warning remain explicit limitations. Acceptance did not qualify marine labels, biological validity, real-seawater optics, research capture or ML training. The separate ocean-material M4 issue remains open.

The original technical packet and pending review records retain their pre-review status as immutable snapshots. [Current Gate B acceptance](reviews/gate_b_acceptance_state.json) and [current progress](CURRENT_PROGRESS.json) record the accepted state. No accepted evidence or historical failure was rewritten.

All 16 dry cases passed; 24 total attempts were retained and 16 reserve attempts remain. The main MARLIN installation, canonical source and prior accepted dolphin/ocean work remained unchanged. This acceptance record did not launch Kit or execute captures.

Gate B’s prerequisite for bounded M3 qualification is satisfied. **M3 remains unstarted, and the sprint remains open.**

Verify the acceptance and its underlying evidence read-only:

```bash
/usr/bin/python3 -B experiments/above_water_annotation_v1/qa/m2_acceptance_v1/verify_gate_b_acceptance.py
```
