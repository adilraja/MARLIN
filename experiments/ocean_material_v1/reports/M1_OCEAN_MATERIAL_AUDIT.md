# M1 — Current ocean material audit and preserved baseline

Date: 29 October 2026. Status: **completed audit/baseline scope with recorded limitations**.
No candidate water material has been implemented or accepted. Optical performance,
physical shader-distance calibration and biological visibility remain unvalidated.

## Baseline identity and preservation

The initial outside-sandbox probes found no Kit process and no service listening
on localhost:8011. This baseline is therefore a **fresh reconstruction using the
existing marine-setup implementation**, not recovery of the old GAMA scene.
The existing setup used `start_swimming=false`; its existing ocean, environment,
asset and camera code supplied all other settings. No production source changed.

Accepted appearance baseline: `../baseline/frozen_02/`. It contains the complete
sampled `scene.usdc`, checkpoint metadata, binding/status records, renderer/water
settings, captures and measured repeatability. The exact accepted camera, lights,
animal transforms and wave geometry are recoverable from that frozen scene.
External USD/MDL dependencies must remain available. Never overwrite these files
with later candidate evidence.

The initial audit's `../baseline/scene.usda` and `material.json` are retained
diagnostic evidence from an earlier sampled wave phase. Do not substitute that
scene for the accepted capture checkpoint. Binding/parameter values were checked
again independently in `frozen_02/material_before.json` and `material_after.json`.

## Effective material and geometry

Live binding resolution identified `/World/Ocean.material:binding`, targeting
`/World/Looks/OceanWater`. No competing binding was reported on its ancestors.
The material's MDL surface output connects to `OceanWater/Shader.outputs:out`.
The shader uses `sourceAsset`, `OmniSurface.mdl`, subidentifier `OmniSurface`.
USD resolved the module to the installed Kit kernel's `mdl/core/Base/OmniSurface.mdl`.

Only that live-resolved module was inspected, read-only, as permitted by the
sprint's targeted installed-definition audit. No recursive runtime/cache scan or
vendor edit was performed. Its SHA-256, actual declarations/defaults and matches
for all **14 authored inputs** are in `installed_material_definition.json`.
The MDL wrapper imports OmniSurfaceBase. Its deeper implementation/distance scaling
has not been independently inspected or measured; no alternative import path is
claimed merely because a guessed location exists in documentation.

The ocean is an open, double-sided, right-handed quad mesh: **16,641 vertices,
16,384 faces and 512 boundary edges**, with no nonmanifold edges in the audit.
Authored vertex normals faced generally +Y (sampled normal Y: 0.9461–1.0000).
The world transform was identity. No closed water interior was established.
Bounds for the accepted frozen phase are recorded in `frozen_02/inspection.json`;
the earlier diagnostic's bounds belong to its own sampled phase.

| Existing control | Authored shader input | Effective authored value | Interpretation |
| --- | --- | --- | --- |
| Reflection | `specular_reflection_weight`, `specular_reflection_color` | 1, white | Dimensionless weight/RGB |
| Roughness | `specular_reflection_roughness` | 0.045 | Dimensionless; API range 0–1 |
| Index | `specular_reflection_ior` | 1.333 | Dimensionless engineering value; not newly calibrated |
| Transmission switch/weight | `enable_specular_transmission`, `specular_transmission_weight` | true, 1 | Supported installed inputs; appearance is not proof of refraction |
| Transmission colour | `specular_transmission_color` | (0.78, 0.92, 0.95) | RGB engineering value |
| Medium depth control | `specular_transmission_scattering_depth` | 100 | Native shader float; physical conversion unverified |
| Scatter colour | `specular_transmission_scattering_color` | (0.005, 0.02, 0.03) | RGB control; not measured turbidity |
| Scatter anisotropy | `specular_transmission_scatter_anisotropy` | 0 | Dimensionless; API range −1–1 |
| Shell mode | `thin_walled` | true | Installed definition describes a surface with no interior |
| Base contribution | `diffuse_reflection_weight`, `diffuse_reflection_color` | 0.02, (0.02, 0.10, 0.13) | Existing nonzero diffuse contribution |
| Metalness | `metalness` | 0 | Dimensionless |

Float32 values and exact types are retained in the JSON, rather than replaced by
rounded display values. There are no authored cutout-opacity overrides in this
shader. The inspected installed defaults are `enable_opacity=false`,
`geometry_opacity=1.0`, and an empty opacity texture. Thus no new alpha-opacity
workaround was introduced by this audit. MDL resolution and visible rendering do
not by themselves establish every backend capability or absence of internal fallback.

## Units and the unresolved medium question

