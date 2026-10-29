# M2 — Transmission and refraction in an isolated water fixture

Date: 29 October 2026. Status: **passed for the declared isolated engineering
fixture and tested capture configuration**. This did not integrate a material
into the animated ocean, calibrate seawater attenuation or complete M3–M6.

## Implemented changes

Added the fixed NVIDIA Kit Services endpoint
`POST /scene/ocean/material/diagnostic/capture` in `water_diagnostics.py`.
It reused the existing calibration-camera and isolated capture implementation,
and the existing OmniSurface input-authoring helper. The capture helper gained
optional output-root, viewport-setup and rendered-frame-wait arguments; its
existing callers retained their previous defaults. The service imported the new
diagnostic module. Syntax checks passed for all three changed source modules.

The existing Kit application loaded the diagnostic through extension reload;
M2 required no application restart, runtime upgrade, standalone renderer or
arbitrary command-execution endpoint. The request accepted only fixed views,
conditions, diagnostic probes and a bounded settling choice. Invalid view input
returned HTTP 422. The unchanged 768 MiB GPU guard rejected insufficient
headroom before rendering; it was not disabled.

## Fixture, material and camera

The isolated USD context explicitly used Y-up and 0.01 metres per scene unit.
A white emissive 0.18 × 0.18 m fiducial lay at (0,-1,0) m, above a black surface
at y=-1.02 m. Target geometry and its own material were byte-identical across
the six settled conditions. Known target dimensions were also checked from
world bounds. The target and camera were never hidden to manufacture transmission.

The water was one closed six-face mesh bounded by (-5,-2,-5)..(5,0,5) m.
Every edge had two incident faces and each tested face normal pointed outward.
The target was inside the declared medium, and there was no duplicate coplanar
top interface. Water geometry was identical across both non-dry conditions.
No waves, normal textures, displacement or wildlife were present in the fixture.

The installed OmniSurface path was retained. The selected settings were
transmission enabled/weight 1, reflection weight 1, IOR 1.333, roughness 0.001,
base contribution 0, white transmission colour, zero scatter colour, positive
native depth 100 and `thin_walled=false`. Geometry opacity was not reduced.
Installed opacity defaults and supported input declarations were established in
M1. Air index 1.0 and water index 1.333 remained engineering assumptions.
The matched control used IOR 1.0 with the same closed geometry and depth.

**Depth 100 was not converted into a claimed physical attenuation distance.**
White transmission and zero scatter isolated refraction; physical distance
interpretation and absorption/scattering measurements remained M3 work.
The selected preset and complete effective capture settings were recorded in
`../diagnostics/m2/selected_preset.json`.

Images were 512 × 384 pixels. The ideal diagnostic camera used focal length
35 mm, pixel pitch 40 micrometres and focal length 875 pixels. Its vertical
separation above the target was 4 m, putting it 3 m above the interface.
Nadir pitch was zero; oblique pitch was 40 degrees. Camera definitions were
identical across conditions within each view. Saved render-product resolution
and camera were checked independently of the UI projection.

The existing renderer setting remained `RealTimePathTracing`, with RTPT bounce
budgets 8/8 and translucency enabled. It was not silently switched to another
mode. The pre-existing height fog and auto exposure were disabled only during
the diagnostic and restored afterward. The installed viewport action disabled
grid, axis and light gizmos only in the temporary measurement viewport.
The physical red/green reflection markers remained present.

## Preserved development failures and settling requirement

The first six-condition set used native depth zero. The dry fiducial rendered,
but the medium conditions failed the predeclared observability check. These
captures were retained. A single positive-depth probe showed the target, while
a separate reflection-off probe did not resolve the failure. Reflection-off
was never selected as an accepted replacement for physical reflection.

A fresh positive-depth set using only application-update settling remained
inconsistent: the oblique water target disappeared again. This set was also
retained as failed optical evidence, despite successful capture API responses.
The initial global display bitmask also failed to remove viewport overlays;
the installed per-viewport action corrected capture hygiene for later images.

Before the final bounded set, the settling plan added a completed wait for
**64 rendered frames**, with a 30-second wait timeout. The existing warm-up
and capture-completion protocol remained. No ray budget, output size, camera,
target, refractive index or opacity was altered to obtain that pass.
Unreachable Python objects were collected before the unchanged memory guard.
The complete six-condition set then passed, followed by a fresh default-preset
reconstruction. Rendered-frame waits were not presented as measured sample counts.

Plans and raw execution records were retained separately:
`PLAN.md`, `PROBE_PLAN.md`, `ACCEPTANCE_RUN.md`, `SETTLING_CHECK.md`, and the
four request/result records under `../diagnostics/m2/qa/`.

## Refraction prediction and measured results

