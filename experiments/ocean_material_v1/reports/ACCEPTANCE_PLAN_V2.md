# Baseline plan amendment — version 2

Recorded on 29 October 2026, before the first retained baseline image and before
any candidate material. The version 1 plan remains retained without rewriting.

The live audit resolved the bound OmniSurface shader and exported scene/material
evidence, but the existing metric-projection helper refused the 512 x 384 viewport
because the camera aperture aspect differs from image aspect. No image from that
attempt is accepted and its failure is preserved. This is a camera-conformance
limitation, not a reason to change animal geometry or camera calibration.

Use the existing viewport resolution recorded by the checkpoint (1280 x 720),
with its existing camera, explicitly as a nonmetric appearance baseline. Keep
the full camera/stage in a frozen checkpoint. This changes the declared image
size before image acceptance, without changing sensor geometry or making any
pixel-to-world accuracy claim. Retain the same predeclared repeat-image limits.

Checkpoint the current scene before stopping the camera and ocean subscriptions,
then restore that checkpoint with those controllers stopped. This preserves the
saved composed wave/animal/camera state instead of capturing continuously moving
controllers. Record controller stop results and checkpoint restoration results.
Use only existing checkpoint and viewport-capture endpoints. Before every image,
require at least 768 MiB free GPU memory. Save one warm-up and three retained
repeats. Take two existing checkpoint restores to verify restoration of the saved
binding and settings; the animation phase/controllers are not checkpointed.

Do not restart Kit a third time for this diagnostic. Do not patch the camera
projection helper, adjust camera apertures, disable guards or change water inputs.
Record raw scene/camera preservation separately from unsupported projection
validation. Later metric refraction diagnostics must use deliberately compatible
diagnostic camera geometry within M2.
