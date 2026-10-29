# Final M3 acceptance protocol

The unclamped PathTracing probe confirmed the firefly hypothesis: clear target
HDR increased from about 2.77 to 11099.8; absorption at .75 m then yielded
about (7576.7,9390.0,10246.5), consistent with per-channel attenuation.
Scatter .05 also redistributed light into the background. Preserve the
clamped comparisons as diagnostic evidence; do not use them for coefficients.

Use `controlled_v3_unclamped_effective_usd_settings`, PathTracing, explicit
per-product fog=false and pt/rtpt firefly filters=false, explicit camera
autoExposure=false, constant clipping .01–25 m, all other declared fixed
geometry, light, target/material, camera and 64-frame settling settings.
Keep native emitter10 and all source lights unchanged. Native display PNGs
may saturate this bright target; retain them but measure native float HDR.
For comparison figures only, apply **the same** fixed display transform
clip(RGB/12000,0,1)^(1/2.2) to every retained HDR, with no per-image exposure
or local adjustments. These figures are labelled HDR previews, not SDK PNGs.

Run the original five controls, nine absorption, eight scatter, three unit
and one exposure conditions (26 total), saved in `qa/final/`. Require the
original 3% repeat and unit tolerances; scattering must exceed 3% in signal,
background or contrast and visibly redistribute light. Prefer the native
distance100, scatter .02 engineering candidate if it meets these checks;
otherwise retain it as a diagnostic and report why. No scientific water name.
No new physical coefficient-fitting claim; known MDL coefficients and rendered
relative signals are distinct. No production ocean integration (M4).