The independent geometric calculation solved Snell's law at the flat y=0
interface for the camera-to-target-centre ray, then projected the intersection
through the declared camera. It used the actual camera basis and pixel
intrinsics, not a hand-selected displacement fitted to the images.
The original fixed neutral-pixel ROI, threshold, four-connected component
selection and minimum area were retained for accepted measurements.

The acceptance tolerance was the larger of 2 pixels and 1% of predicted
displacement. Image coordinates increased downward, so a negative vertical
displacement represented an upward shift.

| View and condition | Predicted vertical shift | Measured vertical shift | Vector error | Result |
| --- | ---: | ---: | ---: | --- |
| Nadir, matched index | 0 px | 0 px | 0 px | Passed |
| Nadir, water | 0 px | +0.012 px | 0.017 px | Passed |
| Oblique, matched index | 0 px | +0.017 px | 0.249 px | Passed |
| Oblique, water | −40.873 px | −40.637 px | 0.288 px | Passed |

All required targets were observable in the settled set. The oblique water
displacement exceeded the measurement uncertainty and agreed with the planar
prediction within the original 2-pixel tolerance. A fresh request with an empty
JSON body reconstructed the selected default preset and gave the same 0.288-pixel
error. These results established the declared engineering refraction check,
not physical calibration of a field camera or measured seawater properties.

Accepted raw images:

- [Oblique dry control](../diagnostics/m2/captures/oblique_k7diovqm/rgb.png)
- [Oblique matched-index control](../diagnostics/m2/captures/oblique_2b1jua4s/rgb.png)
- [Oblique water candidate](../diagnostics/m2/captures/oblique_nurn8ljo/rgb.png)
- [Nadir water candidate](../diagnostics/m2/captures/nadir_9tai1y_k/rgb.png)
- [Fresh default reconstruction](../diagnostics/m2/captures/oblique_t3ef46mz/rgb.png)

## Reflection and dependency evidence

Fixed red/green emissive markers at z=-4 m, y=4..6 m were outside the direct
target view. They appeared as reflected coloured bands in the oblique water
image. A simple colour-presence check counted 26,319 red and 26,319 green pixels
in that image, versus zero of either class in dry and matched controls.
This supported visual reflection demonstration, not calibrated reflectance.

OmniSurface was the selected installed material; OmniGlass was inspected as an
available alternative but was not selected or substituted. The saved USDs
retained the actual MDL source and authored settings. No MDL module-load or
shader-fallback error was observed for the fixture. Existing asset-importer
dependency errors and temporary-viewport UI callback errors remained recorded;
they were not hidden, repaired in vendor files or counted as clean SDK shutdown.
The quantitative pixel check provided the material-behaviour evidence.

## Resources, regressions and restoration

The same RTX A2000/6,138 MiB host and driver 595.91.07 were used. Settled-set
preflight free memory was 1,268–1,495 MiB, above the unchanged 768 MiB guard.
These were observations before requests, not continuously sampled peak usage.
The coroutine timeout remained 90 seconds; no native-resolution sensor run or
larger dataset was attempted.

Six initial requests, two probes, six update-settled acceptance attempts, six
rendered-frame-settled conditions and one fresh reconstruction produced 21
rendered requests. Only the declared settled set and fresh reconstruction
passed the final optical checks. Earlier black/unstable images remained failures.

Sixteen offline tests passed: four independent refraction-math checks, four
existing water-material checks, five renderer-snapshot checks and three
calibration-geometry checks. Two existing native-USD tests were skipped because
standalone Python lacked pxr. Native Kit projection, closure, dimensions and
camera checks executed in the actual diagnostic captures; those skips were not
reported as offline passes.

The default stage remained retained in every accepted capture. Afterward, the
saved marine checkpoint and original live setup were restored. All 73 recorded
renderer settings, active camera, resolution and global display setting matched
the pre-M2 values. Reconstructing live setup reset procedural history; exact
controller/wave phase restoration was not claimed. All pinned M1 evidence files
still matched their hashes. The live ocean material was not replaced by this
isolated preset. No human review acceptance or later-milestone completion was inferred.

## References and remaining boundary

The installed definitions were authoritative for names and types. Relevant
official documentation was checked as a guide, with local execution supplying
the actual support evidence:

- [NVIDIA OmniSurface transmission](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/templates/parameters/OmniSurface_Transmission.html)
- [NVIDIA OmniSurface medium controls](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/templates/OmniSurface.html)
- [Installed-version viewport display overview](https://docs.omniverse.nvidia.com/kit/docs/omni.kit.viewport.menubar.display/107.1.3/Overview.html)

M2 established reflection, transmission and a measured planar refraction result
for one isolated closed medium under one supported capture configuration.
Absorption/scattering calibration, animated-ocean integration, broad renderer
comparisons, native sensor capture and biological visibility remained outside
this milestone's acceptance.
