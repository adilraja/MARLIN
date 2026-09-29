# Milestone 1 readiness audit

Audit date: 2026-09-29. Source commit:
`a7949fd12577a8cceb3a102aa49506f03567d7ff`.

The audit and initial protocol are complete. MARLIN has substantial reusable
camera, capture and scene infrastructure, but the pilot dataset is not ready
to generate. Later milestones require target calibration, evaluated-mesh
annotations with visibility checks, a five-GSD capture integration and an ML
runtime. No experiment images or detection results have been produced here.

## Evidence levels

"Passed now" means an offline check executed in this audit. "Historical" means
a stored local report or source documentation was inspected, not that a new
capture was made or all old output hashes were recomputed. "Pending" means no
completion claim is made. Generated Kit directories and bytecode were excluded.

## Capability assessment

| Capability | Finding and evidence | Required next work |
| --- | --- | --- |
| World-space model measurement | Implemented in `tools/gltf_to_usd.py`: evaluated mesh vertices transformed by evaluated `matrix_world`, combined bounds, dimensions and maximum dimension | M2 apply meaningful anatomical measurements; bounds alone do not establish animal length |
| Cetacean gallery | Exists; current gallery layout and asset-existence tests passed | No gallery rewrite or species expansion |
| Generic pinhole camera | `calibration_geometry.py` implements camera authoring, projection and plane sampling; existing real-USD tests passed | M4 integrate existing camera with isolated marine capture and validate all five imaging conditions |
| HiDef reconstruction | Fixed 549 m, 150 mm profile with 30-degree pitch and supported inferred rolls; current camera and projection tests passed | Preserve profile and evidence status; do not vary it in place to create the pilot |
| Sony preview | Fixed provisional profile; current geometry/USD tests passed. Historical nine-target preview validation passed | No native Sony requirement; preserve unresolved acquisition and intrinsic evidence |
| Frozen scene and replay | `freeze_stage`, private-layer replay, callback capture gates, hashes and restoration implemented; current regressions passed | M3 reuse one biological snapshot across the five camera variants and compare scene identities |
| Environment | Fixed flat diffuse `survey_fixed_v1` JSON and application endpoint exist; preset still says `visual_QA_pending` | M3 create resolved `gsd_baseline_v1`, freeze renderer/exposure too, inspect target appearance |
| Seed and split utilities | `condition_seed` excludes GSD; `validate_split_records` protects four identity fields; current tests passed | M3 scene sampler/manifest; M6 actual split assignment and immutable IDs |
| Animal labels | `hidef_marine.animals_record` projects eight world-AABB corners and records USD visibility; source explicitly disclaims visible-target ground truth | M4 evaluated-mesh boxes, declared amodal/visible semantics, underwater correspondence and pixels-on-target |
| Dataset export and training | Survey JSON describes contracts; no complete pilot exporter/training implementation found in inspected canonical source/tools | M4–7 implement bounded pipeline and lock a standard detector |
| GAMA bridge | Existing offline exchange, live-protocol mocks, actor and image-evidence tests passed | Preserve it; do not depend on it for the pilot |

The generic camera decision and all experiment-specific settings are in
`PROTOCOL.md` and `specification.json`. Existing `survey_v1.json` predates later
camera work and includes classification and threshold goals outside this sprint;
it is not copied wholesale or silently rewritten as the pilot protocol.

HiDef evidence remains unresolved for deployed GT6600C identity, ROI versus
binning, ROI origin, exact 150 mm lens, physical mounting roll, distortion,
intrinsics and true camera-to-sea height. Sony trial mode/crop, lens, intrinsics,
distortion, mounting, exposure/readout and height reference remain unresolved.
The source evidence file is `config/camera_hardware_evidence_v1.json` under the
render-service extension; published/inferred/assumed values remain distinct.

## Target shortlist and calibration gaps

| Asset | Evidence available | Current limitation |
| --- | --- | --- |
| European storm petrel working rig | Real-USD pose/playback tests passed; historical Kit rig review and static pose exports exist; original source and licence retained | Physical scale unverified; species identity comes from task attribution, not independent taxonomic verification; cleaned foot contacts and pose suitability need review |
| Harbour porpoise static candidate | Recorded DigitalLife specimen reference 1.555 m; full transformed measurement, helper exclusion explanation, preserved original rig, reopened USD bounds check | Landmark-to-publisher measurement correspondence and waterline remain provisional; `scientific_render_ready` is false |
| Northern gannet cleaned copy | Textures and pedestal removal reviewed historically | Still standing with folded wings; physical scale, flight and on-water states not ready |
| CARI'MAM bottlenose candidate | Existing provisional 2.6 m reference, landmarks, axis correction and real-USD tests | Anatomical correspondence unresolved; shallow-swim only; conflicting source/top-level licence attribution already flagged |

M2 should inspect petrel and porpoise first. They are candidates, not selected
calibrated animals. Do not set the physical scale to 1 or 100 by convention,
assume USD `metersPerUnit` proves biological size, or repurpose display placement
as calibration. No new biological dimensions were chosen during this audit.

