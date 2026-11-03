# M4 — Underwater-camera attenuation follow-up

| Field | Result |
|---|---|
| Sprint | MARLIN — Ocean Material and Underwater Appearance |
| Recorded | 30 October 2026 |
| Milestone | 4 — Apply the material to the existing animated ocean |
| Status | Unresolved native inside-medium rendering; milestone remained open |
| Follow-up evidence | `../diagnostics/m4_underwater/` |
| New production water fix | None qualified or enabled |

Fifteen saved-image probes completed: twelve views from inside water and three
above-water controls. Every inside view returned the same neutral target HDR
mean, **(11336, 11336, 11336)**. A small flat enclosure reproduced the failure
without the animated wave geometry. The material attenuated the target when
viewed from above. A supported solution to the camera-inside case was not found
in this installation; this follow-up did not close M4.

## What was tested

The existing viewport rendered 512×384 images in PathTracing. The diagnostic
camera, white emissive target, exposure, native HDR buffer, 64 delivered-frame
settling and 768 MiB safeguard followed the original M4 procedure. Both fog and
automatic exposure were disabled. EXR, float NPZ, display PNG, effective native
settings, frozen USD and restoration records were retained for every capture.

The diagnostic camera was at (12, -.5, 0) metres for inside views and at
(12, 3, 0) for nadir controls. The target was fixed at Y=-1 m. The curved-ocean
probes froze the original wave calculation at one second. The flat fixture
temporarily replaced only the render geometry of `/World/Ocean` within the
existing capture transaction: X=10..14 m, Z=-2..2 m, top Y=0 and bottom Y=-3 m.
It had nine points and nine consistently oriented faces, with a shared skirt
and bottom-centre triangulation. Closure/orientation checks passed. There was
no second top surface. All original geometry was restored after each request.

| Probe | Result for inside camera |
|---|---|
| Repeat selected M4 medium | Neutral target, failure reproduced |
| USD double-sided geometry | Neutral target |
| Registered non-uniform-volume control | Neutral target |
| Existing MDL shader connected to USD volume terminal | Neutral target |
| Volume terminal plus non-uniform-volume control | Neutral target |
| Installed `OmniVolumePerlinNoise`, equal endpoint colours, absorption only | Neutral target |
| Native control set in both Carbonite and render-product scopes, after restart | Neutral target for original and procedural material |
| Installed procedural material with differing endpoint colours and nonzero scattering | Neutral target; coloured attenuation from above |
| Flat closed enclosure with selected engineering medium | Neutral target |
| Flat closed enclosure with clear medium | Identical neutral target |
| Flat enclosure with both native radiance and light caches disabled | Neutral target |

The procedural-volume probes were compatibility diagnostics. They changed the
water shader within the temporary transaction, including its interface IOR,
and were **not** accepted as equivalent replacements for the M3/M4 medium.
Their existing NVIDIA material identifiers and inputs were read from the
installed definitions. No vendor files were changed. The final diagnostic
source and patch are retained; requests spanned source reloads as the fixed
probes were added. A single source hash is not asserted for all fifteen images.

## Controlled observation

The predeclared measurement used rows 184..199 and columns 248..263 of the
native float HDR buffer. The flat-enclosure results were:

| View | Clear medium RGB | Selected engineering medium RGB |
|---|---|---|
| Above water | (11112.8, 11112.8, 11121.8) | (6575.8, 8749.5, 9852.6) |
| Inside water | (11336, 11336, 11336) | (11336, 11336, 11336) |

All twelve inside views failed the planned chromatic attenuation qualification.
The intended distance sweep was conditional on finding a working fix and was
not run. No acceptance threshold was weakened to manufacture a pass.

`comparisons/flat_enclosure_controls.png` shows clear/selected pairs using one
fixed `log1p(RGB)/log1p(12000)` mapping. The native display PNGs remained
saturated; the reported means came from the retained float buffers.

These observations support the inference that the tested material path does
not initialise the primary ray with the enclosing medium's optical properties.
They do not prove that every NVIDIA volume representation, renderer mode or
later release lacks camera-inside support. The missing supported mechanism
remains the dependency to resolve.

## Native support investigation

The registered camera/volume schema inventory and RTX settings tree were read
through the application's APIs. No initial-medium camera control was found in
that inventory. The native mapping from `/rtx/pathtracing/ptvol/enabled` to
`omni:rtx:pt:ptvol:enabled` was verified in the startup log. Both scopes were
explicitly tested after restart. Final bound-shader records verify the actual
procedural material and controls for those later probes.

NVIDIA's [PathTracing documentation](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/rtx-renderer_pt.html)
describes procedural MDL volumes and the non-uniform-volume setting. The
[MDL/OpenUSD reference](https://docs.omniverse.nvidia.com/usd/latest/technical_reference/referencing_mdl.html)
documents the surface and volume terminals. Those supported authoring routes
did not fix the tested case. Neither document was treated as proof that these
specific camera-inside captures should work.

The inspected native `OmniVolumeDensity.mdl` and `OmniVolumeNoise.mdl` hashes
are retained. Inspection was limited to those core volume definitions and
targeted non-recursive material-family inventories; there was no recursive
runtime scan or vendor edit. A diagnostic capability endpoint initially used
an unavailable Sdr method and returned HTTP 500; its corrected SDK call then
recorded the inventory. The log snapshot retains that diagnostic error.

## Resources and restoration

The host remained an RTX A2000 with 6138 MiB and driver 595.91.07, using the
existing Kit 110.2.0 runtime. One attempted batch was rejected at 670 MiB free
before rendering. A fresh checkpoint was saved, the verified Kit process was
stopped gracefully, and the same app was relaunched once. No reboot, runtime
upgrade, package installation or vendor replacement was performed.

All fifteen successful requests passed the unchanged guard; the smallest
recorded pre-request free-memory value was 891 MiB. This is a sampled request
value, not a continuous memory peak. The failed optics persisted after restart
with adequate headroom, so these observations do not support treating memory
shortage as the cause of this particular failure.

The original pre-work checkpoint `checkpoint_mpwvumxn` and standard marine
setup were restored. All 73 recorded renderer settings, camera, 1280×720
resolution, fill-frame and display options matched. The additional native
volume global returned to false; the original material and 16,641-point,
16,384-face ocean were active. Ocean/chase controllers were reconstructed with
swimming disabled; animation phase was reconstructed rather than preserved.

Thirty offline tests passed and two general USD-dependent tests were skipped.
Seven canonical modules passed syntax checks. The four original wave/sampler
functions retained identical ASTs, and the cetacean controller retained
identical bytes. All 1,286 pinned M1/M2/M3/initial-M4 evidence files remained
unchanged. This follow-up extended bounded diagnostics only; the water preset
remained explicitly unqualified for an inside camera.

## Next dependency

Use the prepared `NVIDIA_SUPPORT_CASE.md`, frozen scenes and effective-control
records to establish a supported initial-medium mechanism for this Kit/RTX
build. That draft has not been sent externally. A runtime change must be tested
in isolation against the same clear/attenuating inside/above controls before
altering the working installation; a newer version alone is not evidence of a
fix.

A separate native spatial-volume representation is another research direction,
but it has not been shown to solve this case. Coupling a new density field to
the animated boundary would broaden this material/enclosure implementation.
The sprint's geometry exception requires reporting a major geometry dependency
before expanding it. No density-grid system, artificial camera shell, target
opacity change, image-space attenuation or substitute fog was introduced.

M4 stays open. Its previously validated above-water integration and rollback
remain available. M5 and M6 were not marked complete by this investigation.
