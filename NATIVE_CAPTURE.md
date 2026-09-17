# Native HiDef tiled capture — 2026-09-15

**Milestone status: incomplete. Native metric-target rendering passed; native
marine rendering remains diagnostic because tile-overlap checks failed.**

## Narrow SDK stability milestone passed — 2026-09-17

The full native-image milestone remains incomplete, but the scoped single-tile
stability and subsequent two-neighbour test now pass. No camera geometry,
animal calibration, water parameters, or overlap thresholds were tuned.

| Diagnostic | Artifact | Result |
| --- | --- | --- |
| One tile, 16 requested samples | `oblique_7n98eq53` | Completed; 854 × 306; all restoration checks true |
| Three repeats, 16 requested samples | `oblique_zg4w0obv` | All dimensions/projections passed; worst repeat mean 0.298009/255 |
| Three repeats, 1024 requested samples | `oblique_5ttdidmz` | All dimensions/projections passed; worst repeat mean 0.056756/255 |
| Tiles 3,4,3,4, 1024 requested samples | `oblique_0pt9zx9w` | All four cross-tile overlap means passed; worst 1.652302/255 against unchanged ≤2/255 |

Every saved PNG was 854 × 306. Independent reprojection of a 5 × 5 ray grid
per tile gave maximum error 0.000012701 pixels. All output hashes and all eight
recorded restoration checks passed. Temporary product removal is asserted after
each capture; successful consecutive captures also exercise session-layer cleanup.
The pair's individual overlap-pixel maximum reached 14/255: the acceptance
criterion is the documented mean absolute error, not exact pixel equality.

Reports: each repeat/pair artifact contains `tile_geometry_validation.json`;
`artifacts/hidef_marine/sdk_pair_comparison.json` independently recomputes pixel
differences. `tools/verify_tile_diagnostic.py` checks dimensions, hashes,
restoration and ray matrices without pretending a partial image is a full image.
CPU checks: 6 native-tile, 8 shared HiDef, 6 projection and 4 analysis tests passed.

Remaining limitations: SDK sample budgets are requested values, not independent
GPU sample telemetry; this is not a full-image/raster alignment certificate.
All 64 tiles and their full overlap set still need validation. The SDK path is
still diagnostic-only; the existing full native capture path is not silently
replaced by it. Earlier failed artifacts below remain valid historical evidence.

## Two-tile SDK investigation — 2026-09-16

### Resolution reset traced

Runtime setter tracing in `oblique_u5wkwtbf/sample_00_tile_03.trace.json`
identified the 1280 × 720 assignment: SDK `_prepare_viewport` changed the
persistent per-viewport `fillViewport` preference, triggering the viewport
settings menu's `fill_viewport` / resolution model callbacks. Setting only
`ViewportAPI.fill_frame=False` had left that preference unsynchronized.
The product initially stayed 854 × 306, then followed the UI reset on the next
update. The SDK did not switch render mode in this trace.

The fix sets and settles the per-viewport preference before binding the tile,
then restores its previous value. Temporary setter instrumentation was removed.
Explicit product geometry is now validated separately from the UI buffer.
The first full capture after this correction (`oblique_5eivh5qa`) maintained
dimensions but exposed an AOV naming mismatch (`Color` versus `LdrColor`), now
corrected. The following run (`oblique_xjqnx3f6`) exposed session-layer render
settings surviving between repeats; cleanup now removes the owned subtree from
each local layer, not only the current edit target. Repeated-capture validation
of that cleanup was interrupted and must not be claimed complete yet.

The resumed attempt `oblique_ykvkkck0` started in a fresh Kit session on
2026-09-16. Startup shader compilation delayed checkpoint restoration; the
restore HTTP client timed out but Kit subsequently began the diagnostic.
Kit then stopped responding during the async-to-synchronous capture transition.
No PNG or completion report was produced, and a separate read-only API request
also timed out. GPU headroom was 3396 MiB, so this was not a preflight-memory
rejection. The in-process timeout did not complete while Kit was unresponsive.
This run does not validate repeated captures or cleanup; no overlap test was
started. The recoverable presentation checkpoint remains `checkpoint_r7rmq2ii`.

