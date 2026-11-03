# M4 — Standalone reproduction and isolated Kit comparison

| Field | Result |
|---|---|
| Sprint | MARLIN — Ocean Material and Underwater Appearance |
| Milestone | 4 — Apply the material to the existing animated ocean |
| Recorded | 30 October 2026 |
| Investigation | Completed standalone reproduction and isolated version comparison |
| Underwater-camera issue | Reproduced in both SDKs; unresolved |
| Milestone 4 | Remained open |
| Working MARLIN installation | Unchanged; reopened and restored after approved temporary closure |
| Evidence | `../diagnostics/m4_standalone/` |

The newer SDK did **not** resolve the tested camera-inside attenuation issue.
Both final runs rendered valid clear and absorbing controls from above water.
With the camera inside the closed water mesh, clear, absorption-only and
engineering water all produced the same neutral target: **(11336,11336,11336)**
in the measured native HDR ROI. No production water fix or runtime upgrade was
applied to MARLIN.

## Matched comparison

Two official, private SDKs ran sequentially:

| SDK | Recorded native build | Final run |
|---|---|---|
| Matching baseline | `110.2.0+feature.342835.698af100.gl` | `baseline_render_09` |
| Production candidate | `110.4.1+production.392751.33a8249d.gl` | `candidate_render_03` |

The baseline matched the existing application's recorded kernel build. The
candidate came from NVIDIA's upstream Kit App Template package manifest, saved
with the exact downloaded package metadata. These were complete native SDK and
extension environments; the experiment did not isolate a single renderer
binary. Both resolved the same water MDL source SHA-256,
`f69e5d0c80194df2972d29f58635e7c23ada1844c7ed763e089287371fe67498`.
Native runtime and extension identifiers were recorded for each run.

NVIDIA's [Kit 110.4 release notes](https://docs.omniverse.nvidia.com/dev-guide/latest/release-notes/110_4.html)
list OMPE-96387 as a fix involving camera-dependent transmission. That entry
motivated testing; it was not treated as proof that this enclosed-medium case
was supported or fixed. The standalone observations did not establish such a
fix in the tested candidate.

The final twelve captures used identical human-readable USDA files, app and
capture source. A closed outward-oriented flat enclosure, white native MDL
emitter, black background, constant dome and camera were the entire scene.
There were no MARLIN imports, HTTP services, controllers, animal assets,
references, payloads or external textures. Only standard `OmniSurface.mdl` and
`OmniEmissive.mdl` were resolved from each SDK. The supplied scenes ran without
accessing the original fixture from which their geometry was reduced.

## Optical result

Ratios below are absorption-only HDR divided by clear HDR from the same view
and SDK. The ROI was rows 184..199 and columns 248..263.

| View/path | Expected direct ratio RGB | Kit 110.2.0 | Kit 110.4.1 |
|---|---|---|---|
| Inside, .5 m | (.7746, .8944, .9487) | (1, 1, 1) | (1, 1, 1) |
| Above, target depth 1 m | (.6, .8, .9) control | (.60068, .80020, .89856) | (.60078, .80035, .89877) |

The inside ratio errors were (.2254,.1056,.0513), all exceeding the planned
.03 absolute tolerance. Engineering water's inside blue/red ratio was 1 in
both builds, failing B/R>1.05. From above it was approximately 1.4974 and
1.4975. Clear channels were neutral. Both final runs passed the visible-emitter
and above-water absorption controls, so the underwater failure was observed
with functioning material transmission from outside the interface.

Fifteen scene variants were prepared and passed native CPU USD validation in
both SDKs, including .25, .5, 1 and 2 m inside paths. The initial .5 m inside
test failed, so the conditional distance sweep was not rendered. Animated-ocean
qualification was not repeated or marked complete by this standalone task.

The [fixed-scale image comparison](../diagnostics/m4_standalone/comparisons/sdk_controls.png)
uses `log1p(RGB)/log1p(12000)` for every panel. Display PNGs saturated at the
chosen emitter level. EXR and float NPZ were retained as measurement evidence;
absolute radiometric calibration was not established.

## Capture controls and exploratory attempts

