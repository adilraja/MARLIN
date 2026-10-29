# MARLIN — Ocean Material and Underwater Appearance

## Codex sprint specification

| Field | Value |
|---|---|
| Document version | 1.0 — proposed execution specification |
| Project | Existing MARLIN NVIDIA Omniverse Kit application |
| Repository | `/home/madil/kit-app-template` |
| Sprint focus | Water material, its medium representation, and its behaviour in saved captures |
| Basis | The agreed six-milestone material-first plan in the project discussion |
| Status | Implementation instructions, not a record of completed work or scientific acceptance |
| Primary deliverable | One versioned, configurable ocean-water preset with diagnostic evidence, capture settings, dependencies and a rollback procedure |

> **Sprint objective:** Improve MARLIN's water reflection, transmission, refraction and depth-dependent appearance while preserving the existing wave simulation, animal controllers, camera geometry and capture pipeline.

This is a material-first sprint. Controlled images are diagnostic evidence for the material; building a real-survey reference collection, a new wildlife dataset or a new annotation system is not a prerequisite.

---

## 1. Scope and working principles

Continue the existing application. Do not rebuild MARLIN, duplicate its material/capture services, or assume that an earlier material implementation is still active.

Read the applicable repository instructions and inspect the current implementation before editing it. The canonical runtime source is under:

```text
source/apps/
source/extensions/cris.madil.render_service/
```

Locate the current ocean-generation, material-binding, surface-sampling and capture code. Reuse its supported configuration mechanisms. The paths and output names suggested below may be adapted to existing repository conventions; document any adaptation.

### In scope

- Inspecting the material actually bound to the ocean and its effective parameters.
- Demonstrating reflection and transmission/refraction in a small controlled scene.
- Establishing an explicit water-interior representation where the material requires one.
- Configuring absorption and scattering, with documented units and limitations.
- Applying the working material to the existing animated ocean.
- Testing the actual saved-image capture path, reload behaviour and resource requirements.
- Demonstrating the result with one existing animal whose own materials and pose are held fixed.

### Out of scope

Do not introduce a replacement wave model, FFT ocean, fluid solver, broad weather randomisation, foam system, new GAMA behaviours, pods, flocks, animal rigs, new species, new camera profiles, a large dataset, or detector training.

Do not migrate the entire stage to metres, redesign annotations, or change animal materials during this sprint. Do not make native-resolution HiDef or Sony capture a prerequisite.

Keep the existing marine demonstration, GAMA bridge and completed experiments intact. Never overwrite accepted historical images, labels, predictions, results or manifests in order to demonstrate an improvement.

### Geometry exception: only what the material needs

A small bounded water volume is permitted for diagnostics. A minimal render-side enclosure or medium boundary may also be added if necessary for the installed renderer's water representation.

This is not permission to replace the ocean simulator. Any added boundary must use the existing surface consistently, avoid duplicate interfaces, and leave the wave equations and animal surface-sampling contract unchanged. Record its dimensions, normals, ownership and assumptions. If integration requires a major geometry redesign, report that dependency rather than expanding the sprint silently.

---

## 2. Material-selection and evidence rules

OmniSurface is a candidate, not an unconditional requirement. NVIDIA documents water-capable surface and interior controls in the OmniSurface family, but the actual shader variant, available inputs and renderer support must be established in the installed application.[^nvidia-material]

Do not assume that the current ocean still uses `UsdPreviewSurface`, or that replacing a shader alone will solve the problem. Do not invent MDL module paths, material identifiers, parameter names or renderer settings. Inspect the local implementation and check version-compatible documentation.

NVIDIA distinguishes geometry opacity from specular transmission.[^nvidia-transmission] Consequently, **reducing cutout/geometry opacity is not an acceptable substitute for demonstrating water transmission and refraction**. Preserve a fully present interface in the physical-water candidate; any separate opacity diagnostic must be labelled as a control.

Use the smallest supported material solution that satisfies the tests. Do not upgrade Kit, replace vendor binaries or reinstall the environment merely to obtain a preferred template. An unsupported capability is a documented limitation, not a reason to claim that a fallback is equivalent.

### Units and configuration

Inspect stage unit metadata, parent transforms, actual object dimensions and the material's distance interpretation. Do not assume that one scene unit is one metre or copy a historical `scale=100` convention without verification.