Added the experimental `sdk_pair` diagnostic: tiles 3, 4, 3, 4 from the
unchanged frozen native snapshot, with an owned render product, exact dimension
checks throughout capture, timeout/cancellation, and temporary-product removal.
It does not assemble or certify a full image. The SDK must be explicitly enabled
through the bounded capability endpoint (see RUN_COMMANDS.md).

Kit downloaded and enabled NVIDIA `omni.kit.capture.viewport` 2.10.2 and
`omni.graph.examples.cpp` 2.11.0. Source inspection of this installed SDK showed
that its synchronized capture lifecycle increments an iteration-based sample
counter. `done` therefore is **not independent hardware sample-count evidence**;
the diagnostic explicitly records `actual_gpu_samples_verified=false`.

Live attempts were rejected because the requested 854 × 306 product became
1280 × 720 during capture. Settling the initial product binding did not prevent
the reset. A subsequent change to complete the PathTracing renderer transition
before SDK capture remains **GPU-unverified**: the next attempt was blocked at
564 MiB free, below the unchanged 768 MiB preflight guard. No SDK overlap result
was accepted. Resource reclamation is not proven merely by removing USD prims.

Next: on a fresh, recoverably checkpointed Kit session, verify this transition
ordering and GPU allocation cleanup before expanding beyond the two tiles.
Do not claim this smaller milestone, measured SPP completion, or native marine
capture certification yet. Ocean animation and all 11 gallery swimmers were
restarted after extension reloads; source camera geometry was not tuned.

## Method and safety

### Checkpointed renderer-transition retest — 2026-09-16

Saved and SHA-256 verified `checkpoint_v7ranvgj` before gracefully stopping
Kit. Its scene hash is
`828bb5ac2b7225276732bbe58651dbe191c69f176d3ea306d8a861b63160bd2b`.
Free GPU memory was 592 MiB before shutdown, 2889 MiB with Kit closed,
1829 MiB immediately after restoration, and 1296 MiB at capture preflight
after the restored scene had loaded. Total GPU memory was 6138 MiB.

Ran `sdk_pair` with the renderer transition performed before product binding.
Artifact `artifacts/hidef_marine/oblique_nqd5r3za` preserved the exact source
scene hash `513542ff86961ae6b4f5d59ebc195683e9ed377e745426210838257ac3cb38a8`.
Its first tile failed after 1.41 seconds: requested 854 × 306, observed
1280 × 720. See `sample_00_tile_03.failure.json`. No tile or overlap pass was
accepted, and actual GPU sample completion remains unverified.

This fresh-session failure demonstrates that the renderer-transition correction
is insufficient; stale allocations from the prior session alone cannot explain
the dimension reset. The checked new-session log contained no GPU out-of-memory
messages. The checkpoint was explicitly restored again, its gallery camera
selected, and a visible ocean/animal viewport capture inspected. Final free GPU
memory was 1143 MiB. The restored checkpoint is a frozen visual state: animation
controllers were deliberately not started on checkpointed deformed mesh points.
No camera geometry, assets, or renderer source was changed for this retest.

The RTX A2000 has 6138 MiB total memory; initial headroom was only 1112 MiB.
A monolithic 6576 × 2192 RTX allocation was not attempted. An initial larger-tile
attempt stopped after one tile when free memory reached 652 MiB, below the
unchanged 768 MiB guard. Memory recovered after live-stage restoration.

The bounded path now renders **64 fixed-size 854 × 306 tiles**. Each contains
an 822 × 274 native-pixel core and a 16-pixel guard on every side. Outer guards
extend beyond the frame and are discarded. Equal-sized buffers avoid growth
when moving between edge and interior tiles. GPU headroom is checked before
each tile; the existing live-stage restoration and shared capture lock are used.
The whole request has a 600-second timeout. No second RTX renderer is created.

For each tile, USD horizontal/vertical apertures and offsets select a sub-frustum
of the full camera. Focal length and world pose stay fixed. The saved scene
contains the full camera, restored after tile rendering. Core crops are pasted
into the full-resolution image **without resizing or blending**. This is native
sampling, not an enlarged preview. The source stage and animal models are not
edited by capture. Capture PNG writes are awaited before image decoding.

