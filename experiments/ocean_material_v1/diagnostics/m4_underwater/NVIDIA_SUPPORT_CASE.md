# Draft: primary rays starting inside a closed MDL water medium

Prepared locally; not submitted or sent externally.

## Environment and question

Existing Omniverse Kit 110.2.0 application, Linux/Vulkan, RTX A2000 6138 MiB,
driver 595.91.07, PathTracing. Is there a supported mechanism in this build to
initialise a camera's primary ray with the optical properties of its enclosing
closed MDL medium? If a spatial volume is required, which installed NVIDIA
representation supports inside-camera transport while retaining a refractive
animated water interface?

## Reproduction

1. Open the supplied frozen USD from a flat-enclosure capture and select
   `/World/MarlinOceanIntegrationDiagnostic/Camera`.
2. Use its retained `effective_settings.json` and matrices: 512×384, PathTracing,
   fog off, firefly filtering off, camera auto exposure off; settle 64 delivered
   frames. Preserve the recorded exposure and ray controls.
3. The closed water boundary has top Y=0, bottom Y=-3 m, X=10..14 m and Z=-2..2 m.
   Y is up; stage `metersPerUnit` is .01. Its outward normals and closure were
   validated. White emissive target: Y=-1 m. Inside camera: (12,-.5,0) m,
   looking downward. Above control camera: (12,3,0) m.
4. Compare clear and engineering-water scenes below. Each frozen file includes
   the exact captured geometry and material. Original MARLIN scene content is
   also retained; referenced marine assets and installed MDL dependencies are
   not bundled separately. This is a bounded flat-fixture reproduction within
   the application, not an assertion that the exported file is self-contained.
5. Read native HdrColor, not the saturated display PNG. Fixed centre ROI:
   rows [184,200), columns [248,264).

| Case | Frozen scene | Observed centre HDR RGB |
|---|---|---|
| Selected medium, inside | `captures/inside_133t5ycr/scene.usdc` | (11336,11336,11336) |
| Clear control, inside | `captures/inside_jtlb1lf0/scene.usdc` | (11336,11336,11336) |
| Selected medium, above | `captures/nadir_4vfjbu3t/scene.usdc` | (6575.8,8749.5,9852.6) |
| Clear control, above | `captures/nadir_bzmkgh2g/scene.usdc` | (11112.8,11112.8,11121.8) |

The expected inside result has path-dependent chromatic attenuation. The
engineering preset uses OmniSurface, IOR 1.333, roughness .001, transmission 1,
transmission colour (.6,.8,.9), native reference depth 100, scattering (.02,.02,.02),
anisotropy 0 and `thin_walled=false`. Its original M3 distance interpretation
was checked against known-size geometry. The clear control changes transmission
colour to white and scattering to zero.

## Controls already tried

The curved original enclosure and a flat nine-face enclosure both failed from
inside. USD sidedness, MDL volume-output connection, the registered native
non-uniform-volume flag (both Carbonite and RenderProduct scopes), and disabled
native radiance/light caches did not resolve it. Installed
`OmniVolumePerlinNoise` probes with uniform and varying endpoints also stayed
neutral from inside, while a varying-density probe attenuated from above.
Those procedural probes were diagnostics with different interfaces, not
accepted replacements for the selected water material.

The symptom persisted after a checkpointed app restart with successful GPU
preflight. Every successful capture retained native HDR/EXR, effective controls,
scene hash and restoration checks. No cutout-opacity workaround or camera
shell was used. See `qa/probe_validation.json`, `qa/native_medium_capabilities.json`,
`qa/native_medium_settings.json`, and the sealed restart log snapshots.

These observations suggest missing initial-medium state for primary rays in
this tested path. Please confirm the supported API or representation rather
than treating that inference as a proven universal renderer limitation.
