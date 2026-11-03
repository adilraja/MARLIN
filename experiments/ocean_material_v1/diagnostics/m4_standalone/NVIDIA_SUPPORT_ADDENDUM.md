# Standalone version-comparison addendum — not submitted

The MARLIN camera-inside attenuation issue was reproduced in a minimal native
Kit app, without MARLIN imports, assets, services or controllers. Official SDK
builds were isolated from the working installation and tested sequentially:

- `110.2.0+feature.342835.698af100.gl`
- `110.4.1+production.392751.33a8249d.gl`

See the bundled result summary and captured source/effective settings. Both
final runs used the same USDA scenes and harness, a persistent material
instance, native streaming/material readiness checks and 64 rendered-frame
settling. The above-water clear and absorbing controls qualified. With the
camera .5 m inside the closed mesh, clear, absorption-only and engineering
water all returned the same neutral target. A negative result was not accepted
from the earlier captures whose material/target controls were unready.

The direct underwater path was .5 m. With OmniSurface transmission colour
(.6,.8,.9) at native depth 100 in a .01 m/unit stage, the planned absorption/clear
ratio was approximately (.7746,.8944,.9487); the measured ratio was (1,1,1) in
both SDKs. For the 1 m target depth viewed through the interface from above,
the measured ratio was approximately (.601,.800,.899) in both SDKs.

The mesh is closed, outward oriented and Y-up. Thin-walled is false. The target
uses native OmniEmissive; water uses native OmniSurface. PathTracing, fixed
exposure, no fog, no firefly filtering, 16 total/glossy bounces and 512×384
captures were used. Actual accumulated sample count was not measured. Host:
NVIDIA RTX A2000, 6138 MiB, Linux, driver 595.91.07. Resource safeguards passed.

Questions for NVIDIA:

1. What supported authoring/settings mechanism initialises a primary camera
   ray with an enclosing OmniSurface medium's absorption/scattering properties?
2. Is the enclosed homogeneous OmniSurface representation supported for a
   camera already inside it in these builds? If so, which requirement is missing?
3. Does OMPE-96387 address this case, or a distinct transmission problem?
4. If a separate native spatial-volume representation is required, what is the
   supported route for matching it to an animated ocean boundary?

The reproduction makes no image-space correction, artificial camera shell,
target-opacity adjustment or substitute-fog workaround. No SDK/library files
were modified. The working MARLIN installation was not upgraded. The remaining
underwater distance sweep and animated integration are conditional on finding
a supported mechanism and were not marked complete.
