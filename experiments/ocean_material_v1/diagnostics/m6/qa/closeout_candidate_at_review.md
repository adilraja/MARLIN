# MARLIN ocean material sprint — closeout candidate

Updated **3 November 2026**. Sprint: **MARLIN — Ocean Material and Underwater Appearance**.

**The sprint remains open.** M6's implementation, paired captures, fresh-process persistence, rollback and regressions have passed the declared technical checks. Named human review by **MAR** is pending. M4's inside-water-camera attenuation defect still reproduced on driver 595.99.02; the new driver resolved the NVML mismatch but did not resolve this renderer capability.

## Milestone status

| Work | Current outcome |
| --- | --- |
| M1–M3 | Earlier acceptance evidence remained sealed and unchanged |
| M4 | Above-water integration supported; inside-camera attenuation remained unqualified, including the new-driver retest |
| M5 | Bounded PathTracing HDR/EXR plus fixed-display repeat/reload checks completed; useful native LDR PNG remained unqualified |
| M6 | Versioned preset, animal comparisons, fresh-process reload, rollback and regressions ready; new named human review pending |

## New-driver reproduction

The six initial frozen standalone scenes were repeated with the same private Kit 110.2 build, source scene hashes, product controls and optical analysis. Driver was 595.99.02, kernel 7.0.0-42; the older tests used driver 595.91.07 and an earlier kernel. This is a persistence check on the current host configuration, not an isolated causal claim about one changed component.

The 1 m above-water absorption/clear RGB ratio was **[0.600536, 0.800048, 0.898451]**, consistent with [0.6,0.8,0.9] within the existing 0.03 absolute tolerance. The inside-camera 0.5 m ratio remained **[1,1,1]**, instead of [0.774597,0.894427,0.948683]. Clear, absorbing and engineering inside cases all measured centre RGB [11336,11336,11336]. Above-water positive controls passed; inside checks failed. A local [NVIDIA addendum](diagnostics/m4_driver_5959902/NVIDIA_SUPPORT_ADDENDUM.md) was prepared but not posted.

![Driver retest](diagnostics/m6/figures/driver_retest.png)

The native reproduction retained its original 64-frame/45-second frame wait and first-case/subsequent 240/90-second coroutine bounds. Only its optional direct vendor MDL hash was skipped, to honour repository restrictions on generated caches; rendering was unchanged. The owned informational IOMMU notice was dismissed without changing host settings. Six cases completed; sampled peak GPU use was 2,206 MiB, minimum free 3,592 MiB. Total process wall time 218.04 s included startup and notice acknowledgement.

## Versioned preset and unchanged animal

The package is [presets/engineering_v1](presets/engineering_v1/README.md): byte-identical parameter JSON, exported MDL material layer, closed-medium requirements, effective capture settings, saved selected scene, local dependency hashes, source snapshots and original animal attribution/licence. It uses native `OmniSurface.mdl`; the water material has no texture assets. Native vendor/cache files were not read or copied. The animal's two local texture files, original USD and licence were hashed and preserved.

The asset was the existing **Model 61A - Bottlenose Dolphin** by DigitalLife3D. Its measured render-purpose world bounds were approximately **0.827 × 0.837 × 2.586 m**, an asset measurement rather than a biological-size claim. Root scale remained [100,100,100], rotation [0,0,0] for this existing asset, and mesh/material/anatomical pose were unchanged. Only temporary Y translations changed inspection placement; live standard placement was restored afterward.

Within every old/new pair, animal transforms and identity, camera matrices, effective camera/product/global controls, lights and original top-ocean points matched. Changed scene prims were confined to the water and its engineering material. The new water required the already-tested closed side/bottom boundary: 17,154 vertices / 17,408 quads versus the original 16,641 / 16,384 top grid, a 20 m bottom depth and horizontal derivative bound 0.385612. Wave equations, shared sampler, coordinate conventions and animal controllers were not rewritten.

The camera remained above water. Geometric framing selected height **8.551 m**, 35 mm focal length, 20.48 × 15.36 mm aperture, 40-degree downward pitch and 512 × 384 square pixels. Near/far were 0.01 / **34.206 m**, recorded as an M6-specific camera setting. The pinhole builder's theoretical target metadata was not represented as additional physical targets or new raster-calibration evidence.

| Engineering placement | Asset world Y bounds | Fixed-log box-region MAD (8-bit) | Pair invariants |
| --- | --- | ---: | --- |
| above | 0.646 to 1.483 m | 57.66 | Passed |
| intersecting | -0.367 to 0.471 m | 59.02 | Passed |
| below | -1.483 to -0.646 m | 62.53 | Passed |

Those colour differences include changed water/background/lighting interaction; they are neither an animal-quality score nor a refraction/visible-mask error. Direct projected geometric boxes remained identical within pairs. Refracted/distorted appearance and surface reflection/shadow features can differ from those direct boxes. Existing annotation definitions and historical labels were unchanged; no new visible-mask claim was made.