The stage used Y up and .01 metres/unit, with a water bottom at -5 m. The
inside camera was at (12,-.5,0) m; its initial target lay .5 m below it. The
above camera was at (12,3,0) m and target depth 1 m. The medium used transmission
colour (.6,.8,.9), native transmission depth 100, IOR 1.333, roughness .001,
thin-walled false, and scattering colour 0 or .02. The fixed white native
emitter had intensity 10 and camera-exposure compensation enabled.

PathTracing used 512×384 resolution, fixed exposure, disabled fog/firefly
filters, 16 total/glossy bounces, denoising enabled, native visible emitters,
configured sample limit 512 and one sample/iteration. The actual accumulated
sample count was not measured. Camera matrices, actual render-product camera
and resolution, authored controls, buffer shape/finite checks and exact scene
hashes were validated.

Early runs exposed asynchronous material-readiness problems in the minimal
app. Some controls captured background or a fallback state. The final harness
retained one stage/material instance, applied and checked changed scene
attributes, required at least five seconds of settling and two quiet seconds
with completed native file loading and no streaming activity, then waited for
64 delivered rendered frames. Readiness traces were saved. A capture/file pass
was kept separate from optical qualification.

The final comparison additionally required visible clear emitters in both views
(>100/channel, compared with observed target ~11,000 and background <1), clear
above/inside ratio >.5, and the above absorption control within .03. These
conditions rejected unready controls; the underwater acceptance tolerance
remained unchanged. The source snapshots and detailed amendment explain the
intermediate protocol changes. No causal attribution was made for every early
failure.

All **68** captures across twelve rendering attempts were retained: twelve in
the final matched comparison, six in an additional supporting baseline run,
two dry geometry/camera controls, and 48 other exploratory captures. The
earlier candidate run with absent clear emitters was excluded. The final
report's version result comes from the matched pair, not from those excluded
images. Readiness corrections were diagnostic protocol changes, not a fix to
the production ocean.

## Resources and preservation

The host used an RTX A2000, 6138 MiB, driver 595.91.07. Each launch required
2048 MiB free; each capture required 768 MiB. Final baseline/candidate minimum
pre-capture free values were 2041/2037 MiB. Once-per-second global GPU samples
recorded minimum free values 2013/2034 MiB. These are sampled host values, not
exact per-process memory peaks. Final process times were 75.4/50.9 seconds;
they include differing startup/cache conditions and are not a benchmark.

All SDK downloads, package roots, extensions, shader/CUDA caches, configuration
and user data were private to this experiment. Initial precaching completed
for both SDKs. Informational IOMMU notices owned by the isolated test processes
were acknowledged without changing BIOS, kernel, driver or renderer settings.
No SDK/library files were patched. The test still failed with ample measured
headroom; these observations do not support blaming this failure on memory
shortage.

The user approved checkpointed temporary MARLIN closure. A fresh checkpoint,
`checkpoint_3zhoh8ur`, was saved before gracefully stopping the verified original
process. After the sequential tests, the same MARLIN app and original binary
were reopened. The executable SHA-256 matched. All 73 renderer settings,
camera, 1280×720 resolution, fill-frame and display options matched the saved
checkpoint. Ocean and chase controller parameters matched, with swimming
disabled. Procedural animation phase was reconstructed after the closure.

All 128 pre-work source hashes and nine prior follow-up source pins matched.
All 1,514 pinned evidence files from M1, M2, M3, M4 and the underwater follow-up
remained unchanged. Existing source modifications from those earlier tasks
were preserved. This investigation added experiment files only.

## Delivered reproduction and next dependency

`marlin_camera_inside_reproducer.zip` contains the fifteen final scenes,
manifest, native app/harness, portable launcher, README, protocol amendment,
comparison summary and image. SDK binaries and proprietary material-library
files are not bundled. The README provides separate precache and render
commands with private profiles. The ZIP was checked for path safety, integrity
and scene/source hash consistency; it was not rerun on a second host.

`NVIDIA_SUPPORT_ADDENDUM.md` extends the earlier support draft with the isolated
results and asks for a supported initial-medium mechanism for primary camera
rays. Neither document was sent externally. Vendor guidance or a separately
qualified native volume representation remains the next dependency. Expanding
the animated volume architecture would require explicit scope consideration.

M4 remained open; M5 and M6 were not marked complete. A working supported
inside-camera mechanism must pass the original distance sweep, animated-ocean
integration, sampler/controller regressions and rollback before completion.