The stage **explicitly authors 0.01 metres per unit and Y-up**. The existing
marine setup requests a 16,000-unit-wide ocean, 128 subdivisions per side and
40-unit wave height. The shader receives the depth value 100 directly, without
Python-side unit conversion. Metadata length conversion would make 100 scene
units one metre, but **this is not evidence that the shader depth parameter is
interpreted as one metre**. That interpretation needs an installed implementation
or known-distance diagnostic. The present open thin-walled mesh does not establish
a finite medium path at all. These are recorded baseline deficiencies for M2/M3,
not a reason to claim absorption or refraction passed in M1.

The existing underwater height-fog cue was enabled. Its exact settings are in
the checkpoint. The baseline image therefore combines surface shading with that
pre-existing cue; apparent blue attenuation must not be attributed solely to the
water material. Later isolated tests must control this confound explicitly.

## Saved captures, camera and repeatability

The initial 512 × 384 audit stopped at the existing metric-projection helper:
camera aperture 20.955 × 15.2908 did not match the requested image aspect.
No calibration change or projection-helper patch was made. Plan version 2 was
recorded before accepted captures, retaining the original failure and plan.

The appearance baseline uses the existing **1280 × 720** viewport and
`/World/Cameras/DolphinChaseCamera`. Its raw camera definition and composed pose
are frozen in the accepted USD. **Conformed viewport projection is not validated**;
these images are not metric camera/refraction evidence. M2 must deliberately use
compatible diagnostic geometry instead of silently treating them as calibrated.

The existing `capture_viewport_to_file` path saved one warm-up and three retained
PNGs. A client-side disk-commit wait was needed because the existing diagnostic
endpoint could return its path before the file appeared. Saved dimensions and a
fresh complete PNG were verified. No source capture service was changed.

The predeclared saved-RGB limits were mean absolute error ≤1 code value and
99th-percentile absolute difference ≤8 code values (equivalent to 1/255 and 8/255).

| Retained pair | Mean absolute RGB difference | p99 difference | Maximum difference | Result |
| --- | ---: | ---: | ---: | --- |
| 01–02 | 0.4594 | 6 | 66 | Passed |
| 01–03 | 0.5195 | 7 | 68 | Passed |
| 02–03 | 0.1999 | 3 | 25 | Passed |

This establishes bounded **display-domain** repeatability, not identical pixels
or linear radiometry. The maximum differences remain reported even though the
acceptance rule uses mean and p99. No target/background optical contrast or
absorption coefficient has been inferred from these baseline images.

## Runtime, resources and rollback

The tested GPU is an **NVIDIA RTX A2000, 6,138 MiB**, driver **595.91.07**.
The live-resolved material belongs to Kit kernel 110.2.0+feature; extension startup
versions are retained in `runtime_versions.json`. The actual renderer setting is
`RealTimePathTracing`; no broader fidelity claim is inferred from that name.
All **73 recorded renderer/cue settings** are retained in the checkpoint, including
tone mapping, exposure, AA, ray budgets, caches and colour processing. Configured
settings and update counts are not measured sample counts.

Initial free memory was about 4,416 MiB. During the retained capture sequence,
free memory was 1,906–1,942 MiB; the highest observed used-memory sample was
3,893 MiB. These are observations, not a continuously sampled peak. Final observed
free memory after live restoration was 2,022 MiB. Startup required 2,048 MiB free;
each capture required the existing **768 MiB** guard. No guard was disabled.
Retained capture calls including disk completion took approximately 0.166–0.225 s.

Two checkpoint restorations executed successfully; material and water/fog status
matched before/after. Following restoration of the original marine configuration,
all **73 renderer settings** matched the baseline using the existing `same_settings`
comparison. See `qa/full_settings_restoration.json` and `ROLLBACK.md`.
Exact procedural/controller history is not checkpointed and is not claimed restored.
Kit remains running with the original marine setup, ocean animation and chase
camera restored, with the dolphin's swimming disabled as in this reconstructed baseline.

One Kit-only restart was used after the initial starter-stage refusal; no further
restart or runtime upgrade was used. The pre-existing asset converter/importer
startup failures were preserved and were not repaired. Existing USD assets loaded.

## Verification and milestone boundary

- All nine pinned production source files were unchanged.
- Four existing water-material tests and five renderer-snapshot tests passed.
- All **4,859 inputs in the previous engineering closeout seal** still matched.
- Failed startup/audit/capture-client attempts remain retained, with their reasons.
- No candidate shader, new wave model, animal material change, dataset or ML run occurred.
- No human approval has been inferred.

M1 provides the reversible appearance baseline and acceptance plan. It does not
establish physical shader-distance units, finite-medium correctness, validated
refraction or full metric camera conformance. These must be resolved in their
controlled diagnostics before any corresponding later milestone can pass.

Official execution reference used: [NVIDIA Kit scripting](https://docs.omniverse.nvidia.com/kit/docs/kit-manual/110.1.5/guide/python_scripting.html).
It documents the local `--exec` route; the actual tested runtime evidence above
is local. No generic remote code-execution endpoint was introduced.
