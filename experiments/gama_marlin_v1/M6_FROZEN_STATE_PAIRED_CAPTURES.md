# Milestone 6 — Freeze one GAMA state across all five GSD captures

Sprint: **GAMA–MARLIN Behavioural Integration and Validation**  
Engineering acceptance: **passed**  
Biological suitability: **provisional; engineering use only**, carrying forward MAR's M5 review. No biological approval was inferred.

One actual, predeclared GAMA state produced ten accepted 1024 × 768 captures: the five GSD conditions in ascending order, then in reverse order with an artificial two-second delay before each capture. All ten images shared one resolved biological/environmental scene identity. All **101 state checks** passed, including checks around delays, warmup and individual capture probes. The original live scene was restored, ownership was released, and all eleven demonstration animals and the ocean resumed.

The formal evidence inventory is [milestone_6_manifest.json](qa/milestone_6_manifest.json). The accepted live result is [m6_live_03/results.json](qa/m6_live_03/results.json), with its complete [paired manifest](qa/m6_live_03/group/manifest.json), [resolved identity](qa/m6_live_03/group/resolved_state.json) and [frozen USD](qa/m6_live_03/group/source_scene.usdc).

## Declared state and workload

The client reparsed the retained raw GAMA XML and checked it against the sealed M5 trajectory and execution hashes. It replayed steps 0 through 8 exactly once, then captured step 8. No new model execution, synthetic substitute state or selection based on image appearance was used.

| Field | Captured value |
| --- | --- |
| Source run | `m5_positive_seed_184729_a` |
| Seed | 184729 |
| Step / simulation time | 8 / 4 seconds |
| Behaviour | `shallow_swim` |
| Horizontal X/Z | −5.229630306507289 / 6.054004200300862 m |
| Mean-sea-level depth / root Y | 0.5 m / −0.5 m |
| Heading / speed | 49.17856275642697° / 0.5 m/s |
| Pose mapping / animation phase | `static_pose_proxy_v1` / not applicable to the static pose |
| First order | 0.5, 1, 2, 3, 4 cm/px |
| Second order | 4, 3, 2, 1, 0.5 cm/px |
| Artificial delay | 2 seconds before every second-order capture; none added to the first order |

The [declaration](qa/m6_live_03/declaration.json) was written before images were inspected. Both unsuccessful earlier attempts retained this same selection rule. The GAMA clock, Kit timeline and procedural ocean clock were recorded separately; their values were not claimed to be synchronized.

## Snapshot and camera separation

The new bounded Kit Services endpoint, `POST /integration/gama/v2/actor/paired-capture`, reuses the existing actor ownership, capture lock, controller gate, USD freezing helpers, camera construction and generic viewport renderer. Its HTTP payload accepts only an ownership token, one to three complete five-GSD orders and a delay from zero to five seconds. [API and operating details](../../integrations/gama/PAIRED_CAPTURE_V2.md) describe the transaction.

The controller gate and timeline were held while the complete composed scene was flattened and animated attributes were evaluated at the source time. Current procedural ocean and animal mesh geometry, materials and lighting were retained. Three sampled attributes were resolved; **zero time samples remained**. One private frozen stage supplied the entire sequence, while a strong reference retained the original live stage for restoration.

The scene-state hash binds the GAMA state, composed animal matrix, static pose mapping, non-camera USD content, source clocks, renderer settings and dependency records. Camera subtrees and `/Render` are excluded; each camera condition has a separate hash and recorded render-product/projection metadata. Local dependencies were rehashed throughout capture.

```text
resolved_scene_state_hash:
631a6a4615ec8cf267d5688e294e3044107dcf6004d97e0e08567eb4377a7c8b
```

Camera X/Z was chosen once from the resolved animal root. Only camera Y varied. The animal was never translated between conditions. Camera optics followed the validated Pilot generic route: 50 mm focal length, 5 µm pixel pitch, ideal nadir perspective, centimetre stage and 1024 × 768 output.

| Nominal GSD (cm/px) | Separation above root plane (m) | Camera Y (m) | Reference footprint W × H (m) |
| --- | --- | --- | --- |
| 0.5 | 50 | 49.5 | 5.12 × 3.84 |
| 1 | 100 | 99.5 | 10.24 × 7.68 |
| 2 | 200 | 199.5 | 20.48 × 15.36 |
| 3 | 300 | 299.5 | 30.72 × 23.04 |
| 4 | 400 | 399.5 | 40.96 × 30.72 |

Actual composed matrices, apertures, focal length, viewport output and render-product camera were checked against these conditions. Float32 aperture rounding produced measured values within the declared tolerance. The sweep changed both camera height and footprint, as in Pilot v1.

The frozen **current presentation environment** was used. This preserved pairing but did not reproduce Pilot's flat-water, diffuse-light environment. No M4 diagnostic underwater light or follow camera was added. Reference-plane GSD was checked geometrically; underwater refraction and anatomical-surface GSD remain uncalibrated.

## Captures, settling and RGB comparison

Every condition retained three fresh PNG probes and one accepted image: **30 probes and 10 accepted PNGs** in total. Every probe used a unique output path and was fully decoded before acceptance. Consecutive-frame full-image mean absolute RGB changes were below the declared threshold of one raw 8-bit channel unit, equivalent to 1/255 after normalization. This was a settling check, with no RTX sample-count certification.