NVIDIA documents transmission depth as scale-dependent.[^nvidia-transmission] Record the conversion between physical diagnostic dimensions and shader/scene values, and check it with known-size geometry. Do not assume that a stage metadata field automatically rescales every shader input.

Keep the configuration small. It should identify the material and supported controls for reflection/roughness, refractive index, transmission, medium colour/distance, scattering and any optional normal detail. For every control, record its actual installed shader input, type, units or dimensionless interpretation, constraints and effective value.

Presets may be described as **engineering** or **appearance-oriented**. Do not label a scattering slider as measured turbidity or assign field units without a documented calibration.

---

## Milestone 1 — Audit the current water material and preserve a baseline

### Objective

Establish what the application actually renders and make every subsequent change reversible.

### Required work

1. Inspect the effective ocean material binding, including inherited bindings, overrides, shader connections, opacity/transmission settings and unresolved assets. Record the geometry, normals, relevant transforms and whether a water interior is represented.
2. Record the installed Kit/material versions, renderer mode and important capture settings. Identify the actual GPU and available memory; do not assume a previously discussed upgrade has happened.
3. Record camera intrinsics/extrinsics, output dimensions, exposure, colour processing, lights, ocean state and unit convention. Preserve a small fixed set of baseline captures and their manifests.
4. Save a restorable copy or isolated layer for the original water material and any render settings that will be changed. Keep historical experiment packages unchanged.
5. Write a bounded test plan identifying comparison conditions, numerical tolerances, memory safeguards and criteria for accepting the material. Where numerical tolerances require baseline measurements, establish them before testing the candidate, not after seeing its result.

Prefer application diagnostics to broad filesystem searches. If an installed runtime definition must be examined, use targeted read-only inspection of that component. Do not recursively scan the generated runtime or edit `_build/`, extension caches, bytecode or vendor files.

### Deliverables

```text
M1_OCEAN_MATERIAL_AUDIT.md
baseline configuration and captures
baseline manifest
acceptance plan
rollback instructions
```

### Acceptance criteria

- The bound material and its effective settings are identified, not guessed from an old function name.
- The current stage-unit and material-distance conventions are recorded.
- Baseline images are tied to exact scene/camera/render settings.
- A rollback can restore the original material and affected settings.
- No production behaviour has been changed merely to complete the audit.

**Proceed only after the baseline and test plan are recorded.** A conflict requiring broader architectural changes must be surfaced before implementation.

---

## Milestone 2 — Demonstrate transmission and refraction in a small test scene

### Objective

Prove the essential water behaviour without wildlife, waves or a large ocean obscuring the diagnosis.

### Required work

1. Create a small isolated diagnostic scene with a flat water interface, known-size checkerboard or fiducial target, and simple objects at declared positions. Freeze the lighting, camera, exposure and target geometry. Start without normal-map detail or animated waves.
2. Establish a valid medium representation for the selected material and renderer. For a finite-volume test, check boundary orientation, closure and target placement inside the intended medium. Do not treat an arbitrary open plane as a verified volume.
3. Implement clear-water transmission using supported material inputs. Record the chosen refractive indices and their provenance or engineering-assumption status.
4. Capture a no-water control and the water candidate from a nadir and an oblique diagnostic view. An index-matched control may also be used. At least one view must expose a measurable refractive displacement, not just a colour or alpha change.
5. Compare the oblique displacement with a simple planar-interface geometric prediction or an existing validated refraction diagnostic. Record the geometry, measurement, tolerance and result. Also inspect reflection against a fixed, recognisable environment.
6. If the material appears black or unexpectedly opaque, diagnose binding, normals, medium boundaries, unsupported settings and ray budgets before changing multiple parameters. Any budget adjustment must remain within the declared resource limits.

Thin-walled and finite-medium behaviour are not interchangeable: NVIDIA documents thin-walled surfaces as shells whose transmission does not enter a normal solid interior.[^nvidia-geometry] The chosen setting must match the declared diagnostic geometry.

### Deliverables

```text
M2_TRANSMISSION_REFRACTION.md
minimal diagnostic scene and launch/capture procedure
material parameter record
control/candidate images and geometric comparison
```

### Acceptance criteria