Relevant records:

- `assets/birds/european_storm_petrel/README.md`
- `assets/survey_species/european_storm_petrel/manifest.json`
- `assets/cetaceans/model_75a_-_harbor_porpoise/working/calibration_v1/calibration.json`
- `assets/survey_species/inspection_comparison/KIT_REVIEW.md`
- `integrations/gama/BOTTLENOSE_CALIBRATION.md`

## Historical capture evidence and native status

HiDef preview replay `oblique_84nq0v7m` / `oblique_2oh2ojlw` has a stored passed
verification report. Sony probe `sony_39sl5rol` and marine replay
`sony_e9yl1vk9` / `sony_60p_93va` have stored passed geometry/replay reports.
Their capture-time appearance is not a validated pilot environment.

The native 6576 x 2192 metric probe `oblique_a3dx2mg2` passed overlaps. It has
`projection_probe: true`; it does not certify animal/ocean radiometry.
Full native marine records `oblique_htk8y1za` and `oblique_wfbfsc4p` failed
overlaps despite passing geometry/dimensions/restoration checks. Both remain
diagnostic evidence.

The later SDK tile-pair report `artifacts/hidef_marine/sdk_pair_comparison.json`
records a focused pass: worst neighbouring overlap mean 1.652301/255 and worst
identical-repeat mean 0.055182/255, under the existing 2/255 limit. This is a
subset, not a complete accepted native marine image. The source now contains
`sdk_tile_capture.py`, so older notes saying the SDK is not integrated are stale.

Current classification: **partially validated**. Do not label native rendering
fully validated or solely hardware-limited. M4 still owes the bounded complete
marine check and a clear record of any resource or radiometric failure.

## Runtime and dependency observations

- Local API GET of `http://localhost:8011/openapi.json` failed with connection
  refused after a host-level retry. No responding Kit HTTP service was available
  at audit time. This is not proof that no Kit process exists. No Kit process was
  launched, stopped or restarted during M1.
- Host-level GPU query succeeded: NVIDIA RTX A2000, 6138 MiB total, 4672 MiB free
  at that instant, driver 595.91.07. Headroom is transient and must be rechecked
  at capture time. The initial sandbox GPU failure was not a hardware failure.
- Official Blender 5.0.1 supplied Python 3.11.13, USD 0.25.8 and NumPy 1.26.4.
- The desktop dependency runtime supplied Python 3.12.14, NumPy 2.3.5 and
  Pillow 12.3.0 for image tests.
- Default Python, Blender Python and the desktop dependency Python had no
  installed Torch, Torchvision or Ultralytics distribution in the checks used.
  No model checkpoint or training entry point was found in inspected project
  source/tools. This is not an exhaustive search of all user environments.
  Selecting/provisioning one standard detector is an explicit M6 dependency.

## Regression results

**126 existing offline tests passed, zero failures/errors/skips in the final
two-suite run:** 118 in Blender/USD and 8 in the existing image runtime.
Per-test IDs, runtime versions, timestamps and the source commit are recorded
in `qa/baseline_usd.json` and `qa/baseline_image.json`; matching logs retain output.

The initial combined Blender run recorded 118 passes and two module-import
errors because Pillow was unavailable there. It is retained in
`qa/baseline_tests.json` and `.log`. Both affected modules subsequently passed
their eight tests in the dependency runtime; neither tests nor application code
were weakened. These are offline regressions, not a live endpoint smoke test.

`qa/input_provenance.json` identifies 146 canonical source and selected evidence
files by SHA-256. The tracked source/tool diff is empty. Existing untracked
`GEMINI.md` files are recorded as inputs, not newly authored changes.

## Required implementation order

1. M2: select and measure the two targets; review provenance, axes, pose and
   waterline; resolve a supported Kit session to validate spawning.
2. M3: resolve state ranges and renderer settings; generate and reconstruct
   frozen seeded biological scenes.
3. M4: reuse the capture/restoration machinery for the generic camera; implement
   evaluated geometry labels, presence QA and sampling metadata. Validate two
   complete five-GSD sets before bulk generation; complete the native status job.
4. M5–6: generate auditable data, freeze grouped splits, provision and lock the
   detector and verify the no-resize input path.
5. M7–8: train once under the protocol, evaluate held-out paired scenes, plot
   provisional results and report uncertainty and limitations.

No render-ready status, native certification, target calibration or ML success
has been inferred from these audit results.

## Protocol geometry feasibility

The five selected generic camera configurations were additionally checked with
the existing USD camera builder. All produce the requested flat-plane GSD;
maximum sampled reprojection error is 0.000011433 px. At the finest GSD the
footprint is 5.12 x 3.84 m; at the coarsest it is 40.96 x 30.72 m. M3 must fit
the calibrated targets in the finest footprint without per-GSD repositioning.
`qa/protocol_geometry.json` records these offline results. They are additional
feasibility checks, not part of the 126 regression-test count or live rendering.
