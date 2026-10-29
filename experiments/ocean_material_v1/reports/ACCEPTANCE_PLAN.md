# Ocean material acceptance plan — version 1

Recorded before the first new baseline capture or candidate change, 29 October 2026.
This is an engineering test plan. No field-water or biological acceptance is implied.

## Milestone 1 baseline

Use the existing MARLIN application and marine setup. If a live ocean exists,
inspect it without reconstructing it. Refuse to replace an unrelated nonempty
stage. Since the initial HTTP and host-process probes found no Kit, any new
marine scene must be identified as a fresh reconstruction, not the recovered
October scene. Use one existing dolphin with no swimming. Freeze the shared
capture state and timeline for export and capture, then restore those controls.

Retain the complete sampled scene, effective binding and authored shader values,
stage unit metadata, actual bounds and boundary-edge counts, camera projection,
lights, renderer settings, enabled extension versions and GPU observations.
Record unauthored shader defaults, unresolved definitions and material-distance
interpretation as unknown unless measured or resolved from installed definitions.

Capture one warm-up and three retained repeats at exactly 512 x 384 using the
existing Kit viewport capture utility. Preserve every failure. Request no second
renderer, native sensor capture, new material or runtime upgrade. Startup requires
at least 2048 MiB free; each capture retains the existing 768 MiB guard. Each
capture is limited to 60 seconds, the audit coroutine to 300 seconds. Record update
counts separately from renderer samples. Do not increase budgets after failure.

Baseline repeat measurement: compare full RGB arrays and retained fixed ROIs,
reporting mean absolute difference, 99th percentile absolute difference and maximum
difference in the saved image colour domain. Initial engineering limits are
mean <= 1/255 and p99 <= 8/255, with matching dimensions and exact frozen geometry.
If the baseline fails, preserve it and amend the repeatability plan explicitly
before any candidate test. A matching state hash alone is not an image pass.

## Later milestone acceptance gates

Before M2, identify the installed shader definition, supported controls and
distance convention. Use known-size geometry to verify physical-to-scene scaling.
Use the same small target, camera, lights, fixed exposure and image settings for
no-water, index-matched (if supported) and water comparisons. A finite volume must
be closed with checked winding; a thin-walled sheet must not be called a volume.
At least one oblique target displacement must exceed the measurement uncertainty.
Compare the target centroid with a planar Snell prediction: tolerance is the
larger of 2 image pixels and 1% of predicted displacement. Record the selected
indices as engineering assumptions unless separately supported. Maintain full
interface opacity and verify an unchanged target, not hidden-object substitutions.

Before M3, declare three physical depths within the diagnostic volume and retain
the M2 clear-water control. Sweep absorption first and scattering separately.
Use fixed target/background ROIs, record channel means and contrast, and use
linear image data where available. Otherwise report display-domain measurements
without fitting physical absorption coefficients. Decide the expected direction
and minimum detectable contrast change from control-repeat noise before candidate
acceptance, rather than selecting a tolerance from the candidate result.

M4 must retain surface coordinates, sampled heights and controller outputs for
identical inputs: compare floats with relative tolerance 1e-7, absolute 1e-6 scene
units. Render-side boundaries must not introduce another independently simulated
surface. Any major enclosure redesign is a scope decision.

M5 uses the same declared image size and camera. Repeat and fresh-reload image
checks use the above limits unless a prior, explicitly versioned control study
requires a change. Compare camera matrices with absolute tolerance 1e-6 and
renderer settings with the existing `same_settings` helper. Record effective
renderer mode, actual hardware, elapsed time, observed memory and failures.

M6 retains an unchanged animal and controlled above/intersecting/below-water
pairs. Preserve existing annotation semantics and record visible/refraction
discrepancies. Restore the original material/settings and run existing relevant
regressions. Obtain actual named human review before recording review acceptance.

## Proceed gate

Do not start a candidate material while the M1 baseline, material/distance audit
or rollback evidence is incomplete. Unsupported capabilities are partial results,
not equivalent fallbacks. Preserve historical experiments and their original
statuses throughout.
