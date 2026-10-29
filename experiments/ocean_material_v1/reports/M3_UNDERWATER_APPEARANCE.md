# M3 — Controlled absorption and underwater clarity

| Field | Value |
|---|---|
| Sprint | MARLIN — Ocean Material and Underwater Appearance |
| Milestone | 3 — Add controlled absorption and underwater clarity |
| Recorded | 29 October 2026 |
| Base commit | `b570d0e` |

**Result:** Passed the declared isolated, unclamped **PathTracing** engineering
scope. Animated-ocean integration remains M4 work.

M3 established depth-dependent RGB attenuation, a checked distance conversion,
and separately demonstrated volume-light redistribution from the installed
scattering control. It selected one engineering medium candidate, preserved
the unsuccessful and clamped diagnostic attempts, and restored the live marine
scene. It did not change the production ocean preset or animal materials.

## Evidence and implementation

The complete package is `../diagnostics/m3/`:

- `engineering_medium_v1.json`: the selected candidate and required renderer.
- `qa/final/*_execution.json`: exact requests, output directories and timings
  for the **26 final captures**. These identify accepted captures; directory
  names alone do not distinguish them from earlier diagnostics.
- `qa/measurements_final.json`, `qa/final_validation.json`: measurements and
  acceptance checks, including each camera, physical fixture and output.
- `comparisons/`: fixed-scale HDR previews, measurement ROIs and plots.
- `PLAN.md` and its explicit subsequent diagnostic protocols: decisions and
  tolerances recorded before the corresponding acceptance run.
- `qa/restoration_validation.json`, `qa/previous_evidence_integrity.json`:
  restoration and M1/M2 integrity checks.

The implementation added the bounded Kit Services route
`POST /scene/ocean/material/diagnostic/medium/capture`. It reused the M2 mesh,
material-authoring and camera helpers and the existing viewport SDK capture
path. The common capture helper gained an optional extra-output callback;
existing callers retain their defaults. The M2 builder gained optional target
height, background height and medium parameters with its old defaults intact.
The capability route now inspects fixed registered camera/render-product
schemas and installed capture signatures. There is no arbitrary code, input
file or output-path execution route.

No vendor files, runtime binaries or generated copies were edited. Targeted
read-only inspection followed the live-resolved OmniSurface wrapper imports
to `OmniSurfaceBase.mdl` and `OmniShared.mdl`; paths, hashes and the relevant
algorithm interpretation are retained in `qa/installed_medium_definition.json`.

## Fixed physical fixture

The M2 accepted package remained unchanged. M3 reconstructed its clear medium
control with a target-depth sweep and a fixed lower background:

| Quantity | Final value |
|---|---|
| Coordinates and normal stage units | Y-up; 0.01 metres per scene unit |
| Closed water bounds | X/Z ±5 m; Y from -2 to 0 m |
| Boundary checks | Six outward-facing faces; zero boundary edges |
| Target | One white emissive 0.18 × 0.18 m square; emission RGB10 |
| Target depths | 0.25, 0.75, 1.25 m below the interface |
| Black background | Fixed Y=-1.8 m; fixed material and dimensions |
| Camera | Nadir at (0,3,0) m; fixed orientation and clipping 0.01–25 m |
| Intrinsics/output | 35 mm focal length; 40 µm pixels; fx=fy=875 px; 512×384 |
| Lighting | M2 dome and red/green emissive markers, unchanged across conditions |
| Interface | IOR 1.333; roughness 0.001; transmission 1; diffuse weight 0 |
| Interior | `thin_walled=false`; no opacity override |
| Other effects | No waves or normal detail; product fog and camera auto exposure disabled |

The target moved only vertically. Its size, material, normals and visibility
remained fixed. All dimensions were converted from metres into the selected
isolated stage units. Native USD bounds measured the target, and capture
metadata recorded the actual camera matrices and render-product dimensions.
The final validation checked those values for every accepted capture.

All accepted runs used the installed `PathTracing` mode. The isolated product
explicitly requested `HdrColor` and disabled its pt/rtpt firefly filters.
The camera/product USD attributes, including defaults, are preserved in each
`effective_settings.json`. The separate `renderer_settings` metadata field
records legacy global settings before viewport setup; its scope is labelled
and must not be confused with the effective per-product record.

## What the diagnosis found

