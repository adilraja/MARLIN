# M1 and Gate A acceptance — 9 November 2026

**MAR accepted Gate A for `above_water_m1_audit_v1`. Milestone 1 is complete.**

The explicit response was: "Accept Gate A as MAR". The [named decision](reviews/MAR_GATE_A_2026_11_09.json) binds the acceptance to the sealed M1 audit, review packet, capture/annotation contract, numeric acceptance plan, row-level workload, implementation proposal and restoration rules.

Acceptance retained all four audit limitations: the native segmentation provider was not registered in the queried profile; the metadata probe timed out during shutdown; shared HDR/EXR/annotation frame provenance was not established; and marine annotation/refraction support remained untested.

The accepted proposal begins with bounded isolated native-provider and clean-lifecycle feasibility. **Any required new dependency installation must stop for a concrete proposal and review first.** No main MARLIN upgrade, biological/optical/survey qualification, production research dataset or ML training was authorised by this acceptance.

The original technical manifest and Gate A packet retain their pending-at-preparation wording as historical evidence. Their bytes remain unchanged. The [current gate state](reviews/gate_a_review.json), [sprint status](SPRINT_STATUS.json) and separately sealed [acceptance manifest](reviews/MAR_GATE_A_2026_11_09_acceptance_manifest.json) record the subsequent decision.

Recording the acceptance did not start M2, alter production source or the scene, install dependencies, launch Kit, render images, create a Git commit or push to GitHub. The separate ocean-material M4 underwater-camera attenuation issue remains open.

Read-only verification:

```bash
/usr/bin/python3 -B experiments/above_water_annotation_v1/qa/m1/verify_gate_a_acceptance.py
```