- Submerged diagnostic objects are observable through the declared clear-water candidate.
- At least one controlled comparison demonstrates refraction, with a documented geometric check.
- Reflection and transmission are produced by the selected material path, not by hidden-object changes or reduced cutout opacity.
- The shader loads without an unreported fallback or missing dependency.
- The test can be reconstructed without manually repairing its settings.

A transparent-looking blue sheet alone does not satisfy this milestone.

---

## Milestone 3 — Add controlled absorption and underwater clarity

### Objective

Establish configurable underwater attenuation and scattering with a clear interpretation of distance.

### Required work

1. Retain the M2 clear-water result as a control. Introduce absorption first, then test scattering separately. Document any coupling imposed by the installed shader rather than assuming independent physical coefficients.
2. Use one diagnostic target at at least three declared depths, with all other relevant conditions fixed. Select depths appropriate to the test geometry and resources; they are engineering conditions, not species-behaviour assumptions.
3. Record both physical distances and authored shader/scene values. Use a known-distance check to confirm the adopted unit interpretation without rescaling the MARLIN world.
4. Capture a small parameter sweep around a selected candidate. Record target/background contrast and channel changes using a fixed measurement procedure. State the image colour domain; prefer retained linear data for attenuation measurements where supported.
5. Explain the observations and limits. Do not interpret every change in tone-mapped brightness as a direct absorption coefficient, or require every rendered pixel to become monotonically darker with depth.
6. Select one baseline engineering water-medium preset. Keep other settings as diagnostics, not as an unreviewed library of scientifically named water types.

Absorption and scattering controls must not be replaced by depth-triggered object hiding, target-opacity changes, arbitrary background darkening or post-processing that makes missing targets appear plausible.

### Deliverables

```text
M3_UNDERWATER_APPEARANCE.md
controlled depth/parameter comparisons
unit-conversion and measurement notes
candidate medium preset
```

### Acceptance criteria

- The diagnostic comparisons establish interpretable attenuation and scattering behaviour under the declared conditions.
- Units and parameter coupling are documented; changes are not unexplained slider adjustments.
- No animal geometry, camera calibration or target visibility flags are manipulated to manufacture the effect.
- Unsupported scattering or medium behaviour is explicitly reported. A clear-water-only fallback is partial completion, not completion of the full material objective.
- The chosen values remain labelled engineering assumptions unless measured-water evidence supports stronger claims.

---

## Milestone 4 — Apply the material to the existing animated ocean

### Objective

Transfer the working water material to MARLIN while preserving the simulation surface and existing application behaviour.

### Required work

1. Apply the candidate through the current material-binding/configuration route. Preserve the old material as a selectable fallback, with no destructive replacement of source assets.
2. Test on the existing ocean with animation initially frozen. Check normals, bounds, duplicate surfaces, medium entry/exit and unintended visibility of sides or bottom. Then enable the existing wave animation and repeat the inspection.
3. Where an enclosure is required, couple its render-side boundary to the existing top surface without changing the physical surface sampler. Check for gaps, self-intersections and duplicate coplanar interfaces across the tested wave phases.
4. Verify that surface heights and existing animal depth/following behaviour have not changed because of the material integration. Reuse relevant regression checks instead of writing a second simulation implementation.
5. Only after the main material works, consider optional fine normal detail. Record its physical scale, strength, dependencies and animation phase. It must be switchable off and freezeable. Do not add material displacement or a second independently animated wave system.
6. Keep the new preset opt-in during development. Existing scene-setup routes must not unexpectedly overwrite the chosen preset or alter historical experiment configurations.

NVIDIA documents normal mapping separately from displacement.[^nvidia-geometry] Optional normal detail here is a rendering addition, not a claim that animals interact with a newly simulated physical ripple surface.

### Deliverables

```text
M4_ANIMATED_OCEAN_INTEGRATION.md
integrated material preset and binding code/configuration
frozen and animated diagnostic captures
surface-sampler/controller regression evidence
```

### Acceptance criteria

- The material remains bound and renders correctly on the tested animated surface.
- Existing wave equations, shared surface sampling and animal controllers remain unchanged in behaviour.
- Added geometry, if any, is minimal and its boundaries/assumptions are documented.
- Fine-detail phase can be frozen for reproducible captures; optional detail is not a blocker to the core sprint.
- The original material can still be restored.

---

## Milestone 5 — Verify saved-image rendering and resource requirements

### Objective

