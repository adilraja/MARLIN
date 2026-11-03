# Prospective 595.99.02 underwater-camera retest

Run the six initial sealed standalone scenes (inside 0.5 m and above-water 1 m, each clear/absorption/engineering) using the same experiment-owned Kit 110.2 executable, standalone app, product controls, source bytes and optical analysis as the prior driver-595.91.07 baseline. No MARLIN scene/assets or source changes enter the isolated renderer.

Use 512 × 384, 64 delivered frames, the existing per-case bounds and 768 MiB capture / 2,048 MiB renderer-start safeguards. Keep the prior harness's material-loading readiness and warmup procedure unchanged. Sample GPU memory approximately once per second and preserve failures. Only one renderer process is active at a time. Close MARLIN gracefully after its verified checkpoint, then reopen and restore it for M6.

The native capture harness is copied unchanged except that its optional direct MDL-file hash is skipped: repository instructions prohibit inspecting generated/vendor cache files. This observation-only change does not alter rendering. Record registered/resolved MDL references and Kit/runtime versions instead, and retain the exact one-line diff and script hashes.

Reuse the previous independent optical tests: neutral clear control channel spread ≤ 1%; absorption/clear versus Beer-law prediction absolute RGB ratio error ≤ 0.03; engineering blue/red ratio > 1.05. Require a valid above-water emissive/absorption positive control before interpreting the inside result. Inside failure keeps M4 open. The old evidence and NVIDIA forum post are not edited; prepare a local addendum if needed.
