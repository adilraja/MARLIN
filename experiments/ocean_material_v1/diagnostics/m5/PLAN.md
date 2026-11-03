# M5 predeclared capture and resource protocol

Sprint: MARLIN — Ocean Material and Underwater Appearance.
Milestone: Verify saved-image rendering and resource requirements.

This protocol was declared before M5 rendering. M4 and its NVIDIA camera-inside case remain open. This work qualifies the existing above-water engineering preset only; it cannot establish underwater-camera support.

- Reuse the M4 integrated ocean fixture, engineering_v1, phase 0, oblique camera, 512 × 384 square pixels, and the native Kit viewport capture SDK used by MARLIN experiments. Retain PNG, native float HDR and EXR. The UI window does not define capture intrinsics.
- Selected capture mode: the installed `PathTracing` token. Preserve M3's material, lighting, fog and firefly settings. Record effective product/camera controls and global settings. Record configured budgets separately from observed rendered-frame completion; no claim of hardware sample telemetry.
- Initial capture, two frozen repeats, then two captures after an actual fresh anonymous-layer read of the saved flattened scene from disk. Never rebuild the fixture in lieu of reloading it. The saved input hash must remain unchanged. Retain and restore the live stage using the existing single-viewport approach.
- Settle 64 rendered frames before each image, with a 30 s frame-wait limit; discard a warmup PNG. Stage attachment and renderer switching invalidate render history; no unsupported reset command is assumed. Repeats retain accumulated state and settle again. Record this distinction.
- One additional diagnostic in the installed `RealTimePathTracing` token, if registered and affordable, on the same frozen fixture at the same dimensions. This is a mode comparison, with no identical-pixel acceptance criterion and no rebranding as Real-Time 2.0.
- For same-mode repeat and reload comparisons, preserve M1's full RGB and fixed ROI tolerances: mean absolute difference ≤ 1/255 and p99 absolute difference ≤ 8/255; report maximum. Camera matrices must match within 1e-6. Compare actual scene/settings equality separately using the existing settings comparator. Fixed central ROI is x=[128,384), y=[96,288). HDR differences are additional diagnostic evidence, not a replacement for the declared display-image criteria.
- Minimum 768 MiB free before each capture; no second GPU renderer/context. If needed, explicitly use the existing 512 × 384 batch-preview transaction and restore it afterward. No output resizing, medium removal, sampling changes or effect removal to rescue a failing case.
- Capture coroutine limit 60 s per additional image, suite limit 300 s. Record unsuccessful attempts and stop on resource/time/cleanup failure. No restart is planned. Any future restart must be documented with its effect on phase and render history.
- Sample GPU used/free memory once per second; report sampled peak, not an exact allocation peak. Record host, GPU, driver, Kit/renderer versions, elapsed time and restoration checks.
- Protect historical M1–M4 evidence and source snapshots with hashes. Do not rewrite older evidence or infer M4 completion from M5's above-water results.

Full native HiDef/Sony output and fresh-process repeatability are outside this bounded acceptance run. A fresh-stage reload is required. Unsupported modes, temporal differences and unresolved settings must be reported explicitly.
