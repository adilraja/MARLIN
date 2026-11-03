# M4 integration plan — 30 October 2026

Base: committed M3 `9346a02`. Preserve every pinned M1/M2/M3 file.

Apply the M3 engineering medium through the existing OmniSurface authoring
route, with physical reference distance converted using the unchanged stage
units. Keep the original bound material as the explicit rollback selection.
Add only a perimeter skirt and flat bottom to the SAME ocean mesh; retain
the existing top vertices/faces as an unchanged prefix, with shared perimeter
indices so there is no second top, gap or independent wave evaluator.
Use face-varying normals to preserve the original smooth top normals while
giving sides/bottom outward normals. Bottom depth defaults to 20 m below the
ocean's local mean level, an engineering boundary rather than a bathymetry claim.

The existing animation callback will pass its calculated top arrays through
an opt-in render-enclosure adapter. The wave evaluator, surface sampler,
clock and animal controllers will remain unchanged. Serialized per-ocean
ownership/rollback metadata will make the choice explicit. Ordinary marine
setup must preserve an already selected preset; new setups retain old defaults.
Reject unsafe/folded geometry, unsupported transforms and incompatible ocean
reconfiguration rather than silently changing the medium or simulation.

Validate closure, directed-edge pairing, orientation, positive projected top
cell areas, bottom depth, shared seams and unchanged top normals/positions at
phases 0, .5, 1, 2, 4 seconds. Check the analytical horizontal-displacement
derivative bound <1 for the existing waves, and compare the unchanged sampler
and deterministic depth/following controller outputs before/after selection.
Geometry tolerance: 1e-6 stage units for copied seams/top data; sampler/controller
equivalence 1e-8 stage units. Topology counts must be exact and closure have zero
boundary/nonmanifold or same-direction shared edges. Keep renderer-only data
out of the sampler and controller state.

Retain a frozen original/candidate capture at one common phase/camera, then
candidate images at declared animated phases, and entry/exit/edge inspection.
Use the existing viewport/SDK at 512x384, 64 rendered-frame settling and native
HDR output with M3's explicit effective USD controls and firefly filtering off.
Reuse the CURRENT viewport to avoid an extra Hydra renderer on the 6 GB GPU.
Guard: >=768 MiB free before capture, one request at a time, bounded timeout;
retain failed attempts. No resolution/ray-budget escalation or app restart.
Keep scene/camera/settings checkpoints and verify restoration afterwards.

Capture evidence must show material binding retained while the ocean advances,
observable target transmission, and no second top or boundary artefact in the
central diagnostic field. Full animal demonstration, exposure qualification,
save/reload capture repeatability and high resolution remain M5/M6 work.
Optional normal detail is deferred until the core integration is established.
