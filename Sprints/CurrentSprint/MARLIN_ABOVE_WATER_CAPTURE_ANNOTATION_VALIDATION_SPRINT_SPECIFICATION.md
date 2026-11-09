# MARLIN — Above-Water Capture and Annotation Validation

## Codex sprint specification

| Field | Specification |
|---|---|
| Document version | 1.0 — proposed execution specification |
| Prepared | 9 November 2026 |
| Repository | `/home/madil/kit-app-template` |
| Experiment identifier | `above_water_annotation_v1` |
| Target | One instance of the existing DigitalLife3D Model 61A bottlenose dolphin, using the accepted asset and body cycle |
| Camera | Ideal virtual perspective camera above the water; one nadir and one oblique view, with actual capture matrices verified |
| Water | Reuse the accepted `engineering_v1` preset; temporary diagnostic controls use private scene copies |
| Primary outcome | Establish which capture and annotation products are correct and reproducible for specified above-water views |
| Proposed first execution | M1 audit and baseline, followed by a stop at Gate A before implementation |
| Current authorisation | Specification preparation only. No milestone execution, runtime change or new capture campaign was started by drafting this document. |
| Completion scope | Bounded engineering validation with a new named review; no research-dataset, biological, optical-calibration or survey approval |

> **Sprint objective:** Bind saved above-water images and precisely defined annotations to the same frozen animal, ocean, camera and renderer state, then establish their supported scope using controlled geometry, occlusion, water-interface and replay tests.

The intended use is to prepare a dependable capture/label contract for a later aerial-imagery study. This sprint does not train a detector, estimate detection probability or establish an operational GSD threshold. The capture count below is a finite validation workload, not a production dataset.

The separate ocean-material Milestone 4 underwater-camera attenuation issue remains open. This sprint may proceed with cameras above the medium; that viewpoint does not by itself establish valid annotations through refractive water. NVIDIA's response can inform a later isolated test, but cannot silently change this sprint's accepted preset, dependencies or criteria.

---

## 1. Baseline, scope and preservation

### 1.1 Evidence carried forward

Read these records before execution, and verify their current hashes during M1:

- [Bottlenose sprint status](../../experiments/gama_dolphin_behaviour_v1/SPRINT_STATUS.json) and [MAR's final Gate D acceptance](../../experiments/gama_dolphin_behaviour_v1/M6_GATE_D_ACCEPTANCE.md). The reviewed `bottlenose_engineering_demo_v1` was accepted on 5 November 2026 for bounded engineering/visual use. Its biological support stayed provisional; it granted no optical or research-capture approval.
- [Accepted demonstration capture limits](../../experiments/gama_dolphin_behaviour_v1/M5_INTEGRATED_DEMONSTRATION.md) and [reproduction/rollback procedure](../../experiments/gama_dolphin_behaviour_v1/M5_REPRODUCTION_AND_ROLLBACK.md). Retained evidence uses native HDR/EXR and fixed derived displays at 512 × 384, with a frozen ocean for that campaign. It does not qualify native LDR or a calibrated physical camera.
- [Ocean-material closeout and open M4 scope](../../experiments/ocean_material_v1/OCEAN_MATERIAL_SPRINT_CLOSEOUT.md) and [engineering preset capture settings](../../experiments/ocean_material_v1/presets/engineering_v1/capture_settings.json). Preserve accepted M5/M6 evidence and the unresolved inside-camera issue.
- [Historical GAMA capture protocol](../../integrations/gama/DATASET_CAPTURE_V2.md). Its owned porpoise labels were direct amodal evaluated-mesh projections, with rendered visibility recorded as unknown. Do not reinterpret or relabel those historical outputs as dolphin visible masks.
- [Capture projection implementation](../../source/extensions/cris.madil.render_service/cris/madil/render_service/capture_projection.py). It distinguishes actual capture-camera matrices from UI projection matrices. Reuse the existing checks where applicable.

Prior acceptance is input evidence, not acceptance of the new annotation mechanism. Audit the actual running configuration instead of restoring an old checkpoint over newer user work.

### 1.2 In scope

1. One explicitly identified animal instance and its render-purpose meshes, with stable ownership and provenance.
2. Camera/product verification, image-coordinate conventions, evaluated-pose geometry and direct geometric boxes.
3. Native NVIDIA instance/semantic annotation capability, where supported by the installed runtime, with dry-scene controls before water tests.
4. Above-water observation of fully exposed, surface-intersecting and fully submerged target geometry; controlled flat and frozen-wave comparisons.
5. A versioned capture bundle, synchronous state evaluation, save/reload, capture-order checks and finite resource measurements.
6. Failure evidence, restoration, a human review packet and a precise decision about permitted next use.

### 1.3 Out of scope

Do not change GAMA behaviour, dolphin locomotion, skeletal cycle, skinning, mesh, material, scale calibration or biological assumptions. Do not add species, pods or a new animation system. Do not refactor the wave sampler or animal controllers, add another ocean model, or patch water/renderer dependencies to make a label pass.

Do not redesign Sony/HiDef camera models, qualify native full-resolution sensor output, invent optical distortion calibration, start ML training, generate train/validation/test splits or expand the workload into a statistical wildlife study. Depth maps, optical flow, sonar and underwater cameras are outside the required product set.

Do not overwrite historical images, manifests, approvals, presentations or acceptance packages. Preserve original model sources and licences, including the DigitalLife3D Model 61A CC-BY-NC-4.0 attribution and restrictions. Do not publish or upload new evidence under this specification alone.

### 1.4 Architecture and working rules

Follow applicable `AGENTS.md` instructions. MARLIN remains an Omniverse Kit application with NVIDIA Kit Services HTTP interfaces. Canonical changes belong under `source/apps/` and `source/extensions/`; experiment orchestration and QA can use the established experiment/tools directories. Reuse existing capture, projection, freeze, checkpoint and ownership mechanisms before adding a small missing helper.

Do not inspect, search or edit `_build/`, `extscache/`, caches or bytecode. Resolve runtime capabilities through supported in-process queries and version-compatible official documentation. Do not modify installed SDKs or introduce arbitrary remote execution endpoints. Run syntax checks if Python production source changes and relevant existing regressions for affected contracts.

Use a private, owned test scene/layer or checkpointed transaction. Checkpoint the current scene and record controller histories/settings before any live mutation. Avoid restarting Kit; any required fresh-process test must first preserve newer user work and have a concrete restoration plan. Prior permission for an earlier isolated test is not blanket permission to close current applications.

---

## 2. Capture and annotation contract

M1 must resolve these definitions into a versioned machine-readable contract before Gate A. Preserve old endpoint field meanings; new products require explicit names, versions and provenance.

### 2.1 Distinct label products

| Product | Meaning | Required qualification |
|---|---|---|
| `direct_amodal_geometry_box` | Perspective bounds of the complete evaluated target geometry, ignoring occlusion and refraction; retain raw and image-clipped forms | Camera math, evaluated geometry, clipping and units |
| `native_instance_mask` | Raw integer instance-ID pixels and their native mappings for the exact render product | Installed annotator, identity, synchronisation and dry controls; marine validity assessed separately |
| `native_tight_box` | The installed native tight-box output, with unmodified raw coordinates and mapped target identity | Dry controls and verified coordinate conversion; no automatic equivalence to a refracted silhouette |
| `reviewed_appearance_reference` | Reviewer-marked visible body region or boundary on a fixed derived display, with ambiguous regions recorded | Named human review and declared rules; limited visual reference, not absolute physical truth |

The default required products are the saved HDR/display pair, the direct geometric box, a qualified native instance mask and a tight box derived from that mask. Preserve the mask-derived box under its own name. The separate `native_tight_box` is a compatibility diagnostic: its failure cannot be hidden, but does not invalidate a correctly qualified mask and its derived box. Gate A must name any additional required products. A geometric-only result cannot meet the full visible-annotation objective.

NVIDIA's versioned Replicator documentation describes tight boxes as bounds of visible pixels and instance masks as outputs for semantically labelled entities. These are candidate interfaces, not proof of their installed availability or behaviour through water.[^replicator]

Do not rename a geometric box as a visible box. A projection of a world AABB must be identified separately from a bound computed from evaluated mesh geometry. A union of projected vertices is not an occlusion-aware silhouette. Near-plane-crossing primitives require validated clipping or an explicit unsupported-case result; simply discarding behind-camera vertices is insufficient.

Preserve the native outputs and derive normalized boxes from copies. Test endpoint inclusivity, empty boxes, row/column order and conversion to the declared internal convention. Store numeric ID-to-prim mappings for every capture; native IDs may change after reload, while the owned target identity must still resolve correctly.

### 2.2 Presence, visibility and uncertainty

Keep the following independent:

- **Scene presence:** the owned target geometry exists in the captured scene.
- **Geometric image intersection:** the declared direct projection intersects the camera image/frustum.
- **Native target-labelled pixels:** target pixels reported by the installed annotator, with count and mapping validity.
- **Reviewed body appearance:** visible, ambiguous or not discernible under the declared display/review procedure.
- **Qualification:** passed, failed, unsupported, blocked or not tested for the exact product and condition.

An empty native mask is not proof of physical absence or invisibility. A submerged or out-of-frame animal is not a negative-presence example. Absence controls remove only the owned target from a private copy; verify its geometry and semantics are absent. Other scene objects remain outside the target class scope.

The target appearance class covers directly seen body surfaces, including a transmitted/refracted body image if it is qualified. Reflections, shadows, caustics, wakes and glints are excluded from that class and must be flagged if an annotator includes them. Review ambiguity at water boundaries must remain explicit. Do not infer visible fraction by dividing native mask area by a direct box area.

### 2.3 Coordinates and state ownership

Retain Y-up, heading 0° = +Z and 90° = +X, and the actual stage `metersPerUnit`. Record physical metres and authored scene units. Use the real render-product camera, resolution, crop, pixel aspect, aperture, clipping and view/projection matrices, independently of the GUI window. The default internal image convention is top-left edge origin, pixel centres `(column + 0.5, row + 0.5)` and half-open integer mask boxes; native conventions must be measured and converted explicitly.

Evaluate root transform, skeleton/joints and skin at one authoritative simulation time. Capture waits, annotator stepping, renderer settling and network arrival must not advance animal or ocean state. Record ocean phase and actual deformed points, not just nominal time. There must be one owner per controlled degree of freedom.

For controlled water placements, apply a recorded rigid Y translation to a private frozen animal copy. These are geometric inspection fixtures, not new behavioural trajectories or breathing/surfacing claims. Classify exposure using evaluated render-purpose geometry relative to the actual surface. A root position or body-centre depth alone is insufficient. No mesh deformation, rescaling or pose correction is allowed to satisfy clearance.

### 2.4 Image domain and synchronisation

Start with the existing native `HdrColor`/EXR route and one fixed derived display transform. Record the HDR colour domain and exact display formula/settings; do not normalize each image independently. Native LDR can be investigated only as a separately declared diagnostic, without replacing the supported HDR acceptance path.

RGB/HDR and annotation outputs must identify the same camera, product, state and delivered frame, using supported frame/time metadata where available. If a native API cannot provide a common frame identifier, use a locked immutable scene plus an alternating known-state diagnostic to test stale-frame behaviour, record the weaker guarantee and obtain its explicit disposition at the gate. Never manufacture a frame identifier.

Do not call matching JSON or USD hashes proof of pixel equality. Report scene-state, annotation and RGB repeatability separately. Capture settings include effective renderer mode, exposure, ray budgets, denoising, accumulation/reset procedure and actual completed-frame evidence. A configured sample limit is not an observed accumulated sample count.

---

## 3. Bounded workload and acceptance rules

### 3.1 Proposed capture declaration

All counts describe **capture bundles**: one retained HDR image, its fixed review display, metadata and requested annotation arrays from one declared state. Multiple AOVs are not additional independent samples. Reference calculations and saved snapshots are not new GAMA executions.

| Block | Conditions | Bundles |
|---|---|---:|
| Dry controls, M2 | Eight fixtures × two above-target views | 16 |
| Marine matrix, M3/M5 | Two frozen body poses × three exposure placements × two views × five scene conditions | 60 |
| Matched repeat, M4/M5 | Twelve matrix rows, preselected across both views, poses and all five scene conditions | 12 |
| Fresh-process replay, M4/M5 | The same twelve rows, reopened/reconstructed in a fresh process | 12 |
| Synchronisation sequence, M4 | Eight declared time/state samples × two views | 16 |
| Marine absence controls, M3/M5 | Two representative water conditions × two views | 4 |
| **Planned total** | Unique primary rows plus declared repeat/replay/control work | **120** |

Reserve at most **24 additional bundles** across the entire sprint for baseline/pilot diagnostics, failed attempts and retries: **144 attempted retained bundles maximum**. Every attempt consumes the budget, including aborted attempts after capture starts. Do not silently restart the count. M1 may use up to four of this reserve for baseline confirmation, without adding a new annotation mechanism. Existing accepted captures may instead supply baseline context.

The eight dry fixtures are: a fully visible analytic fiducial, a partly opaque-occluded fiducial, a fully opaque-occluded fiducial, an image-edge-clipped fiducial, a fully out-of-frame target, an absent target, and the existing animal in two frozen body phases. Use simple known geometry to establish reference boundaries; the animal cases extend identity/pose checks without claiming an independently known anatomical outline.

The five marine scene conditions are: no-water reference; smooth flat clear-water diagnostic; flat `engineering_v1` diagnostic; and the existing `engineering_v1` ocean frozen at two distinct declared wave phases. Two poses × three placements × two views produce twelve rows per condition. M3 executes a predeclared sentinel subset of these same sixty rows; successful unchanged rows count toward M5 rather than being recaptured automatically. Failed attempts and replaced declarations remain in the attempt ledger.

Additional rendered fiducial/interface diagnostics consume the 24-bundle reserve. If all required diagnostics cannot fit, amend the declared cap at a review gate before executing more work; do not hide them outside the ledger.

Flat/clear controls are derived diagnostic scene copies with exact differences recorded. Do not alter the accepted preset in place or assume a changed interface geometry preserves its qualification. Keep the chosen animal transform identical across water conditions for each paired row. If a wave phase changes an intended exposure class, report actual surface clearance and fix the declaration before acceptance; do not quietly translate only the difficult member of a pair.

Use **512 × 384** as the initial single-product resolution and one animal. M1 chooses two phases from retained accepted body states, three placement offsets, the two camera poses/intrinsics, two wave phases, sentinel/absence rows and twelve replay rows. Lock these choices with reasons and hashes before acceptance runs. Select distances for resolvable diagnostic edges, not as a claim about real survey detectability. No continuous video, altitude/GSD sweep, random environmental campaign or extra animals are required.

### 3.2 Numerical rules

Gate A must accept an `acceptance_plan.json` with numeric thresholds, reference procedures, exclusion rules and resource limits. Required starting criteria are:

| Check | Initial criterion |
|---|---|
| Saved product | Exact declared width/height, camera identity and output array shapes; finite required HDR/geometry values |
| Camera projection | At most 1 pixel error for independently measured analytic dry fiducial landmarks/edges, with edge convention recorded |
| Dry raster mask | Zero wrong interior pixels outside a declared 1-pixel boundary band on unambiguous analytic opaque fixtures; explicit boundary/IoU measurements also reported |
| Mask-derived box | Exactly encloses the target mask under the internal convention; native tight-box discrepancy at most 1 pixel per edge after audited conversion |
| Empty controls | Zero owned-target-labelled pixels and no nonempty owned-target tight box in absent, fully out-of-frame and fully opaque-occluded dry controls |
| Identity and synchronisation | Zero unexplained target mapping errors, stale-state captures, mixed-time bundles or duplicate controller owners |
| Replay state | Use the accepted baseline tolerances where applicable; freeze exact numeric root/joint/skin/ocean/camera limits and units in M1 |
| Marine alignment | Lock analytic flat-interface landmark limits and the reviewer boundary/uncertainty comparison procedure before the sentinel run; evaluate separately per product and condition |
| Repeat images | Freeze HDR/display error statistics, regions and pass limits in M1; retain actual distributions separately from scene-state equality |

Use independent analytic geometry or an independently checked raster reference for dry fixtures, not only agreement between two native outputs that may share the same error. A deliberately refraction-sensitive oblique fiducial must distinguish direct geometry from transmitted appearance in M3.

Any change to these starting criteria must be justified and versioned at Gate A before candidate acceptance results. An inconclusive calibration permits further bounded diagnostics or a stop, not retroactive tolerance fitting. No required failed row may disappear into a mean score or be reclassified as a negative. Unsupported transparency behaviour remains a failed/unsupported product condition.

### 3.3 Resource bounds

Query current GPU/driver/runtime and available disk space; historical memory observations are not current capacity. Keep existing memory guards enabled and use the stricter of the existing threshold and M1's admitted annotation workload threshold. The last accepted dolphin campaign used a 768 MiB free-memory guard; that floor alone does not establish sufficient headroom for extra annotators.

Allocate one render product at a time, stream evidence to disk and detach/destroy owned annotators/products after use. Native render products can consume substantial GPU memory.[^replicator] M1 must set finite per-capture and per-transaction timeouts, settling limits and a cleanup check. Preserve the current settings on failure; do not reduce a declared product/resolution mid-run and retain its pass claim.

The proposed incremental evidence budget is **5 GiB**, with **10 GiB free disk space** required before a campaign. These are engineering planning limits, not measured output sizes. Estimate from the first bounded captures and confirm at Gate A. If capacity or the attempt budget is insufficient, stop the affected block, retain failures and present the smallest scope decision. Do not clear unrelated caches, delete results, disable guards or restart the machine automatically.

---

## Milestone 1 — Audit capture, camera and annotation capabilities

### Objective

Establish the actual baseline, smallest implementation plan and locked acceptance contract without changing accepted behaviour or animation.

### Required work

1. Read repository instructions and verify the prior acceptance records and selected source/assets/preset hashes. Record current Git commit plus tracked/untracked changes relevant to the experiment, without committing unrelated work.
2. Record the live scene/checkpoint, stopped/running controllers, ownership, camera, ocean/material selection, display/renderer settings and restoration procedure. Inspect the actual world-unit convention and evaluated skin access.
3. Query installed Kit, renderer, USD and annotation capabilities/version through supported runtime APIs. Inspect canonical app/extension declarations. Absence of a direct Replicator dependency is not proof that it cannot be loaded; availability is not proof it has been tested. No dependency installation or upgrade is authorised by this audit.
4. Audit existing capture routes, render-product validation, projection metadata, HDR display and ownership/freeze support. Identify what can be reused and the smallest missing interface. Confirm whether RGB and annotators can use one product/frame.
5. Specify label definitions, class/instance mappings, confidence/uncertainty fields, empty-result handling, coordinate conversions and the rules for target-only removal. Declare schema/version compatibility before proposing an endpoint change.
6. Fix the complete bounded workload, numeric criteria, dry references, marine sentinel/review subset, resource/time limits and relevant regression list. Do not leave tolerances as an unchecked promise to decide during acceptance.
7. Prepare Gate A with source evidence, representative baseline images, missing capabilities, proposed files, expected mutations, rollback and explicit reasons for any scope amendment.

### Deliverables and acceptance

`M1_CAPTURE_ANNOTATION_AUDIT.md`, baseline/dependency manifests, `capture_contract.json`, `acceptance_plan.json`, `capture_declaration.json`, rollback instructions and `reviews/GATE_A_REVIEW.md`.

The audit passes when current capabilities and unknowns are evidenced, required thresholds and references are concrete, prior evidence is preserved and the implementation is bounded. **Stop at Gate A.** A named reviewer must accept this plan before annotation implementation, semantic authoring or new capture-pipeline changes. Preparing this specification has not recorded that acceptance or executed M1.

---

## Milestone 2 — Validate dry-scene geometry and native annotations

### Objective

Prove the camera/identity/occlusion contract with controlled opaque geometry before introducing water.

### Required work

1. Implement only the Gate A changes, preserving existing endpoints and historical field meanings. Use native installed annotation APIs where they satisfy the task; do not build a parallel renderer.
2. Create owned, reconstructible dry fixtures and the two accepted frozen animal phases. Apply temporary instance/semantic labels in a private layer; inspect inheritance across the animal's actual render meshes and exclude helper geometry by recorded purpose.
3. Execute the sixteen dry bundles. Check actual saved-product settings and analytic fiducial projections. Validate native masks and tight boxes against independent dry references, including occlusion and empty outputs.
4. Show that the two selected poses produce evaluated geometry/labels for their different phases. Check cropping, coordinate conversion, identity remapping and unsupported near-plane cases through appropriate geometry tests.
5. Verify temporal locking, invalid/missing product handling, cleanup and rollback. Retain raw arrays and overlays with unmodified HDR images available separately.

### Deliverables and acceptance

`M2_DRY_ANNOTATION_VALIDATION.md`, sixteen capture bundles, reference fixtures/calculations, geometry/identity/occlusion comparisons, regression evidence and `reviews/GATE_B_REVIEW.md`.

All required dry controls must meet the locked criteria. A failed native annotation path is not replaced by a geometric-box fallback under the same name. **Gate B** requires a named review of the dry label semantics and results before claiming marine annotation validation. If native support is unavailable, report the exact blocker and a geometric-only partial result; broader dependency work needs a new scope decision.

---

## Milestone 3 — Qualify labels through the above-water interface

### Objective

Determine which label products describe the transmitted body appearance, and where water causes a semantic or alignment failure.

### Required work

1. First use a flat, clear diagnostic interface and a known submerged fiducial. Record refractive indices, medium geometry, units and camera geometry as engineering inputs. In an oblique view, compare the observed transmitted landmark position with an independent planar-interface prediction. This is a geometric diagnostic, not full seawater qualification.
2. Run the locked marine sentinel rows spanning both views, poses, all five scene conditions and all three exposure placements. The Gate A declaration must identify the rows and their coverage. Verify cameras remain above the actual wave-height envelope with a measured margin.
3. For matched rows retain the same camera, lights, animal/skin state and capture settings, listing only intended water/surface differences. Record signed surface-clearance measurements and actual exposure class for each frozen scene.
4. Compare direct geometric boxes, native masks, native tight boxes and fixed-display appearance separately. Inspect missing transmitted pixels, surface labels replacing animal labels, reflected-body inclusion, glint/shadow contamination and partial-boundary ambiguity.
5. Produce a review subset covering both views and all three placements, including both wave phases and both poses across the set. Provide raw displays without overlays, native overlays, direct projections and reviewer boundary/uncertainty annotations. Do not call a target-removal RGB difference an exact silhouette: removal can also change lighting, reflections and shadows.
6. Record a capability table by product, water condition and view. Assign passed, failed, unsupported or not tested with evidence. Preserve raw outputs when native annotations disagree with image appearance.

### Deliverables and acceptance

`M3_ABOVE_WATER_LABEL_QUALIFICATION.md`, flat-interface prediction and measurements, sentinel/absence evidence, per-condition capability table and `reviews/GATE_C_REVIEW.md`.

**Gate C** requires a named decision about exactly which marine products/conditions can proceed to a claimed validation campaign. Passing dry labels alone cannot pass this gate for through-water labels. An unsupported marine path may be documented and independent state/replay work may continue within Gate A's plan, but the original through-water objective remains partial. A restricted replacement completion scope requires an explicit reviewer decision and versioned amendment; no silent reduction of the definition of done is allowed.

---

## Milestone 4 — Bind capture bundles to frozen state and prove replay

### Objective

Ensure an image and its labels come from the same reproducible state, including articulated geometry and ocean phase.

### Required work

1. Define an immutable bundle schema binding source run/sample, target identity, pose, wave state, camera/product, renderer, annotation outputs and file hashes. Reuse accepted freeze/checkpoint functionality with any necessary small versioned extension.
2. Execute the sixteen-bundle synchronisation sequence using eight declared samples from retained accepted inputs. These are discrete state evaluations, not a newly validated dynamic wave/behaviour simulation. Alternating distinguishable states must expose stale annotations or an accidental clock advance.
3. Capture the twelve declared matrix rows again in a different order, then reopen/reconstruct the same twelve in a fresh process. Count these as the repeat/replay blocks in section 3, not an extra campaign. Preserve one matching primary bundle for each comparison.
4. Compare camera, root/joints, evaluated skin, ocean points/phase, material/settings and semantic target resolution against locked tolerances. Verify the actual saved scenes independently. Distinguish a frozen USD scene from the controller history needed to resume animation.
5. Measure mask/box and HDR/display repeat differences independently. Native numeric ID renumbering may be normalized only through retained valid mappings. Missing frame guarantees, repeated pixels or changed renderer history must be reported.
6. Exercise capture failure, interrupted output and cleanup. Mark incomplete bundles unusable; do not leave them looking accepted or overwrite the failed attempt with a retry.

### Deliverables and acceptance

`M4_CAPTURE_REPLAY_CONTRACT.md`, versioned schema, state index, sixteen synchronisation bundles, twelve repeat and twelve replay bundles, separate state/label/RGB comparisons and restoration evidence.

Every accepted bundle resolves to one verified state and product; stale/mixed-time results are zero; declared replay criteria pass. An exact scene-state match cannot rescue a failed annotation or image-repeat check. Fresh-process evidence requires an actual fresh process, not only reopening a stage in the same process.

---

## Milestone 5 — Execute the bounded validation campaign and restoration

### Objective

Complete the predeclared coverage and measure the practical cost of the supported product set.

### Required work

1. Revalidate source/preset pins and resource admission. Execute remaining rows of the sixty-bundle marine matrix and the four marine absence controls, reusing unchanged accepted sentinel outputs. Resolve the ledger so the planned 120 bundles and reserve are accounted for without double counting.
2. Keep the Gate C product/condition disposition attached to every row. Unsupported native marine labels may be retained as diagnostic evidence, but cannot populate a validated-label export. Any allowed geometric product keeps its direct/amodal designation.
3. Verify complete files, dimensions, masks, mappings, projection/pose provenance and scene/preset dependencies. Inspect all contact sheets and every failed/ambiguous case at native capture resolution. Run only the regressions relevant to actual production changes, including capture/camera, actor ownership and ocean restoration.
4. Record elapsed time, completed frames, configured sampling, GPU usage/free-memory samples, output sizes and cleanup per block. Distinguish sampled observations from exact allocation peaks. Enforce the attempt/time/storage guards and preserve unsuccessful work.
5. Restore the current pre-work scene, original controller activity, water/material selection, camera/product/settings and temporary labels/products. Verify the restoration rather than relying on a successful checkpoint call. Hash-check protected source/assets and prior acceptance packages.

### Deliverables and acceptance

`M5_CAMPAIGN_AND_RESOURCES.md`, final attempt/completeness ledger, coverage/qualification table, captures and contact sheets, resource/failure logs, regressions, preservation and rollback checks.

All required rows are accounted for and pass their declared product-specific criteria, or the precise remaining blocker is reported. No unreviewed resolution change, dropped row, relaxed tolerance or memory guard bypass counts as success. A launch/restart that creates temporary headroom is not a permanent memory fix.

---

## Milestone 6 — Review results and define permitted next use

### Objective

Package a reproducible engineering result with an explicit boundary for future capture work.

### Required work

1. Produce a closeout linking the specification/approved amendments, audit, all milestone results, capability matrix, failures, schema, commands, dependencies, licences and restoration evidence.
2. Prepare Gate D with representative dry, fully exposed, surface-intersecting, submerged and absent scenes from both views. Show RGB/HDR displays with and without each overlay, uncertainty marks, flat-interface diagnostics and repeat/reload differences.
3. Obtain a **new named human review** of this exact package. Ask separately about engineering correctness, usefulness of label/appearance alignment and permitted next use. Earlier MAR reviews do not approve these new outputs automatically.
4. Record one explicit disposition: full declared engineering validation passed; partial result with named blockers; or an explicitly accepted restricted scope tied to a versioned amendment. State separately that biological, calibrated optical, real-survey and research-dataset approval have not been established.
5. Supply a manifest-based verification/reconstruction procedure and a clear next-step recommendation. Keep actual evidence recoverable in the established artifact store; hashes alone do not replace the files. Do not create a production dataset or start training after review without a separate instruction.

### Deliverables and acceptance

`ABOVE_WATER_ANNOTATION_SPRINT_CLOSEOUT.md`, `SPRINT_STATUS.json`, final manifest, reproduction/rollback guide, `reviews/GATE_D_REVIEW.md` and the actual subsequent named acceptance record if supplied.

The reviewer must see every remaining limitation and the exact allowed product/conditions. **Stop after closeout and report.** Ocean-material M4 remains a separate open capability unless its own evidence and review explicitly close it.

---

## 4. Evidence organisation

Use new directories; do not repurpose accepted experiment identities:

```text
experiments/above_water_annotation_v1/
    baseline/
    contracts/
    declarations/
    fixtures/
    qa/
    reports/
    reviews/
    manifest.json
    SPRINT_STATUS.json
    ABOVE_WATER_ANNOTATION_SPRINT_CLOSEOUT.md

artifacts/above_water_annotation_v1/
    <versioned_run_id>/
        <bundle_id>/
            scene.usdc
            state.json
            capture.json
            annotation.json
            hdr.exr
            hdr.npz
            review.png
            native_annotations/
```

Names describe the intended structure, not files already generated or capabilities already available. Store reusable scenes/dependencies once where appropriate and reference their hashes from bundles. Preserve new failed runs under distinct identities.

Every bundle must identify: contract/declaration version; source commit and relevant diff/source hashes; asset/licence and water preset pins; source sample/time/pose and any fixture offset; evaluated target geometry; stage units; ocean phase/points; actual camera/product/matrices; renderer and effective settings; HDR/display processing; native annotation type/version/mappings; raw and converted boxes; presence and uncertainty; qualification status; resource observations; output paths/hashes and attempt/comparison family.

No train/test split is created here. Related water, view, pose, repeat and removal variants must retain a common fixture/source-family key so a future study can prevent leakage if it is separately authorised.

## 5. Human gates and overall definition of done

| Gate | After | Required decision |
|---|---|---|
| A | M1 | Accept audit, precise label/capture contract, implementation scope, thresholds and workload before implementation |
| B | M2 | Accept dry-camera/geometry/identity/occlusion evidence and native annotation semantics |
| C | M3 | Accept or reject each marine product/condition and any explicit scope amendment before validation claims |
| D | M6 | Accept the exact final evidence package and permitted next use, with remaining limitations retained |

Review records must contain a real named decision, date, scope, reviewed manifest/version and limitations. Do not pre-fill MAR's acceptance. When a gate is pending, stop dependent implementation and present a concrete review packet; continue only independent work already within an accepted plan.

Full completion of the original objective requires:

1. The installed capture/annotation capability, camera conventions and accepted baseline are verified and preserved.
2. Dry camera, geometry, identity, occlusion and empty-result controls pass locked criteria.
3. The declared marine visible-annotation products pass the above-water transmitted-appearance tests for the required view/exposure/water matrix. If none can be qualified, this objective is partial even when geometric boxes work.
4. Image, annotations, evaluated skin and ocean state are synchronised, saved and replayed within separately assessed state/label/RGB criteria.
5. The finite campaign, resource measurements, regressions, cleanup and restoration are complete and accounted for.
6. Provenance, dependencies, licences, evidence and commands permit verification without modifying prior acceptance packages.
7. A new named reviewer accepts the exact declared engineering result and its next-use boundary.

Code existence, a convincing overlay, a native annotator's name or a matching state hash alone does not satisfy these requirements. Report implemented, executed, passed, failed, unsupported, blocked and provisional outcomes distinctly.

## 6. Documentation reference and evidence boundary

The official reference below was checked on 9 November 2026. It describes Replicator 1.13.30, not necessarily the local version. M1 must establish the installed interface and pin the appropriate documentation. The workflow, workload and tolerances in this document are proposed engineering requirements; they are not NVIDIA guarantees or measured results.

[^replicator]: NVIDIA, [Omni Replicator 1.13.30 Python API](https://docs.omniverse.nvidia.com/kit/docs/omni_replicator/1.13.30/source/extensions/omni.replicator.core/docs/API.html), especially [tight 2D boxes](https://docs.omniverse.nvidia.com/kit/docs/omni_replicator/1.13.30/source/extensions/omni.replicator.core/docs/API.html#bounding-box-2d-tight), [instance segmentation](https://docs.omniverse.nvidia.com/kit/docs/omni_replicator/1.13.30/source/extensions/omni.replicator.core/docs/API.html#instance-segmentation-fast) and `create.render_product`. Native outputs require local validation, particularly with transparent/refractive geometry.
