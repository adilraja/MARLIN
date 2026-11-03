# Standalone positive-control correction

The first 110.2.0 run saved six captures. Inside views reproduced the neutral
target, but all above-water views showed only the dome colour at the target ROI.
It therefore did not reproduce the known above-water transmission control and
is retained as an unqualified exploratory run, not an accepted version result.

Comparison of effective settings found that the minimal app had disabled native
MDL material warmup, whereas MARLIN's base editor enabled it. Enable that native
warmup for both runtimes. Also match MARLIN's surface-only MDL material binding
exactly; the original standalone draft had additionally connected USD's volume
terminal. Neither adjustment is presented as a successful underwater fix.
Restore the explicit diffuse colour input too, while retaining diffuse weight0.

Retain the draft scenes, manifest, initial harness and first images. Regenerate
the standalone stages and require the above-water positive control to show the
target before interpreting underwater-camera observations. Geometry, camera,
light, exposure, render-frame/sample/ray budgets and memory safeguards remain
unchanged. Both isolated versions must use the same corrected scene/harness.

Before interpreting the corrected runs, require the clear above-water target's
centre HDR channels to exceed half the corresponding clear inside-target
channels. This is a permissive target-observability check anchored to the
fixed emissive control, not a measured absorption coefficient. Retain optical
and data checks separately; an absent above-water target invalidates the
comparison even if PNG/EXR sizes and buffer checks pass.

## Final readiness-controlled protocol

Further exploratory runs showed that a fixed frame count or five-second delay
alone could still capture partially loaded MDL materials. Some clear controls
contained only background; another attempt lost the target after changing the
material. These runs were retained and excluded from the final comparison.
Their failures do not establish a renderer-version difference.

The final scenes reduced the already observed MARLIN flat fixture to its water
mesh, camera, target, background and fixed dome. The target used Kit's native
`OmniEmissive.mdl` with constant white emission, intensity 10 and camera-exposure
compensation; water used `OmniSurface.mdl`. This replaced the exploratory
UsdPreviewSurface emitter. Native `showLights.enabled=true` and material warmup
were held fixed. No MARLIN code was loaded in either SDK.

One stage and material instance remained alive across all six conditions. The
harness checked every incoming scene attribute and applied only differences.
Before each 64-frame wait it required at least five seconds of settling, native
loaded-file count >= total count, and two continuous seconds with no native
stage-streaming activity. Failure to reach that state raised a timeout rather
than producing an accepted capture. The readiness trace was retained. The
metadata field `material_settle_seconds` includes subsequent frame/capture time
because it was sampled when the final record was written; it is an upper bound
on readiness duration, not the exact five-second control.

The independent analysis additionally required both clear target means >100
in every native HDR channel, above/inside clear ratio >.5, and above-water
absorption/clear ratio within .03 of (.6,.8,.9). The threshold of 100 separates
the fixed emitter (~11,000) from the observed background/fallback (<1); it is
an observability condition, not an attenuation acceptance relaxation. The
planned underwater Beer-law tolerance, neutrality and engineering B/R tests
were unchanged.

Both final SDK runs used identical scenes, app and capture source. These
protocol corrections established usable positive controls; they were not a
production underwater-camera fix. No conclusion about the precise cause of
every exploratory failure was inferred from the successful controls.
