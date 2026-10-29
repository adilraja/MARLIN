# M3 declared experiment — 29 October 2026

The M2 accepted clear control and evidence remain immutable. This experiment
reuses its closed, outward-facing 10 × 2 × 10 m volume and fully present
OmniSurface interface (IOR 1.333, roughness .001, transmission 1, thin-walled
false, no opacity override). No production ocean material is changed.

## Fixed conditions and measurements

One .18 × .18 m emissive white target (value 10) is moved vertically to
depths .25, .75 and 1.25 m. Camera remains at (0,3,0) m, nadir, 35 mm focal
length, 40 µm pixels, 512 × 384 output. The black background stays at -1.8 m;
all lights, marker geometry, water bounds and renderer settings stay fixed.
Target material, size, normals and visibility remain identical. Fog and the
height-triggered underwater cue are off. No waves or normal detail.

Each capture waits 64 rendered frames, retains LDR PNG and native HdrColor
float buffer (plus EXR when available), and records all render settings. Use
target ROI x=248:264, y=184:200 and two background ROIs x=190:206 and
306:322, y=184:200 (half-open indexing). Report channel means, target-minus-
background signal, Michelson contrast (T-B)/(T+B), and signal relative to the
same-depth clear control. These fixed ROIs must be inspected for containment
before acceptance; a failed ROI test invalidates measurements, not the image.
HDR is a renderer AOV, not calibrated radiance. Check exposure independence
with an extra fixed-scene exposure diagnostic before calling it linear.
Reject nonfloat/malformed buffers and nonfinite values. Never fit coefficients
from LDR pixels or claim field water calibration.

## Sweep order and unit hypotheses

1. Clear control: transmission RGB (1,1,1), native distance 100, scatter 0,
   all three depths, including one repeat at .75 m to measure noise.
2. Absorption-only engineering candidates: RGB (.6,.8,.9), native distance
   50, 100, 200, scatter 0, all three depths. Select the middle candidate
   unless unsupported or it fails useful contrast. Preserve every attempt.
3. Separately compare scatter RGB (.02,.02,.02), (.05,.05,.05), holding
   transmission RGB (.6,.8,.9) and native distance 100 fixed at all depths.
   The shader couples extinction colour/distance with scattering; these are
   native engineering controls, not independent measured sigma coefficients.
4. Known-distance check at .75 m: isolated stage units .01 m and 1 m.
   Compare .01/native100 with 1/native1 and 1/native100, including a clear
   control at unit1. Every physical dimension and camera stays fixed.
   Scene-unit interpretation predicts matching compensated pair; metadata-
   aware metre interpretation predicts matching uncompensated pair. Adopt
   neither hypothesis without measured evidence; never rescale MARLIN.

## Predeclared acceptance and safeguards

GPU guard 768 MiB free before each request; one isolated context at a time;
90-second request timeout. No restart, native resolution increase, ray-budget
increase or dependency installation. Record failures and narrow explicitly.
Require relative signal repeatability within 3% at .75 m; use this tolerance
also for compensated unit equivalence. Depth/parameter changes must exceed
max(3%, three times observed repeat variation) in at least one channel.
Scattering must produce a reproducible signal/contrast/background change
beyond that threshold against absorption-only; otherwise report unsupported
or unresolved scattering, and partial completion. No requirement that every
individual pixel darken monotonically. Check fixed background and target ROIs
visually, physical target bounds numerically, camera/renderer equality,
default-stage retention and renderer restoration. Keep M1/M2 pinned hashes.

Select only one engineering preset, with actual tested renderer and unit
interpretation. Integration with the animated ocean belongs to M4.
