# M4 follow-up — camera inside the water

The original M4 evidence, failed inside-camera image and sealed manifest are
retained unchanged. This follow-up starts from checkpoint_mpwvumxn.

First test the existing native material and boundary: repeat the inside view,
change USD sidedness alone, enable the registered non-uniform-volume control
alone, and test the existing MDL shader on USD's volume terminal. The latter is
an exploratory compatibility test, not a claim of installed support. Combine
the volume terminal and native volume flag only if required. No camera shell,
cutout opacity change, target hiding or substitute fog is acceptable.

Retain native 512x384 HDR/EXR and 64 rendered-frame settling, the existing
single viewport, effective settings, frozen stage and restoration records.
Keep the 768 MiB GPU guard. Use the existing bounded preview session; any
required restart must first save and verify a fresh checkpoint.

If a supported fix works, validate it at camera-to-target paths .25, .5, 1
and 2 metres. Freeze camera Y=-.5 m and wave phase=1 s, move only the declared
diagnostic target/background. Use fixed centre 16x16 HDR means. In an
absorption-only control, compare attenuation ratios to C**(path/1 m), with
absolute channel ratio error <= .03; the clear control must remain neutral
within .01 relative channel spread. Confirm the original failed .5 m view
under the selected scattering preset is no longer neutral (B/R>1.05).

Repeat existing above-water nadir/oblique and wave-phase integration checks,
the actual sampler/controller regression and rollback after the final change.
Document any supported native volume configuration and additional costs.
A failed native path or need for broader rendering architecture must remain
an explicit dependency; it cannot be relabelled as a completed milestone.
