# Unclamped radiometric control before the final sweep

The path-traced .75 m comparison produced an actual scattering background
increase, but the bright absorption-only target still retained nearly constant
luminance. Inspecting the retained effective USD controls showed that both
renderer modes had firefly filtering enabled, including per-emissive and per-
sample intensity limits (3200 native unexposed intensity). Bright emissive
fiducials may therefore be clamped. This is a hypothesis to test, not a finding
inferred solely from the presence of the setting.

Repeat the three .75 m PathTracing probes with the installed, registered
`omni:rtx:pt:fireflyFilter:enabled` and `omni:rtx:rtpt:fireflyFilter:enabled`
authored false on the isolated render product. Keep the original target10,
camera, lighting, geometry, scattering controls, ray/sample budgets and memory
guard. Preserve all previous captures and source snapshots. If absorption
now follows per-channel transmission ratios below one, run the declared final
depth/distance/scattering sweep using this explicit capture configuration.
Do not use clamped HDR values to estimate absorption coefficients.