Full-image matrices are stored separately from each tile's actual render-product
matrices. `assembled_image_resolution` is 6576 × 2192;
`actual_viewport_resolution` is the last small render product, not a false claim
that the GPU rendered a full-frame texture. The aggregate `render_product`
record explicitly identifies CPU assembly; concrete products are in tile records.

GSD maps are calculated at the full native dimensions. At roll 7.7675°, width
spacing is 2.230198–2.496944 cm/px, height spacing 2.535429–2.899999 cm/px.
The nominal nadir value is not substituted for these directional oblique values.
The map exporter retains legacy preview wording in its generic sampling note;
the native config, array dimensions and tiled test kind identify these outputs
as native-pixel maps.

## Acceptance checks

- Native core coverage must be exact, once per pixel.
- Tile-camera projection must match full-camera rays within 0.001 px.
- Nine rendered metric targets must pass the existing 2-pixel bounding-box and
  0.95 polygon-IoU thresholds at three contrast thresholds.
- Every overlapping tile pair is compared over duplicate rays. Mean absolute
  RGB difference must be <=2/255 for each overlap, including diagonal overlaps.
  This is an engineering test, not a physical radiometric calibration.
- All live-stage and viewport restoration checks must pass.

Screen-space rendering effects can differ between tiles even with identical
geometry. The overlap check is required, not waived for plausible-looking RGB.
Failure returns `ok:false` with a diagnostic directory, not an accepted dataset.

## Results

Native target capture: `artifacts/hidef_marine/oblique_a3dx2mg2`.
All nine targets passed: maximum bbox error **1.445744 px**, minimum IoU
**0.994747**. All 210 overlaps passed; worst mean difference **1.290365/255**.
Maximum tile reprojection error **0.000012701 px**. Native maps, output hashes
and live viewport restoration passed. This target test used 90+15 settling
frames on the first tile and 30+15 on later tiles.

First native marine capture: `oblique_htk8y1za`. Geometry, native dimensions,
maps, hashes and restoration passed, but **5/210 overlap comparisons failed**;
worst mean error **4.426758/255**, concentrated around large animals. It remains
diagnostic-only. More settling frames are a controlled test of rendering history,
not a relaxation of acceptance limits or a camera-parameter fit.

Replay of that exact frozen scene with 135 settling frames per tile:
`oblique_wfbfsc4p`. Scene hashes matched. Again **5/210 overlaps failed**,
worst mean error **6.910539/255**. Longer settling did not resolve the issue.
This does not establish which rendering effect is responsible; screen-space
denoising/reflections and tile-dependent lighting remain hypotheses to test.
No acceptance threshold was relaxed and neither marine image is certified.
All tile matrices still agree with native rays within 0.000012701 px.

Next investigation should isolate the tile-dependent rendering effect on the
saved failing scene, concentrating on tiles around the large animals, before
attempting another accepted native marine capture. Do not use global image
similarity to hide these localized overlap failures.

The live viewport and its tracked settings were restored after both runs.
Ocean animation and eleven swimmers were checked active; free GPU memory
recovered to 1683 MiB. No Kit restart was required.

The initial two tile geometry/coverage tests, four projection tests and seven shared HiDef
regression tests passed (13 total). Hardware calibration, biological detectability,
native Sony rendering and monolithic native GPU rendering are outside this work.

## Focused diagnosis and replay isolation — 2026-09-15

**Still not an accepted native marine image.** The fixed source remains
`oblique_htk8y1za`, SHA-256
`513542ff86961ae6b4f5d59ebc195683e9ed377e745426210838257ac3cb38a8`.
The diagnostic captures tiles 3, 4, 4, 5, 11, 12 and 13, including an identical
repeat. Comparisons use the same native-pixel regions: larger guards must not
artificially improve a score by including more uniform water pixels.

Found and fixed a replay-isolation bug: `Usd.Stage.Open(filename)` can reuse
a dirty cached layer containing viewport `/Render` products and camera exposure
schemas from earlier captures. Replay now reads disk into a private anonymous
layer. The artifact retains the exact verified source bytes (USD binary
reserialization alone need not be byte-identical). A regression test deliberately
contaminates the cached layer and verifies that replay ignores it and never
changes the source file. Earlier diagnostic outputs are retained, not relabelled.

