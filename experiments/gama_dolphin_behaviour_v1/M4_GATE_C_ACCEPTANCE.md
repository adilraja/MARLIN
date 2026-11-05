# M4 and Gate C acceptance — 5 November 2026

**MAR accepted Gate C for the sealed existing-cycle body-animation candidate.
Milestone 4 is complete within its documented engineering scope.**

The explicit response was: "Accept Gate C as MAR". The decision accepted the
existing-cycle body-animation map, including its limited turn, descent and ascent
poses, as the bounded candidate for the M5 engineering demonstration. The
[named acceptance record](reviews/MAR_GATE_C_2026_11_05.json) binds the decision to
the exact technical seal, review packet, controller, criteria, results and native
review media.

The accepted candidate retained the inspected asset, rig, textures, fixed
calibration and swim bake. It demonstrated local trunk/tail/fluke motion driven
by simulation time, separately from trajectory root movement. Eight CPU tests,
341 live API checks and comparisons of all 681 candidate native frames passed.
Six reopened pose snapshots matched all 21,504 evaluated skin vertices exactly.
The two labelled 30-second clips are edited normal-speed review excerpts.

Turn, descent and ascent continue the existing swim cycle while the root follows
the accepted trajectory. They do not supply bespoke asymmetric steering,
banking, dive-body or breathing poses. Biological approval, optical approval,
survey readiness and final sprint acceptance were not granted. The separate
ocean-material underwater-camera issue remains open.

The technical manifest, original packet and dated pending state were preserved.
The [current Gate C state](reviews/gate_c_review.json) records acceptance; the
[acceptance manifest](reviews/MAR_GATE_C_2026_11_05_acceptance_manifest.json)
seals the subsequent decision. Verification is read-only:

```bash
/usr/bin/python3 -B experiments/gama_dolphin_behaviour_v1/qa/m4/verify_gate_c_acceptance.py
```

Recording this decision did not change MARLIN's scene or runtime implementation,
start M5, create a Git commit or push to a remote. The next milestone is
**M5 — Demonstrate the full sequence and reproducible frozen snapshots**.