Two initial HDR requests failed: the buffer callback timed out, then an output
inventory showed that the default viewport requested only LDR. Explicitly
adding a native `HdrColor` RenderVar to the isolated product resolved this.
The installed utility version was **2.1.0**, and its callback supplied
`TextureFormat.RGBA16_SFLOAT`. The callback copied the SDK-owned buffer before
returning and retained an EXR plus a float32 NPZ representation of those
half-precision samples. NVIDIA's [viewport capture API](https://docs.omniverse.nvidia.com/kit/docs/omni.kit.viewport.utility/2.1.2/USAGE_PYTHON.html)
documents the HDR capture route; the actual installed signatures and output
were checked locally.

The early exports also showed product fog=true despite the requested legacy
global fog=false. M3 therefore explicitly authored and checked the registered
USD camera/product controls. NVIDIA describes these per-prim controls and
their synchronization with deprecated global settings in the
[RTX schema documentation](https://docs.omniverse.nvidia.com/kit/docs/omni.usd.schema.render_settings.rtx/1.0.1/index.html).
This finding does not change M2's measured geometric displacement, but its
global-setting record must not be used as proof of unclamped radiometry.

The bright target then exposed a second issue: firefly filtering clipped its
luminance, making blue increase while red decreased in absorption-only
comparisons. The installed effective controls included native intensity
limits of 3200. In the .75 m PathTracing probe, disabling the filter increased
the clear target HDR from approximately 2.77 to 11099.8. The absorption case
then measured approximately (7576.7,9390.0,10246.5), with all channel ratios
below one. This intervention established the clipping cause; the early
clamped images were excluded from attenuation acceptance.

The real-time mode's early scattering changes were insufficient on their own
to establish volume-light redistribution. PathTracing supplied that evidence
and was selected for the M3 preset. This does not claim that every real-time
configuration lacks scattering. NVIDIA also documents
[renderer-dependent differences in volume effects](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/rtx-renderer_rt_overview.html).

## Shader coupling and units

NVIDIA's [transmission documentation](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/templates/parameters/OmniSurface_Transmission.html)
describes scale-dependent transmission colour/depth and scattering controls.
The inspected installed implementation was more specific than treating the
scatter RGB slider as an independent measured coefficient.

Let C be the transmission RGB, S the native scattering RGB, d the authored
depth and u the MDL scene-unit conversion. The installed implementation used
the physical reference distance u·d and computed extinction componentwise as
`-ln(C/(1+max(S)))/(u*d)`. A nonlinear albedo function of C·S then divided that
extinction into absorption and scattering. Increasing S therefore changed
both total extinction and its split. The JSON preset records the resulting
model coefficients separately from measured image signals. They were derived
from this shader formula, not fitted to images or measured seawater.

The known-distance test kept a .75 m path and identical physical geometry:

| Metres/unit | Native depth | HDR signal / same-unit clear control (R,G,B) |
|---:|---:|---|
| 0.01 | 100 | (0.682267, 0.845750, 0.922831) |
| 1 | 1 | (0.681369, 0.846289, 0.923958) |
| 1 | 100 | (0.996382, 0.998302, 0.999200) |

The compensated pair differed by at most **0.132%**, below the predeclared
3% equivalence tolerance. The uncompensated case was almost clear. Thus, for
this installed shader/renderer, author
`native_depth = reference_distance_m / metres_per_scene_unit`: a 1 m reference
distance required depth100 in MARLIN's .01 m stage. The live MARLIN world was
never rescaled. This check validated distance interpretation, not a scientific
classification of the chosen water.

## Measurement and final results

All ROIs used full-resolution top-left, half-open pixel indexing:
target x248:264/y184:200, backgrounds x190:206 and x306:322/y184:200.
The fixed target ROI lay inside the smallest/deepest target; the background
ROIs lay outside its boundary. The annotated full-frame check and comparison
crops were inspected. Measurements reported RGB means, T−B signal,
Michelson contrast `(T-B)/(T+B)`, and signal relative to the same-depth clear
control. The NPZ float arrays were used directly, with no gamma or display
transform. Native HDR values are renderer units, not calibrated radiance.

The native SDK PNGs saturated the bright fiducial and were retained as display
outputs. They were not used to infer absorption. Figures used the identical
declared preview transform `clip(HDR/12000,0,1)^(1/2.2)` in every condition;
there was no per-image exposure normalization or local darkening. Changing
the effective tone-map operator changed PNG values while the HDR target
signal changed only **0.0082%**, supporting use of the pre-display AOV.

Absorption was introduced first with C=(.6,.8,.9), S=0 and distances50/100/200
at all three depths. The middle distance100 candidate yielded:

| Physical depth | Relative red signal | Relative green signal | Relative blue signal |
|---:|---:|---:|---:|
| 0.25 m | 0.88028 | 0.94578 | 0.97368 |
| 0.75 m | 0.68227 | 0.84575 | 0.92283 |
| 1.25 m | 0.52891 | 0.75686 | 0.87495 |

Across all nine absorption cases, the largest relative difference from the
simple nadir Beer–Lambert prediction was **0.355%**. This was an additional
model-consistency diagnostic; the formal depth/parameter effect and
repeat/unit criteria used the predeclared 3% threshold. The clear .75 m repeat
signal differed by **0.0374%**.

Scattering was then varied separately at the fixed C and distance100. Both
S=(.02,.02,.02) and (.05,.05,.05) produced light in the background and a
spatial halo, as well as signal/contrast changes. For the selected lower S:

| Depth | Signal/clear R,G,B | Background red HDR | Red Michelson contrast |
|---:|---|---:|---:|
| 0.25 m | (.87786,.94243,.97078) | 3.4278 | .999297 |
| 0.75 m | (.67361,.83445,.91168) | 4.5180 | .998793 |
| 1.25 m | (.51707,.73909,.85715) | 3.1020 | .998920 |

Absorption-only background red was approximately .0062–.0064. The several-
hundred-fold background increase and visible redistribution exceeded the
declared effect threshold. Both .75 m scattering repeats matched the target
ROI mean at the retained sample precision; this is not a claim of bitwise
determinism for all images. The higher S was retained as a diagnostic, not a
second scientifically named preset.

Background brightness was not monotonically increasing with target depth.
The target remained a light source at different heights within a fixed
environment; scattered light followed multiple paths. Neither individual
pixels nor background means were required to obey a single-path attenuation
law. Coefficient fitting from scattering images would require a more complete
transport/measurement model.

## Selected engineering preset

`engineering_medium_v1.json` selected C=(.6,.8,.9), native distance100 at
.01 m/unit, S=(.02,.02,.02), anisotropy 0, IOR 1.333, roughness .001,
transmission 1, base weight 0 and thin-walled=false. These are engineering
conditions. The model-derived per-metre coefficient triples were:

- Extinction: (.530628,.242946,.125163).
- Absorption: (.470494,.207011,.104555).
- Scattering: (.060134,.035935,.020609).

The material required the tested closed medium and unclamped PathTracing
configuration. It was not applied blindly to the current open, thin-walled
ocean. The native scatter slider has no calibrated turbidity/field-water unit.

## Resources, regressions and restoration

The tested host had an **RTX A2000, 6138 MiB**, driver 595.91.07. The 26 final
requests all succeeded, taking 278.4 seconds total, 9.68–12.41 seconds each
(median 10.36). One-second polling supplied 275 GPU observations: peak-observed
used memory 4779 MiB, minimum-observed free memory 1019 MiB. The 768 MiB guard was never
bypassed and did not block a final request. These are sampled observations,
not a continuously measured hardware peak. No Kit restart or ray/sample
budget increase was required.

Each capture waited 64 delivered rendered frames. Configured sampling limits
and denoising controls are preserved in effective settings, but an exact
integrated sample count was not measured. Existing viewport-menu callbacks
still emitted `None.get_stage` errors after destroyed temporary contexts;
these vendor cleanup diagnostics were retained, with no vendor patch.

Sixteen offline tests passed; two general USD camera tests were skipped
because the host Python lacked pxr. The live Kit runs independently executed
native USD target-bound/projection checks, and all 26 final geometry, camera,
PNG, EXR-header, HDR-array and effective-control validations passed. Invalid
depths and arbitrary output paths were rejected with HTTP 422.

All **72 M1 and 139 M2 pinned evidence files** retained their hashes. The
production ocean/material authoring and wave/controller modules were
unchanged. The pre-work checkpoint was restored, the original marine setup
reconstructed with swimming disabled, and the original material binding and
values matched exactly. All 73 recorded legacy renderer settings, camera,
1280×720 live resolution and display options were preserved. Source hot
reload stopped controllers during development; the existing ocean/chase
controllers were reconstructed. Their earlier procedural phase was not
claimed restored.

## Limits and next milestone

M3 validated relative medium appearance and distance in a small flat fixture,
not measured seawater or the animated ocean. HDR comparisons do not establish
absolute radiometric calibration or a complete spectral transport model.
The additional +1-stop camera probe did not change either saved output in
this installed path, so independent exposure calibration was not claimed;
M5 must resolve the effective exposure mapping when qualifying production
captures. All medium comparisons used the same authored exposure controls.

M4 must integrate the opt-in candidate with the existing animated surface and
any minimal required enclosure while preserving the surface sampler and
animal controllers. M5 still owns production capture repeat/reload and larger
resource qualification. Those milestones were not marked complete by M3.
