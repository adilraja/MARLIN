# M4 — Apply the material to the existing animated ocean

| Field | Value |
|---|---|
| Sprint | MARLIN — Ocean Material and Underwater Appearance |
| Recorded | 30 October 2026 |
| Base commit | `9346a02` |
| Status | Above-water integration passed; full milestone remained open |
| Remaining issue | Camera-inside attenuation was not demonstrated |

The M3 medium was integrated as an opt-in preset on MARLIN's existing animated
ocean. Closed-boundary, animation, sampler/controller equivalence, scene-setup
preservation and rollback checks passed. Twelve main capture requests plus
one additional edge inspection succeeded. The camera-inside probe returned a
neutral target rather than demonstrating the expected colour attenuation.
Consequently underwater-camera views were not qualified and **M4 was not
marked fully complete**.

## Material and geometry integration

`POST /scene/ocean/material/preset` selected `engineering_v1` or restored
`original`. The existing OmniSurface binding implementation was reused; its
original function body was retained unchanged in a callable helper. The M3
material parameters and one-metre transmission reference distance were retained,
with native distance computed from unchanged stage units.

The added render geometry was a perimeter skirt and a flat bottom on the
**same `/World/Ocean` mesh**. It did not introduce another top interface or
another wave evaluator:

| Quantity at the existing resolution 128 | Original | Selected medium |
|---|---:|---:|
| Surface vertices | 16,641 | 16,641, unchanged prefix |
| Total mesh vertices | 16,641 | 17,154 |
| Surface quads | 16,384 | 16,384, unchanged prefix |
| Total mesh faces | 16,384 | 17,408 |
| Added boundary geometry | None | 512 side quads, 512 bottom triangles |
| Water representation | Open, thin-walled surface | Closed, non-thin-walled medium |

The 513 added points were a projected perimeter ring and one bottom centre.
Side faces shared the original surface perimeter indices, eliminating seam
gaps by construction. The bottom was 20 m below the local mean ocean level;
it was an engineering boundary, not a seabed/bathymetry model. Its X/Z ring
followed the current displaced surface perimeter.

Face-varying corner normals copied the original smooth top normals exactly
while giving sides and bottom their own outward normals. No material
displacement, optional fine normal map or new surface animation was added.
The optional detail task was deferred; it was not required for core integration.

At phases 0, .5, 1, 2 and 4 seconds, native checks found zero boundary edges,
zero nonmanifold edges and zero same-direction shared edges. Top normals were
upward, side normals outward and bottom normals downward. The existing
Gerstner horizontal derivative bound was approximately .385612, below one;
the tested surface stayed unfolded. Duplicate top faces were not created.

The adapter ran inside the existing ocean update callback after its original
calculation. It used vectorized array preparation and native Vt arrays for
render data. The existing wave evaluator, height sampler, calculation routine
and base topology routine retained identical ASTs. The cetacean controller
source retained identical bytes. No second simulation/update mechanism was
introduced. Existing sampler approximations were preserved rather than
relabelled as new physical or image-surface calibration.

## Selection, setup preservation and rollback

The old material remained available as `/World/Looks/OceanWater`; the selected
material was `/World/Looks/OceanWaterEngineeringV1`. Ownership/configuration
metadata on the ocean retained the original binding, sidedness, restart
contract and any explicitly changed renderer properties.

Normal `/scene/marine/setup` preserved a selected medium, including its closure
after restarting the existing animation. Both binding-only and explicit
renderer-configuration paths were checked. An incompatible resolution change,
an attempted ocean replacement and a legacy material overwrite were rejected
until explicit rollback. New/original scene setup retained its prior defaults.

Rollback restored the current animated top surface, 16,641 vertices, 16,384
faces, smooth vertex normals, original sidedness and original material. The
explicit renderer-option test also restored five native renderer/camera
properties and the prior underwater-cue setting. No animal material, geometry,
rig, scale or biological parameter was changed.

## Sampler and controller regression

The five-phase comparison measured **zero difference** in original surface
positions, original top normals and shared surface-sampler outputs before and
after selection. Tolerances had been declared as 1e-6 stage units for copied
geometry and 1e-8 for sampler/controller equivalence.

The actual existing swimming update was exercised with fixed initial states,
first near the centre and then in its existing boundary-avoidance zone.
Diving and surfacing commands were applied in three segments. Original and
selected-medium trajectories matched exactly for position, depth, heading,
pitch, bank and boundary state. These were engineering regression inputs using
existing controls, not newly proposed animal behaviour parameters.

The initial synchronous 240-step comparison passed on the server but exceeded
the client's 120-second wait. Its successful result and the client timeout
were retained. The responsive version used 20 steps of .3 seconds per
trajectory, yielding between small batches while external controllers were
paused. It also passed with zero output differences. Both runs are retained;
the timeout was not rewritten as an ordinary successful HTTP response.

## Captures and observations

The twelve-request main batch used the current live viewport and existing
NVIDIA SDK, avoiding another USD context/Hydra renderer. It retained native
512×384 PNG, EXR and float-buffer output, effective camera/product settings,
frozen scene exports and per-transaction restoration checks. Each frozen
capture settled for 64 delivered rendered frames.

The main batch covered:

- Original/candidate comparisons at phase 0 from nadir and oblique views.
- Candidate oblique views at phases .5, 1, 2 and 4 seconds.
- An inside-camera view, an upward exit view and an edge-adjacent view.
- A real update-loop sequence retaining the selected binding while the ocean
  advanced from about .453 to 2.461 seconds over ten sampled updates.