Establish a supported capture configuration rather than relying on a convincing viewport preview.

### Required work

1. Use the same capture service or SDK route used by MARLIN experiments. Verify the saved image's dimensions, camera transform and configuration independently of the viewport window size.
2. Record the actual installed renderer mode and relevant ray budgets, denoising, temporal reconstruction, accumulation, exposure and colour settings. Do not rename a legacy renderer as Real-Time 2.0 or assume a feature exists because it appears in current online documentation.
3. Where available and affordable, compare one small diagnostic scene in RTX Interactive/path-traced mode with the selected production mode. Treat this as a diagnostic comparison, not proof that the modes should produce identical pixels.
4. Repeat a frozen scene/camera capture and a save/reload capture using the acceptance plan. Reset or settle temporal rendering state by a documented procedure. Measure observed image differences separately from scene-state equality.
5. Measure available and peak-observed GPU memory, elapsed capture time, failures and cleanup behaviour. Keep the workload bounded and use the installed memory safeguards. Report configured sample counts separately from actually measured counts.
6. If a supported mode fails on the current hardware, preserve the failed attempt and narrow subsequent diagnostics explicitly. Do not silently lower output size, alter camera sampling, remove the medium, or disable a required effect while claiming the same test passed.

NVIDIA cautions that effects including volume rendering can differ between Real-Time 2.0 and Interactive modes.[^nvidia-renderer] The final preset must therefore state the renderer and configuration under which its behaviour was tested.

### Deliverables

```text
M5_CAPTURE_AND_RESOURCES.md
validated capture settings
repeat/reload comparison results
resource and failure log
```

### Acceptance criteria

- The material works in actual saved captures with verified dimensions and camera settings.
- Repeatability is reported against predeclared tolerances, not asserted from matching state hashes alone.
- Resource measurements identify the actual tested host and configuration.
- Necessary restarts and their effect on animation/render history are documented; restart success is not described as a permanent memory fix.
- Full native HiDef/Sony capture remains outside the acceptance requirement.

If only the diagnostic renderer works while the intended experimental capture route does not, report partial completion and the precise blocker.

---

## Milestone 6 — Freeze the preset and demonstrate it with one existing animal

### Objective

Package the water improvement as a reproducible, reversible application change.

### Required work

1. Use one existing porpoise or dolphin. Keep its mesh, scale, material, anatomical pose and orientation unchanged. Freeze its controller for the comparisons; do not begin an animal-material or rigging task.
2. Capture it above, intersecting and below the water using the old and new water materials. For each before/after pair, preserve the same camera, lights, animal transform, ocean state and render settings wherever compatible. List any unavoidable renderer differences rather than attributing them solely to the material.
3. Record any material-dependent discrepancy between direct projected annotation geometry and the refracted visible appearance. Keep existing annotation definitions intact; do not relabel old boxes or claim visible-mask validation.
4. Save one versioned baseline preset, its material assets, texture/MDL dependencies, geometry requirements and supported capture configuration. Check reload in a fresh stage or process at least once within the accepted resource budget.
5. Run relevant existing camera, ocean, controller, capture and restoration regressions. Demonstrate rollback to the original material and restoration of the standard marine scene.
6. Produce a closeout with commands, outputs and comparison images. Obtain a named human review of the demonstrated material change, distinguishing engineering acceptance from claims about real seawater or wildlife-survey validity.

### Deliverables

```text
versioned ocean-water preset
OCEAN_MATERIAL_SPRINT_CLOSEOUT.md
reproduction and rollback instructions
before/after images and dependency manifest
regression and review evidence
```

### Acceptance criteria

- The new material survives capture, save/reload and the tested animated-ocean use.
- The same animal is used for material-only comparisons; improvements to the animal itself are not falsely attributed to the water.
- Dependencies and effective parameters are recoverable without manual retuning.
- Existing MARLIN functions and prior experiment records remain intact.
- The closeout states the demonstrated improvements and remaining limitations without claiming biological, optical or operational field validation.

**Stop after this milestone and report. Do not automatically generate a dataset or begin ML training.**

---

## 3. Suggested output organisation

Use an isolated output root, adapting to the repository's existing conventions:

```text
experiments/ocean_material_v1/
    specification.md
    baseline/
    diagnostics/
    presets/
    captures/
    qa/
    reports/
    manifest.json
    OCEAN_MATERIAL_SPRINT_CLOSEOUT.md
```