Before that fix, `oblique_ipval1ij` and `oblique_gj_d8rm_` compared 16- and
64-pixel guards. Their hashes matched each other but not the pristine source;
both contained prior viewport state. On the same tile-3/4 strip, mean error
fell from 9.1302 to 3.7555/255, still above 2. These are exploratory results,
not clean-source validation. The first denoised/raw attempts
(`oblique_3u_nqwda`, `oblique_88o4i10t`) also had contaminated replay layers
and must not be used for clean single-effect attribution.

Clean-source results, all with 16-pixel guards:

| Capture | Renderer/test | Additional delivered frames | Worst focused overlap mean /255 |
| --- | --- | ---: | ---: |
| `oblique__z1k4ekd` | Original Real-Time 2.0 baseline | 0 | 11.548509 |
| `oblique_6gvt_svm` | Same renderer, render-frame wait | 135 | 10.727362 |
| `oblique_qejy9rj4` | Interactive PT, denoised, 8 spp/update, 1024 total requested | 0 | 6.039388 |
| `oblique_h00ts0mc` | Interactive PT, raw, same requested sample budget | 135 | 5.398763 |

All runs also wait 135 **application updates**. These are not proof of 135
delivered render frames. New metadata records these counts separately. Sample
settings are requested budgets, not a measured convergence counter. The PT
denoised/raw rows differ in waiting as well as denoising, so they do **not**
isolate denoiser causality. In the raw, frame-waited run the repeated tile-4 PNG
pixels were identical, while neighbouring overlaps still failed. This narrows
the issue to cross-tile rendering/sampling, without proving a specific internal
RTX mechanism. Camera parameters and the <=2/255 threshold were never tuned.

The machine-readable comparison is
`artifacts/hidef_marine/tile_diagnostic_comparison.json`. It includes all overlap
metrics and identical-repeat controls restricted to each same comparison region.
Its clean-source checks reject mixed scene hashes.

Every completed clean diagnostic passed live-stage/settings/camera restoration.
After the PT diagnostic, GPU headroom was 615 MiB, below the unchanged 768 MiB
safety threshold; further rendering was stopped. No full marine rerender was
attempted without a passing focused result. No Kit restart was performed.

Next: recover GPU headroom, then compare denoised/raw PT at identical delivered
frame counts and test a higher verified sample budget to distinguish residual
Monte Carlo noise from systematic tile dependence. A larger guard should also
be retested on the pristine source. Do not claim a fix until all 210 overlaps of
a complete native marine image pass, with geometry and restoration rechecked.

