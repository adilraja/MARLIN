# Native HiDef tiled capture — 2026-09-15

**Milestone status: incomplete. Native metric-target rendering passed; native
marine rendering remains diagnostic because tile-overlap checks failed.**

## Method and safety

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

Two tile geometry/coverage tests, four projection tests and seven shared HiDef
regression tests passed (13 total). Hardware calibration, biological detectability,
native Sony rendering and monolithic native GPU rendering are outside this work.

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
