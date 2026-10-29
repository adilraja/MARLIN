# Bounded diagnostic probes after the first failed transmission set

All six initial requests executed, but water and index-matched media hid the
target. The dry controls showed the target. Geometry had zero boundary edges,
outward normals, explicit supported transmission inputs and existing ray budgets
of 8 for RTPT and 16 for path tracing. No water-opacity input was reduced.

Retain that first set. Before further capture, disable the viewport grid/gizmo
overlay for all subsequent diagnostic images and restore the display setting
after each request. This changes capture hygiene, not target geometry or optics.
Initial images remain diagnostic failures, not accepted metric comparisons.

Try at most two individual oblique water probes without changing the renderer,
camera, scene scale, ray budgets or target: positive native depth=100 with white
transmission and zero scattering, then reflection weight=0 with depth otherwise
unchanged. These isolate null-interior handling and the reflection layer. A
reflection-off probe cannot itself satisfy the final reflection criterion.
Keep the same 768 MiB memory guard. Stop if either request reports insufficient
memory. Keep the originally declared measurement rule and tolerances.

Official references checked alongside installed declarations:
- https://docs.omniverse.nvidia.com/materials-and-rendering/latest/templates/OmniSurface.html
- https://docs.omniverse.nvidia.com/materials-and-rendering/latest/templates/parameters/OmniSurface_Transmission.html
- https://docs.omniverse.nvidia.com/materials-and-rendering/latest/rtx-renderer_rt.html

The documentation describes depth=0 as a null interior. Its latest feature claims
are not assumed to prove the installed renderer's behaviour.
