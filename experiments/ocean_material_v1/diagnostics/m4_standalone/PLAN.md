# Standalone camera-medium reproduction and isolated Kit comparison

The current MARLIN installation, canonical source, SDK, shared package cache
and live scene must remain unchanged. Evidence is written only in this new
experiment. New SDK downloads, extension caches, Python bootstrap, user data,
configuration, logs and shader/CUDA caches use private paths under `work/`.
No MARLIN extension or HTTP service is loaded by the standalone app.

Baseline: official `kit-kernel` 110.2.0 feature build, matching MARLIN's recorded
kernel package version. Candidate: official 110.4.1 production build selected
from NVIDIA's current Kit App Template manifest. This compares complete native
runtime packages, including their standard materials and dependencies; it is
not a renderer-binary-only substitution. The newer runtime is a candidate,
not an assumed fix for the related OMPE-96387 release-note entry.

The human-readable USDA scenes contain a flat closed box, one emissive white
target, black background, fixed dome light and camera. There are no MARLIN
assets, references, textures, controllers or extension imports. Their only
material-library dependencies are standard OmniSurface and OmniEmissive MDL
shipped with Kit. See REPRODUCTION_AMENDMENT.md for the retained draft scenes
and the final readiness protocol.
The exact same scene files and capture harness are used for both SDKs.

Initial tests: clear, absorption-only and selected engineering water, viewed
from inside and above. Retain 512x384 PNG, EXR and native float HdrColor, exact
effective controls, native runtime/material identifiers, camera matrices,
geometry validation and memory/time records. Use 64 delivered rendered-frame
settling, fixed exposure, fog/firefly filters off, 16 total and glossy bounces.
Camera-inside position Y=-.5 m, original target Y=-1 m; above camera Y=3 m.
Stage Y is up and metersPerUnit=.01. The volume extends to Y=-5 m.

Measure the fixed centre 16x16 HDR ROI. Clear channel spread must be <=1%;
engineering water must demonstrate B/R>1.05 inside. If inside absorption works,
also test paths .25, .5, 1 and 2 m, comparing absorption/clear channel ratios
against (.6,.8,.9)**path with absolute ratio error <=.03. A successful file
capture is not a successful optical result. Differences in native defaults
must be recorded and controlled before attributing a result to a version fix.

GPU safeguards: require 2048 MiB free before launching a renderer and 768 MiB
before each capture. Do not start a second renderer with insufficient headroom.
Precache mode may download dependencies without starting renderer extensions.
If the live MARLIN process prevents sufficient headroom, prepare all CPU work
first and request permission before a checkpointed temporary closure; no
closure or scene change is authorised by this plan itself.

Completion of this task means a self-contained reproduction, a recorded
attempt/result for both isolated runtimes, and verification that existing
MARLIN source/install configuration was preserved. It does not alone close
M4: any successful fix must subsequently pass the animated-ocean integration,
sampler/controller and rollback checks.

Cold-start amendment: the first isolated baseline launch spent substantial
time compiling native Vulkan pipelines in its empty private cache. Retain that
initial 90-second capture attempt and its exact harness snapshot. Subsequent
runs allow 240 seconds for the first case and 90 for later cases, within the
480-second process watchdog. The 64 delivered-frame wait, its own 45-second
timeout, image size, material, camera, sample/ray controls and memory guards
remain identical. This is startup allowance, not an optical acceptance change.
