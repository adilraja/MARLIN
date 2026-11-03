# Capture batch preview budget

The 768 MiB guard blocked the first batch at 416 MiB free and remained blocked
after Python/SDK reference collection. A checkpointed restart of the existing
Kit app restored 1579 MiB free with the original marine scene. Two 512x384
original-material captures then succeeded, but the next request was blocked
at 746 MiB after repeatedly returning the live preview to 1280x720/real-time.
All responses and both successful captures remain retained as attempt02.

For the acceptance batch, hold the SAME existing viewport at 512x384 and
PathTracing between requests. Resize the existing preview first, retain its
previous mode/resolution/settings, and enforce the original 768 MiB guard
before switching the resized preview. Each actual capture still uses the
same 512x384 image size, camera sampling, 64 rendered-frame wait, medium and
ray budgets. No capture resolution/effect reduction or guard bypass.

The fixed batch-preview begin/end endpoint restores the prior live preview
afterwards. Per-capture layer/spec/camera/restoration checks still apply.
Full native-resolution production capture remains M5 work. This restart and
preview-size dependency are recorded resource conditions, not a permanent
memory fix or an unrestricted production qualification.
