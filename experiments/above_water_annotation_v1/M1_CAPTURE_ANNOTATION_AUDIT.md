# M1 — Capture, camera and annotation audit

Sprint: **MARLIN — Above-Water Capture and Annotation Validation**. Evidence version: **`above_water_m1_audit_v1`**. Prepared on **9 November 2026**.

**M1's audit and proposed execution contract are ready for Gate A. Gate A is pending; implementation has not started.** This record distinguishes observed capabilities, retained historical results and proposed future acceptance criteria.

## Principal findings

| Question | Evidence and disposition |
|---|---|
| Current driver/resources | Host query returned NVIDIA RTX A2000, 6,138 MiB, driver 595.99.02. Before the probe: 2,328 MiB free. After cleanup: 2,385 MiB free. These are samples, not an allocation peak or a capacity guarantee. Free disk after the probe was 127,157,559,296 bytes, above the proposed 10 GiB campaign minimum. |
| Existing live marine scene | `localhost:8011` refused connection outside the sandbox. No live checkpoint or controller inspection could be retrieved. The audit did not restore a historical scene or stop an existing MARLIN process. The post-probe host process query found no process named `kit`. A service failure alone is not proof that every possible other application/port is absent. |
| Installed runtime | A finite private-profile launch of the known MARLIN launcher returned Kit `110.2.0+feature.342835.698af100.gl`, USD `0.25.11`, `omni.hydra.rtx` 1.0.4, `omni.kit.renderer.capture` 2.0.1 and `omni.kit.viewport.utility` 2.1.0. |
| Native annotation provider | The runtime extension manager returned 224 registered installed entries. Neither `omni.replicator.core` nor `omni.syntheticdata` appeared in the queried inventory. No annotator was enabled, package downloaded or segmentation API exercised. This is a profile/installation capability gap; it is not proof that NVIDIA cannot supply the capability. |
| Probe lifecycle | Metadata returned successfully, but process shutdown did not complete within the 120-second deadline. Only the owned probe process group was terminated. Retained logs also contain the known asset-converter/importer import errors. No asset conversion was attempted. Metadata availability does **not** mean clean startup/shutdown or rendering passed. |
| Existing HDR capture | Native float-buffer/EXR capture already exists. Its inventory, buffer and EXR are scheduled separately. `frame_info` is received by the inventory callback but not retained. A common HDR/EXR/mask frame identifier is not currently established. |
| Geometry/camera support | Existing capture-product checks validate the authored USD camera, resolution, pixel aspect and data window independently of the UI projection. Existing freeze logic evaluates sampled attributes into a private flattened stage; accepted native CPU skinning evidence is retained. |
| Preservation | All 119 current canonical source files matched the before-audit inventory. The full bottlenose Gate D verifier passed again. Ocean immutable evidence/preset checks passed separately; three superseded historical source pins are explained below. |

The recorded `runtime_query.json` has `passed=true` for the metadata query only. Its companion `runtime_probe_process.json` records `timed_out=true`; the combined lifecycle disposition is **metadata returned, shutdown timed out**. The probe used an application-created private default stage with 14 prims, Y-up and 0.01 metres/unit. Those values are not represented as a newly inspected live marine scene. No user checkpoint was opened in that process. No new images or annotation arrays were produced.

Evidence: [host observations](baseline/host_after_probe.json), [runtime API query](baseline/runtime_query.json), [probe lifecycle](baseline/runtime_probe_process.json), [exact launch command](baseline/runtime_probe_command.json), [retained probe log](baseline/runtime_probe_stdout.log).

## Baseline and prior acceptance

The current Git head was `ba75626bae6b5d4ddf1b4423ffaf241f5338a2a9`. The working tree already contained uncommitted sprint-document changes, historical logs, support diagnostics, presentation and backup files. The [before-audit Git status](baseline/git_status_before.txt) records them. This audit made no commit and did not collect unrelated files into a commit.

The [bottlenose preservation verification](qa/m1/bottlenose_preservation_verification.json) confirms MAR's existing Gate D acceptance and technical seal, including the accepted source/assets, pose/replay evidence and review boundaries. Its reported 188 tests are the **historical sealed results verified for preservation**, not 188 newly executed regression tests in M1. The accepted scope remains engineering/visual, with provisional biological support and no optical/research-capture approval.

The old ocean M6 verifier does not pass unchanged against today's source: it pins earlier versions of `gama_bridge/actor.py`, `gama_bridge/extension.py` and `render_service/skeletal_animation.py`. Those were subsequently changed by the accepted bottlenose M2/M4 work (`ac9022d` / `143d404`), and their current bytes match that later accepted package. Reverting them would damage valid later work. The [separate ocean pin audit](qa/m1/ocean_preservation_verification.json) retains the failed legacy command/trace and verifies **182 immutable evidence files, 3 checkpoint artifacts, 16 preset files and 4 local asset dependencies**. Another 110 historical source pins still match. No old seal, acceptance record or source was rewritten to manufacture a pass.