The client independently decoded and hashed every retained probe, recomputed its settling metric and checked all accepted images were 1024 × 768. [Pixel repeat analysis](qa/m6_pixel_repeat_analysis.json) reports file-byte equality, decoded RGB equality and continuous pixel differences for each same-GSD pair. Pixel identity was evaluated separately from the scene hash and was not required or inferred by the pairing acceptance criterion.

None of the five same-GSD pairs was byte-identical or decoded-RGB identical. Their corresponding camera and scene hashes matched. The measured differences below describe encoded 8-bit RGB; no new pixel acceptance threshold or colorimetric calibration was applied.

| GSD (cm/px) | Mean absolute RGB difference (0–255) | Pixels with any changed RGB channel (%) |
| --- | --- | --- |
| 0.5 | 0.037954 | 9.2960 |
| 1 | 0.023142 | 6.1840 |
| 2 | 0.086035 | 22.1836 |
| 3 | 0.113766 | 25.0554 |
| 4 | 0.026298 | 5.1422 |

The [contact sheet](qa/m6_paired_contact_sheet.png) shows all ten full frames without cropping. It is a viewing derivative; the original captures are preserved unchanged. Visual inspection found the central porpoise silhouette in every frame, with little internal anatomical detail. Targets were small at 3–4 cm/px; other demonstration animals entered the wider footprints, including a partial animal at the upper image edge. These features were retained rather than removed to improve the result.

## Verification and restoration

The [initial offline batch](qa/m6_01_offline_results.json) passed **124 tests** covering the new resolved-state and transaction logic, existing v2 and legacy actor/exchange routes, GAMA export, and capture projection. After the live fixes, the transaction suite passed [12 clock-settling tests](qa/m6_02_targeted_results.json), then [13 tests including fresh-output regression](qa/m6_03_targeted_results.json). These were targeted reruns, not additional independent biological evidence or a claim that the full batch was rerun after every change.

The [independent retained-scene check](qa/m6_scene_validation_03.json) reopened the saved USD in a separate Blender USD Python process without attaching it to Kit. Using the versioned scene-identity definition, it reproduced the entire resolved identity and hash exactly. It reconstructed all ten cameras, matched each full camera-condition record and hash, and found a maximum projection-matrix difference of **0**. Only camera Y varied; every reconstructed condition preserved physical scene identity. All **34 local dependencies** matched before and after this check, and the private source stayed unchanged. One runtime shader dependency was recorded but its bytes were not inspected. Blender's unknown UI-metadata warnings were retained in the [execution log](qa/m6_scene_validation_03.log); they did not change the recomputed identity.

All transaction restoration checks passed: original stage, camera, resolution, fill mode, selection, renderer/display settings, timeline time/play state, original non-camera source content, controller gate and capture lock. The original ocean clock and owned animal pose were checked before controllers resumed. After release, the client verified all eleven original animals advanced, the ocean advanced, original controller/ocean settings and stable scene attributes matched, the original layer stack was restored, and the private porpoise root was absent. No restart or scene reconstruction was needed.

The [preservation check](qa/m6_final_preservation.json) confirmed all 175 M5 sealed outputs remained unchanged, together with 914 protected Pilot files, the baseline archive, both trained checkpoint copies, all 27 M3 outputs, and the protected M2/M4 outputs. The only existing source file changed for M6 was the bridge's `extension.py`, adding the bounded endpoint; its earlier sealed hashes were retained as historical evidence. Earlier intentional bridge deltas remained explicitly declared. Python syntax and `git diff --check` passed.

## Retained unsuccessful attempts

| Attempt | Outcome | Corrective change |
| --- | --- | --- |
| [m6_live_01](qa/m6_live_01/results.json) | Initial strict clock check failed after attaching the frozen stage; zero captures accepted. | Allowed three gated Kit updates to commit timeline setters, then retained exact clock checks. |
| [m6_live_02](qa/m6_live_02/results.json) | Clock checks passed, but the shared temporary capture path still contained a prior 1280 × 720 image; zero captures accepted. | Used unique per-probe paths and waited for each complete PNG to decode through the same generic viewport backend. |
| [m6_live_03](qa/m6_live_03/results.json) | Ten captures, 101 state checks, independent retained-scene verification and restoration passed. | Accepted engineering evidence. |

Both failures restored the scene successfully, required no recovery, released ownership, resumed the ocean and demonstration animals, and preserved all M5 outputs. Their manifests, frozen USDs, available images and client results remain retained. No failed image was included among accepted captures. The first failure did not retain actual-versus-expected clock values, so its immediate timeline-setter cause remains a diagnosis supported by the subsequent strict-check success, rather than a separately measured clock trace.

NVIDIA documents the [viewport file-capture API](https://docs.omniverse.nvidia.com/kit/docs/omni.kit.viewport.utility/latest/omni.kit.viewport.utility/omni.kit.viewport.utility.capture_viewport_to_file.html) and [asynchronous viewport capture](https://docs.omniverse.nvidia.com/kit/docs/omni.kit.viewport.docs/latest/viewport_api.html). The file-readiness fix was driven by the retained observations on this host.

## Completion boundary

M6 demonstrated one resolved snapshot preserved across all five GSD conditions, changed capture order and artificial delays, with separate camera and RGB evidence. This is engineering acceptance for the provisional static-pose model in the current environment. It does not establish biological realism, underwater optical accuracy, RTX bitwise reproducibility, or a statistically representative wildlife dataset. Milestone 7 and its capture/annotation test set were not started.