Fixed presets use NVIDIA's documented
[Interactive PT settings](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/rtx-renderer_pt.html).
Render-delivery waiting uses the documented
[Viewport API](https://docs.omniverse.nvidia.com/kit/docs/omni.kit.viewport.docs/latest/viewport_api.html).
The live renderer is restored; these are not new global presentation defaults.

Diagnostics are explicitly partial and rejected by the full-image verifier.
The final implementation saves only diagnostic tiles, not a sparse black
full-size `rgb.png`. Earlier diagnostic PNGs remain intact and uncertified.

Final CPU checks: **19 tests passed** (3 native tile, 8 shared HiDef, 4 image
projection, 4 diagnostic-analysis tests), plus source syntax and whitespace
checks. All seven recorded tile matrices in each of the four clean-source
diagnostics matched the independent full-camera rays within **0.000012701 px**.
This verifies geometry, not cross-tile radiometric consistency. The final
partial-output rejection was tested offline; failure-path restoration hardening
was syntax-checked but not fault-injected in Kit. Another GPU diagnostic was
not run below the safety threshold. A capture of the restored existing live
viewport was inspected: ocean and animals were visible, not black or white.

## Clean Kit restart and follow-up — 2026-09-15

The live scene was checkpointed to
`artifacts/scene_checkpoints/checkpoint_dtrp8kj1` before gracefully stopping the
specific Kit process. Checkpoint SHA-256:
`7e6df5abf589336425de8198be6c3adac950468b077be155d277aa4a131cc730`.
Its camera, centimetre units, Y-up convention and exclusion of the transient
`/Render` tree were independently checked with USD Python. The checkpoint was
successfully restored after launching Kit with `cris.madil.render_service`.
Free memory rose from 453 MiB to 3075 MiB with Kit closed, then was 1341 MiB
with the restored scene loaded. Checkpoints preserve frozen appearance, not
controller phase; original gallery assets are reloaded before restarting their
deformations.

Follow-up evidence:

- `oblique_ewpc9qx1`: pristine-source Real-Time guard64 test. Worst expanded
  overlap mean 2.549777/255; worst on the original fixed 16-pixel-guard regions
  4.986758/255. Still failed; wider uniform-water regions are not used to hide
  the residual error.
- `oblique_4f2k3r8p`: denoised PT attempt stopped on camera/image aspect mismatch.
  Its first PNG was **817 × 314**, not the requested **854 × 306**. No accepted
  metadata or image/GSD certificate was produced.
- `oblique_nqq91ix3`: after allowing the renderer switch to settle, the same
  size reset recurred later. Five partial PNGs were retained; the capture failed.
- The next attempt was safely refused at 721 MiB free. Collection of unreachable
  objects before preflight and explicit release of capture-owned stage-cache
  references were added. A subsequent preflight reported 888 MiB; this does not
  prove all retained RTX allocations are fixed. No renderer engine was released.
- `oblique_87r85w6q`: raw 1024-budget run completed with all restoration checks
  true, but worst overlap mean 26.822266/255. This used an experimental sequence
  of one-frame waits, subsequently replaced by a single batch wait; do not treat
  it as a controlled sample-convergence comparison with earlier batch-wait runs.
- `oblique_dvudgl93`: fixed 8192-total/64-per-iteration raw test, using a batch
  wait and 928 MiB preflight headroom, timed out without a valid tile. The
  experiment did not establish whether this sample budget would pass overlaps.

The current tile helper validates projection before **and** after capture. It
checks requested dimensions after a delivered-frame batch, reapplies only the
requested buffer dimensions if a late UI/renderer callback changes them, and
repeats settling. At most three size resets are allowed per tile; instability
fails closed. It never changes camera pose/aperture to accommodate a wrong-sized
image. The batch wait is not a measured path-tracing convergence/sample counter.
NVIDIA documents this separation between automatic UI-sized resolution and an
explicit buffer size in the
[Viewport API](https://docs.omniverse.nvidia.com/kit/docs/omni.kit.viewport.docs/109.0.0/viewport_api.html).

**Milestone remains incomplete.** The restart worked, but memory recovery alone
did not resolve capture consistency. Next investigation should establish reliable
sample completion and fixed render-product sizing across renderer changes before
running another complete native image. The supported capture API exposes
[path-tracing sample budgets](https://docs.omniverse.nvidia.com/kit/docs/omni.kit.capture.viewport/latest/omni.kit.capture.viewport/omni.kit.capture.viewport.CaptureOptions.html);
that capture path has not been integrated or validated here. Do not increase wait
times blindly, relax overlap thresholds, or proceed to biological testing.

Final handoff: **21 CPU tests passed** (5 native tile, 8 shared HiDef, 4 image
projection, 4 diagnostic-analysis), with five source syntax checks and a clean
`git diff --check`. Kit was left running; ocean animation and eleven gallery
swimmers reported active, and the final viewport capture was visually inspected.
Free GPU memory was 590 MiB, so no further native render was attempted. No
complete native marine image was certified in this follow-up.

## Commands

Use the **marine** path, not the older isolated-context capture endpoint:

```bash
python3 tools/capture_hidef_marine.py --native --roll 7.7675 --projection-probe
python3 tools/capture_hidef_marine.py --native --roll 7.7675
python3 tools/capture_hidef_marine.py --replay oblique_CAPTURE_ID
```

The live marine scene must already be loaded. Failed overlaps are deliberately
reported as failure; preserve the diagnostic artifacts for investigation.
With NumPy/Pillow, run:

```bash
python3 tools/capture_calibration_target.py --measure-existing TARGET_DIRECTORY
python3 tools/verify_capture_projection.py CAPTURE_DIRECTORY
```

The source tiles, overlap metrics, full-image matrices and individual product
matrices are retained. No historical captures are overwritten. Native replay
inherits the saved geometry and scene and uses the bounded tile path again.