A separate `outer_edge` view, centred on the nominal 80 m domain boundary,
straddled the finite ocean edge. The skirt was visible at that deliberately
boundary-crossing viewpoint. It must remain outside intended central survey
frusta; the implementation did not claim an infinite seamless ocean or hide
the boundary. The top/side connection remained closed. Central nadir/oblique
captures did not expose the sides or bottom as extra interfaces.

For the exit and boundary camera overrides, inherited diagnostic configuration
and planar-target predictions describe the nominal setup only. Their actual
capture matrices and frozen USD are authoritative. Derived effective positions
are recorded in `qa/effective_camera_poses.json`; no target observation was
expected from those overridden views.

The unchanged .18 m diagnostic target was placed at X=12 m, Y=-1 m, Z=0,
away from the existing animal. Its own material and the fixed background
were identical across comparisons. All nine primary above-water images
showed the target. Descriptive post-run HDR component measurements reported
its area, centroid and colour; these were not substituted for a predeclared
Snell-law check or used to redefine annotations on the curved surface.

Native display PNGs saturated. Comparisons therefore included explicitly
labelled HDR previews using the same `log1p(RGB)/log1p(12000)` display mapping
for every condition, as well as retained original HDR samples. No per-image
exposure normalization or local target/background manipulation was used.

The inside-camera probe was important: at camera Y=-.5 m and target Y=-1 m,
both were inside the closed medium, yet the central target HDR mean was
**(11336,11336,11336)**. Expected chromatic attenuation was not demonstrated.
The upward exit image was retained as inspection evidence, not a quantitative
validation of underwater transport. No supported initial-medium control was
established from the installed camera/product attributes or consulted NVIDIA
material documentation. This is an unresolved capability/configuration
dependency, not proof that all RTX underwater rendering is unsupported.

The [NVIDIA OmniSurface documentation](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/templates/OmniSurface.html)
describes the intended interior transmission controls. M4 did not add a camera
shell, substitute fog or change target opacity to simulate the missing
camera-inside effect. The implemented preset remains explicitly unqualified
for that case in its API/configuration metadata.

## Resource conditions and failed attempts

The host remained an RTX A2000 with 6138 MiB and driver 595.91.07. The initial
batch was blocked before rendering at 416 MiB free; reference collection did
not recover sufficient headroom. A fresh scene checkpoint was saved, the
verified Kit process was stopped gracefully and the existing app relaunched
once. The scene was restored; no system or dependency upgrade was performed.

After restart, restoring the scene left 1579 MiB free. Two original-material
captures succeeded, but restoring the 1280×720 real-time preview between
requests left only 746 MiB before the next capture, which the guard rejected.
Those attempts and outputs remain separate from the main batch.

Holding the same preview at the already declared 512×384/PathTracing settings
through the batch recovered sufficient headroom. This changed the temporary
preview allocation pattern, not the saved-image resolution, effects, medium,
camera sampling or ray budget. The original preview was restored afterwards.

The twelve main captures took **51.90 seconds total**, 2.38–6.61 seconds each
(median 4.35). During that batch, 51 one-second observations recorded a
peak-observed usage of 4766 MiB and minimum-observed free memory of 1032 MiB.
The minimum pre-request free value was also 1032 MiB. The 768 MiB guard remained
enabled. These sampled values are not a continuous hardware peak or a
permanent memory fix. The separate outer-edge probe also passed its guard.

Other retained failures included an anonymous-root-layer save error in the
first live-viewport probe and a subsequent temporary-namespace occupancy
rejection. Capture setup was corrected to support anonymous live roots and
to restore owned root specs and temporary namespaces explicitly. M3's
file-backed/default capture behaviour was retained.

The sealed restart log retained the known asset-converter/libxml2 and dependent
importer startup failures, plus an occupied debugger port. No MDL failure,
device-loss or out-of-memory message was found in that snapshot. USD diagnostics
were muted by the existing application setting, so the log alone was not treated
as an exhaustive geometry or shader correctness check.

## Verification and restoration

Thirty offline tests passed; two general USD camera tests were skipped because
host Python lacked pxr. Seven canonical source modules passed syntax checks.
Native Kit checks exercised the live USD geometry and controller paths.
Every main capture passed data, binding, effective-control, image-size,
EXR-header, float-buffer and restoration checks. Those checks are distinguished
from the failed optical qualification of the inside-camera case.

The original pre-work checkpoint and standard marine setup were restored.
All 73 recorded global renderer settings, camera, 1280×720 resolution,
fill-frame setting and display options matched the pre-work checkpoint.
The original ocean material was selected and the existing ocean/chase
controllers reconstructed with swimming disabled. Procedural animation phase
was reconstructed, not claimed identical after reload/restart.

All pinned M1/M2/M3 evidence was preserved. Accepted capture-source snapshots,
final source hashes, dependencies, commands, failures and log snapshots are
retained under `../diagnostics/m4/`. No generated runtime or vendor code was
edited. No commit was made automatically.

## Remaining work

M4 remains open until the camera-inside medium-initialisation behaviour is
resolved or the milestone is explicitly accepted with an above-water-only
qualification. The existing above-water material integration, geometry,
animation/controller checks and rollback are available for review now.
M5 production capture/reload/exposure qualification and M6 animal comparisons
were not marked complete by this work.