Moving the completed dolphin specification into `Sprints/PastSprints` in the preceding preparation turn had broken a path pinned in Gate C. M1 restored the original path as a symlink to the byte-identical archived file and added a CurrentSprint index. Both resolve to SHA-256 `cd7514ee774a27ba5416337a05a46d0d23ced4bb49abd06edfe0e5eb310d76d0`. The earlier acceptance verifier then passed. The archive stayed unchanged; this is documentation-path repair, not an implementation change.

The [evidence pins](baseline/evidence_pins.json) bind the selected prior records, asset/licence, preset, source helpers and representative images. The [source preservation result](qa/m1/source_preservation.json) covers all 119 current canonical source files.

## Actual animal and reusable geometry

The selected source is the accepted DigitalLife3D **Model 61A bottlenose dolphin**, not the old static harbour-porpoise proxy. Existing audit/rig evidence identifies two skinned meshes, 21,504 authored/evaluated vertices, 40,208 faces and one 20-joint skeleton. No Icosphere/helper mesh was present in that accepted composed asset. Revalidate composition and purposes when building a private M2 fixture; do not delete source components.

The existing v3 actor namespace is `/MarlinGamaBottlenose/Bottlenose_001`. Its two target meshes end in `Object_7/Object_0` and `Object_8/Object_1` beneath the preserved Model/Sketchfab/Armature hierarchy. Reuse that namespace in a private scene. Do not refactor ownership or rename the actor just to attach labels. Retain complete raw per-frame native ID mappings and union only IDs resolving to those two owned meshes; class equality is insufficient.

The actual engineering profile retains Model rotation `[-90,0,0]` and equivalent scale 100 at 0.01 metres/unit. The composed animated root matrix has its own heading/pitch/roll and translation. Keep those distinct. These are asset-transform facts, not new species-wide calibration or biological dimensions.

Two immutable body states were selected before new rendering:

| Pose | Existing source | Body phase | Retained attitude |
|---|---|---:|---|
| A | `m3_ref_a01`, t = 6 s | 0.25 cycles | Existing steady-swim root attitude |
| B | `m3_ref_a01`, t = 30 s | 0.45 cycles | Existing descent root attitude, including its accepted limited pitch |

Both have full cycle weight 1.0. Their state, scene, evaluated-skin hashes and exact proposed Y offsets are in [selected poses](baseline/selected_poses.json). No new GAMA execution, rig evaluation or source-geometry modification is claimed by copying these existing records.

Each exposed placement has at least 0.25 m clearance above the conservative +0.4 m wave envelope; each submerged placement has at least 0.25 m clearance below -0.4 m. The surface placement centres the retained vertical extent on zero, guaranteeing vertices on both sides of every surface inside that envelope: the smaller bracket margin is approximately 0.01176 m for pose A. M2/M3 must additionally validate actual mesh triangles and the constructed render surface. Extent/vertex signs alone do not certify every anatomical part or the final interface geometry.

## Camera and ocean declaration

The initial product is **512 × 384**, square pixels, full image window, 35 mm focal length and 30.72 × 23.04 mm aperture. The corresponding ideal focal length is 583.3333 pixels in X/Y, with principal point (256,192). This is a virtual engineering camera; the 60 µm effective sampling is not a physical sensor specification.

Nadir and 40°-from-nadir oblique cameras sit 8 m above mean sea level, centred horizontally on the retained actor root for each pose. The oblique horizontal offset is `8*tan(40°)` along +Z. Roll is zero; near/far are 0.01/50 m, f-stop zero, motion blur disabled by the proposed capture configuration. Cameras remain at least 7.6 m above the conservative wave envelope.

The [offline framing check](qa/m1/proposed_framing.json) uses the existing `CalibrationConfig` and retained evaluated skin. All twelve pose/placement/view combinations fit, with at least **63.19 pixels** direct-projection margin. This is an offline direct-geometry calculation, not a new native raster check or proof of refracted framing. Saved native camera/product matrices must still be checked in M2.

Reuse the accepted ocean configuration: size 16,000 scene units, resolution 128, wave height 40, wavelength 650, speed 0.7 and choppiness 0.55, at the existing 0.01 metres/unit. The four canonical wave amplitude multipliers sum to one, giving the conservative ±0.4 m top-surface bound. Declare frozen phases 0 and 1.25 seconds; do not introduce an autonomous wave clock during capture.