Production code belongs in the existing source modules or a small appropriate helper, not in generated runtime directories. Reuse the current HTTP/configuration interfaces; add only the validated inputs necessary for this material. Do not introduce arbitrary code-execution endpoints.

Each accepted comparison should retain enough information to identify:

```text
run ID and source commit / tracked changes
scene and material preset versions
resolved scene-state and camera configuration
stage units and material-distance conversion
animal/diagnostic target transforms
wave and optional normal-detail phases
lights, exposure and colour processing
renderer mode and effective settings
image dimensions and capture route
runtime versions and actual hardware
resource measurements and result status
output paths, hashes and dependency versions
```

Matching scene hashes demonstrates state preservation. Image equivalence requires a separate image comparison. If settings or dependencies cannot be recovered, record that limitation rather than filling in plausible values.

---

## 4. Failure handling and acceptance discipline

- Agree or record numerical tolerances before acceptance runs. Keep diagnostics separate from accepted evidence.
- Preserve failed attempts, logs and original statuses. A later successful attempt does not rewrite an earlier failure.
- Do not use automatic exposure, unexplained renderer changes, target hiding or global colour changes to disguise material defects.
- Do not disable memory guards, chase unbounded native-resolution runs or perform a runtime upgrade without an explicit scope decision.
- When a required capability is unavailable, identify the precise missing support, evidence and smallest next decision. Continue independent safe diagnostics, but do not count the blocked capability as passed.
- Do not silently fix unrelated faults. Record them and limit changes to the material and its necessary capture/boundary support.

Progress reports should say **implemented**, **executed**, **passed**, **failed**, **blocked** or **provisional**, with evidence. Code existence alone is not an executed test. A human reviewer must not be recorded as approving an outcome without their actual review.

---

## 5. Overall definition of done

The full sprint is complete when:

1. The previous material and capture configuration are preserved and restorable.
2. The installed material's binding, capabilities and distance units are documented.
3. Transmission/refraction has passed the small controlled diagnostic, without an opacity workaround.
4. Absorption and scattering have been separately investigated and documented in a configurable engineering preset.
5. The candidate works with the existing animated ocean without changing the wave or animal-control model.
6. Saved captures and reload tests pass the declared configuration/tolerances, with resource requirements recorded.
7. One unchanged animal has a controlled above/intersecting/below-water comparison.
8. Relevant regressions and rollback pass, and historical experiment artifacts remain unchanged.
9. Dependencies, configuration, evidence and limitations are packaged for reproduction.

Report **partial completion** if a required material capability or capture route remains unsupported. Do not replace the definition of done with “the ocean looks nicer.”

The intended outcome is:

> **One versioned, configurable water material that works with the existing MARLIN waves, demonstrates controlled reflection/refraction and underwater attenuation, survives experimental capture and reload, and has documented limitations and resource requirements.**

This is not acceptance of a calibrated seawater model, biologically realistic underwater visibility, corrected visible-region annotations, or a deployable GSD threshold.

---

## 6. Documentation references and evidence boundary

The sprint scope and milestone order come from the material-first project plan. The references below support specific material/renderer distinctions; they do not establish which features are installed or working on the user's computer. Online pages were checked on 29 October 2026 and may describe a different version from the pinned local runtime.

Use the installed definitions and version-compatible official documentation to determine actual input names and behaviour. Record discrepancies. Do not import a new feature into the acceptance claim merely because the latest documentation describes it.

[^nvidia-material]: NVIDIA, [OmniSurfaceBase and OmniSurfaceLiteBase](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/templates/OmniSurface.html). Material-family capabilities; verify the installed variant.

[^nvidia-transmission]: NVIDIA, [OmniSurface — Transmission](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/templates/parameters/OmniSurface_Transmission.html). Transmission versus geometry opacity, medium controls and scale-dependent transmission depth.

[^nvidia-geometry]: NVIDIA, [OmniSurface — Geometry](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/templates/parameters/OmniSurface_Geometry.html). Thin-walled behaviour and separate geometry-normal controls. No displacement support is assumed by this specification.

[^nvidia-renderer]: NVIDIA, [Omniverse RTX Renderer — Overview](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/rtx-renderer_overview.html). Renderer modes and documented fidelity differences, including volume-related effects.
