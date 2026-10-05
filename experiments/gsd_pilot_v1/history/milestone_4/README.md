# MARLIN GSD pilot v1

This directory contains the eight-milestone sprint started on 2026-09-29.
The immediate deliverable is a reproducible, synthetic-to-synthetic detection
experiment for one bird and one cetacean at five paired GSD levels. It will not
establish operational wildlife detection thresholds or certify survey hardware.

## Progress

| Milestone | Status | Evidence or exit condition |
| --- | --- | --- |
| 1. Audit readiness and freeze protocol | Complete | `READINESS.md`, `PROTOCOL.md`, `specification.json`, `qa/` |
| 2. Calibrate two targets | Complete for provisional pilot | `wildlife/CALIBRATION.md`, species JSON records, geometry and live Kit evidence |
| 3. Freeze environment and scene generation | Complete | `environment.json`, 50 candidate manifests, 4 reconstructed scenes and 16 live replay checks |
| 4. Prove paired capture and annotations | Complete with stated limits | 20 settled RGB images, 10 exact direct mesh boxes, paired visibility at five GSDs per target; bounded native status recorded |
| 5. Generate pilot dataset | Pending | At least 25 valid paired scene seeds per target and documented QA |
| 6. Freeze splits and model inputs | Pending | No protected identity crosses splits; model-input geometry verified |
| 7. Train and evaluate baseline | Pending | One reproducible detector and held-out metrics by GSD |
| 8. Package results | Pending | Provisional curves, pixels-on-target, limitations and reproduction evidence |

Milestone 1 completion means the audit and protocol are recorded. It does not
mean the later implementation, target calibration or live rendering passed.
The protocol choices are frozen before observing ML results. Pending parameters
have explicit owners and gates in `specification.json`; resolving them requires
a recorded specification revision before collecting the dataset.

The source baseline is `a7949fd12577a8cceb3a102aa49506f03567d7ff`.
Existing tracked files were clean at audit start. No MARLIN runtime source,
wildlife asset, existing camera profile or historical capture was changed for
Milestone 1. New experiment files are not committed automatically.

Milestone 2 selected the European storm petrel and harbour porpoise. Both pass
live spawning, geometry, heading, texture-resolution and static-placement checks.
The petrel uses a nominal species body length; porpoise landmark correspondence
remains provisional. See [calibration evidence](wildlife/CALIBRATION.md).
Specification 1.1.0 resolves only the M2 target choices. Original M1 README and
specification bytes are preserved under `history/milestone_1/`; its relocation
map allows the original M1 manifest to remain verifiable.

Milestone 3 freezes `gsd_baseline_v1` and the engineering sampler. All 50 candidate
records pass geometric footprint checks; four representative scenes pass
reconstruction and repeated live Kit replay. See [scene generation evidence](scenes/SCENE_GENERATION.md).
Specification 1.2.0 retains the M2 version under `history/milestone_2/`.
Milestone 4 captured both targets at all five GSDs with matched target-absent
counterparts. Every target was visible by paired-image comparison, including the
smallest petrel image. The boxes project all evaluated animal mesh vertices
through the authored camera. For the underwater porpoise they are direct amodal
boxes, not refracted visible outlines. Exact silhouette and visible area remain
unknown. The bounded native tiled path passed its technical overlap and viewport
restoration checks, but its oblique image did not establish pilot target content;
the validated 1024 × 768 generic capture supplies this pilot. See
[M4 capture evidence](qa/M4_CAPTURE.md). Specification 1.3.0 preserves the M3
README and specification under `history/milestone_3/`.

**Required finish step for every remaining milestone:** restore the existing
animated demonstration with moving water and the 11 default animals swimming,
verify motion, and leave the viewport running for the user's visual check. Use
`python3 -B experiments/gsd_pilot_v1/scenes/live_session.py preview --milestone N`
with the completed milestone number. This must show the live animation, not just
a still image or the static inspection gallery. Completed preview records are
preserved on later manual reruns.

## Inputs

- `Codex-Instructions/Current-Sprint/Sprint-29-09-2026.docx`: milestone order.
- `Codex-Instructions/Codex-Instructions-28-09-2026.docx`: detailed sprint scope.
- Root `AGENTS.md`: source locations, architecture and preservation rules.

The user explicitly authorized this sprint on 2026-09-29. Its milestone order
supersedes the earlier gallery-only stopping point; the preservation rules
continue to apply. The audit confirms world-space measurement and the gallery
already exist. No species registry or behaviour-controller expansion is needed.

## Reproduce the offline baseline

Run from the repository root. These commands use existing dependencies and
disable Python bytecode writes. They do not launch Kit or traverse its generated
runtime. Each suite replaces only its own current baseline JSON and log.

```bash
PYTHONDONTWRITEBYTECODE=1 /home/madil/opt/blender-5.0.1-linux-x64/blender --background --factory-startup --python-exit-code 1 --python experiments/gsd_pilot_v1/qa/run_baseline.py -- --suite usd
/home/madil/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B experiments/gsd_pilot_v1/qa/run_baseline.py --suite image
PYTHONDONTWRITEBYTECODE=1 /home/madil/opt/blender-5.0.1-linux-x64/blender --background --factory-startup --python-exit-code 1 --python experiments/gsd_pilot_v1/qa/verify_protocol_geometry.py
```

The second executable is the desktop's dependency-loader-provided runtime;
resolve it again through that loader on another installation. The Blender suite
uses real USD. The image suite uses NumPy and Pillow. No third-party package was
installed into Blender or the project. The initial single-runtime attempt is
retained as `qa/baseline_tests.*`: its two module-import errors were missing
Pillow, not failing assertions. The final split-runtime results are
`qa/baseline_usd.*` and `qa/baseline_image.*`.
The third command checks the five proposed GSD configurations with the existing
USD camera builder. It does not render images or certify the marine capture path.

## Output layout

Create output directories when their milestone starts:

```text
specification.json         Frozen choices and explicit outstanding gates
environment.json           M3 resolved preset and renderer settings
wildlife/                  M2 calibration records and evidence
scenes/                    M3 scene manifests and frozen snapshots
renders/milestone_4/       M4 paired scene snapshots, RGB images and settling probes
annotations/               M4–5 geometry and visibility records, COCO labels
splits/                    M6 immutable grouped split manifests
qa/                        Audit, regression, pairing and capture evidence
ml/                        M6–7 dependency lock, input policy and training runs
results/                   M7–8 metrics, plots and final report
```

Do not put credentials, generated Kit files, model downloads or debug renders
in the experiment provenance manifest. Record unresolved runtime dependencies
honestly; snapshots currently reference external materials and textures.