The five scene conditions are dry reference, private clear flat control, private `engineering_v1` flat control, and `engineering_v1` at the two frozen wave phases. Flat controls retain a consistently closed boundary matching the top surface. Their derived settings/geometry require their own diagnostic checks; prior preset acceptance is not inherited automatically. Preserve the accepted preset bytes and select controls only in private scenes.

## Products, timing and confidence

The [capture contract](contracts/capture_contract.json) requires HDR/EXR, one fixed Reinhard display, a direct amodal geometric box, a qualified native instance mask and a mask-derived tight box. The separately named native tight box is a diagnostic. Physical scene presence, direct frustum intersection, native labelled-pixel count, reviewed appearance and qualification status remain independent. Unsupported data is null with a reason, not an invented empty mask or negative example.

Use top-left pixel-edge origin, centres `(column+.5,row+.5)` and half-open internal mask boxes. Preserve native raw coordinates and establish their inclusivity with dry fixtures before conversion. Native numeric IDs may change after reload; instance/prim identity must still resolve. Reflections, shadows, glints, caustics and wakes are outside the body class.

The existing `capture_hdr` helper schedules three jobs and discards frame information. Its bytes must remain unchanged as prior evidence. The smallest proposed extension is a separate canonical helper that retains frame provenance and captures requested AOVs from one product/state, with a fixed alternating-state stale-frame test. If a shared native frame key is unavailable, immutable-state capture with an explicit weaker synchronisation guarantee requires gate disposition. Do not forge a frame ID or infer image equality from a state hash.

## Workload, limits and smallest implementation proposal

The [complete declaration](declarations/capture_declaration.json) enumerates **60 marine + 16 dry + 12 repeat + 12 fresh-process + 16 synchronisation + 4 marine absence = 120 planned bundles**. The sentinel is 21 of the same 60 marine rows, not extra samples. The named marine review set contains 12 rows spanning both views, all three placements and both wave phases, with both body poses represented. Six additional rendered fiducial controls consume reserve; the total cap remains 144 attempts. M1 used **zero** rendered attempts and copied three historical images unchanged.

The [acceptance plan](contracts/acceptance_plan.json) fixes numeric geometry, state/skin, label-repeat, HDR/display and reviewer-confidence criteria before candidate runs. It copies the accepted root/joint/skin/phase limits and adds explicit camera/ocean bounds, dry reference boundaries and marine uncertainty rules. These are proposed engineering requirements, not newly measured pass results or limits fitted to failed candidates.

Resource admission is 2,048 MiB free GPU before allocation, retaining the existing 768 MiB floor during capture, one product, 90 s per capture, 45 s settling timeout and 600 s per transaction of at most six bundles. Current admission headroom is small and annotation allocation has not been measured. Keep the stricter actual guard if it is raised. The evidence budget is 5 GiB and campaign disk minimum 10 GiB. Three reused historical bundles measured approximately 6.56–6.75 MiB each; 144 at the largest measured size would be about 0.95 GiB before native annotation outputs and other overhead. One uncompressed 512 × 384 uint32 mask adds 786,432 bytes. These are planning estimates, not new-campaign measurements; see `qa/m1/storage_estimate.json`. Budget additional arrays, dependencies and failed attempts explicitly before M2. Do not promise 144 captures from current free VRAM.

The [bounded implementation proposal](reports/IMPLEMENTATION_PROPOSAL.md) begins **after Gate A** with native-provider availability and clean lifecycle feasibility. No package installation or main runtime upgrade is included in the proposed Gate A acceptance. If the provider cannot be used from already installed, officially supported components, prepare the exact dependency/version/isolation proposal and return for review. A geometric-only fallback cannot pass the original visible-label objective.

## Gate A disposition

The audit is ready for review with the dependency, lifecycle, common-frame and marine-appearance gaps visible. See [Gate A packet](reviews/GATE_A_REVIEW.md). No M2 code, semantic labels, production API changes, new renders or human acceptance have been recorded. The separate ocean-material M4 issue remains open.

## Official reference boundary

NVIDIA's [ExtensionManager API](https://docs.omniverse.nvidia.com/kit/docs/kit-manual/110.1.2/omni.ext/omni.ext.ExtensionManager.html) documents installed-extension enumeration. The observed inventory is specific to the isolated queried configuration. [Replicator 1.12.16 API](https://docs.omniverse.nvidia.com/kit/docs/omni_replicator/1.12.16/source/extensions/omni.replicator.core/docs/API.html#default-annotators) lists HDR and instance/box annotators as candidate interfaces. That version was checked as a historical documentation reference on 9 November 2026, not installed or established as compatible by this audit. The draft sprint's 1.13.30 reference likewise grants no local capability. Installed/provider compatibility must be resolved before annotation implementation.