![Material comparison](diagnostics/m6/figures/material_comparison.png)

## Saved-image, reload, rollback and animation evidence

M6 retained native HDR NPZ/EXR and native PNGs through the existing Kit viewport SDK. Primary quantitative images used the unchanged M5 mapping `round(255*clip(HDR/12000,0,1)**(1/2.2))`; review figures additionally used a single fixed log1p mapping. There was no per-image normalization or renderer exposure fitting. PathTracing configured 512 samples/pixel and 1/iteration, but completed hardware sample counts were not measured. Each M6 image waited 64 rendered frames within 30 s, with a 60 s image bound and 768 MiB free preflight. Initial three-frame/90 s readiness was separate.

All six paired captures completed in the first process. It exited while attaching the saved scene for in-process reload; no Python failure record or native exit code was retained, and bounded kernel/application diagnostics did not establish a cause. The sampled peak was 3,040 MiB used with at least 2,758 MiB free, which does not establish memory exhaustion. The failed switch was preserved and was not called a pass.

The milestone-permitted fresh-process alternative loaded the exact saved selected scene as its first marine stage. The animal, all evaluated non-render scene hashes, material binding, camera matrices, global settings and effective RGB/HDR controls matched. The only raw product inventory difference was the process/view `viewPickingId`; both values were retained and this picking identity alone was reported separately. Picking/object-ID or mask equality was not claimed; all other controls used the existing strict comparator. See [comparison scope](diagnostics/m6/qa/CONTROL_COMPARISON_SCOPE.md).

| Check | Full-image MAD | Full p99 | ROI MAD | ROI p99 | Maximum | Result |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Fresh-process reload | 0.04570 | 1 | 0.11047 | 2 | 26 | Passed |
| Original-material rollback | 0.00738 | 0 | 0.02173 | 1 | 8 | Passed |

Values are 8-bit primary-display units. The unchanged gate was MAD ≤ 1 and p99 ≤ 8 in full RGB and central ROI; maximum was reported rather than gated. PNG/HDR dimensions and all eight EXR headers were checked independently. The fresh process peaked at 2,528 MiB used / 3,270 MiB minimum free. Its saved results survived a graceful SIGTERM after posted quit did not exit promptly; the process returned 0.

The existing runtime regression passed five wave phases and two real controller trajectories, including boundary and dive/surface paths. A further current-driver live capture recorded **10 actual ocean updates**, advancing phase while retaining engineering binding and boundary updates; all cleanup checks passed. That existing M4 diagnostic kept its separate 90-second transaction bound. Seven memory observations around that live capture peaked at 3,073 MiB used / 2,725 MiB minimum free. Final normal 1280 × 720 preview observation was **NVIDIA RTX A2000, 6138, 3727, 2071, 595.99.02**; this later single observation lies outside the smaller diagnostic capture windows. Sampled peaks are not exact allocation peaks or permanent memory fixes.

## Regressions, restoration and preservation

Existing offline checks covered camera math/evidence, projection/calibration, HiDef parameters, renderer settings/snapshots, cetacean motion, movement, baked animation, gallery helpers, ocean enclosure, water material, underwater cue and environment. **59 tests passed and 2 were skipped** because pxr was unavailable in the external interpreter. Actual Kit geometry/controller/capture/reload/rollback tests ran separately. One initial underwater-cue test-discovery import failure was retained, then passed with the canonical module path; production source was not changed to fix the invocation.

MARLIN was reopened from the pre-work checkpoint and its recorded standard ocean/chase controllers reconstructed, with swimming stopped and the original material selected. Final camera, resolution, fill mode, renderer settings and display options matched the pre-work checkpoint. The final checkpoint was **checkpoint_o6mbuodo**. Phase and render history were reset across process lifecycles, not preserved. All **113 canonical source files**, the M5 package and the earlier M1–M4 evidence remained unchanged. Live process logs are excluded from immutable hashes; sealed snapshots are retained.

## Reproduction, rollback and review gate

Exact launch commands, output paths, source hashes, failures and native controls are retained under `diagnostics/m4_driver_5959902/` and `diagnostics/m6/qa/`. The [preset README](presets/engineering_v1/README.md) gives existing-service apply/rollback commands, a fresh-process capture command with an unused output identifier and the tested deterministic display converter. The copied material/source snapshots are evidence and recovery inputs, not edits to generated runtime files or an alternative service architecture.

The [review packet](diagnostics/m6/REVIEW_PACKET.md) is ready for **MAR**. The current sprint explicitly requires a named human review of this demonstrated material change; previous sprint approval is not reused. Human acceptance is still pending in `diagnostics/m6/review_state.json`. Technical readiness does not close M4, qualify native LDR output or establish real-seawater, biological or wildlife-survey validity. No dataset or ML training was started. Stop here pending human review and the unresolved NVIDIA capability.

Dolphin attribution: this work uses "Model 61A - Bottlenose Dolphin" by DigitalLife3D, CC-BY-NC-4.0; original licence and source links remain associated with the asset and preset package.
