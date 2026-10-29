# Bounded renderer diagnosis before selecting a medium preset

The corrected RealTimePathTracing captures established repeatable channel
filtering, a scene-unit distance interpretation, and a coupled scattering
slider response. However HDR target luminance remained approximately constant
while red fell and blue rose; no absolute absorption coefficient was inferred.
The +1-stop camera probe did not change either saved output in that mode.
This is insufficient evidence of absolute medium radiometry. The real-time
captures and results remain retained, not relabelled as physical transmission.

To resolve this M3 limitation, test only the .75 m clear, absorption and scatter
.05 conditions in the installed PathTracing mode, using the same existing SDK,
512x384 output, 64 rendered-frame settling, lights/geometry and 768 MiB guard.
No bounce/sample budget increase, vendor changes or app restart. Select the
mode through the registered render-product attribute, checking allowed tokens.
Keep physical clipping distances fixed at .01–25 m for all subsequent captures
(previous automatic clipping bounds were outside all water/target paths).
If successful, run the already declared depth/distance/scattering sweep in
that mode and select its engineering preset. If not, report M3 partial.

Acceptance remains 3% repeat/unit equivalence; require absorption-only to
reduce at least one signal channel by >3% with path length, and a repeatable
scattering change beyond 3% in signal, background or contrast. Inspect spatial
light redistribution as well as tint to avoid confusing coupled absorption
changes with demonstrated volume scattering. The mode comparison required
by M5 and broad save/reload validation remain later work.
