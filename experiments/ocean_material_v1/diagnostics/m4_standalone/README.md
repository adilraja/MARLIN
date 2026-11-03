# Standalone underwater-camera reproduction

This experiment compared private official Kit 110.2.0 and 110.4.1 SDKs without
loading MARLIN. See `../../reports/M4_STANDALONE_VERSION_COMPARISON.md` in the
repository (the report is under `experiments/ocean_material_v1/reports/`).
The ZIP includes the same report as `COMPARISON_REPORT.md`.
The distributable ZIP contains this README, fifteen USDA scenes, their manifest,
the native app/capture harness, portable launcher and a result summary. It
contains no NVIDIA SDK binaries or copied MDL library definitions.

## Run outside MARLIN

Requirements: Linux x86-64, a compatible NVIDIA RTX GPU/driver, an independently
obtained NVIDIA Kit SDK, system Python 3, `nvidia-smi`, and network access for
the SDK's native extension resolution. Kit supplies its own Python dependencies.
Use a new output directory for every run. At least 2048 MiB of free GPU memory
is required at startup, and 768 MiB before each capture. Run one SDK at a time.

From the extracted package:

```bash
python3 -B run_reproducer.py --sdk /path/to/kit-sdk \
  --output /tmp/water-precache-1104 --profile /tmp/water-profile-1104 --precache-only
python3 -B run_reproducer.py --sdk /path/to/kit-sdk \
  --output /tmp/water-render-1104 --profile /tmp/water-profile-1104
```

Use a different profile and outputs for each SDK. `--precache-only` downloads
native extensions without starting the renderer. First-time dependency download
can take several minutes. An informational startup dialog may need acknowledging
on a desktop session; no BIOS or IOMMU change is required by this test. Logs
retain the notice. The helper that acknowledged this machine's test-owned
notice is not required or included in the portable package.

The default six captures are clear, absorption-only and engineering water,
each viewed from inside and above. `--suite all` also includes underwater paths
.25, .5, 1 and 2 metres. In this investigation the distance sweep was conditional
on a successful initial inside test and was not executed because it failed.
Every capture retains PNG, EXR, native float NPZ, effective settings, source and
frozen-scene hashes, actual camera/product checks and sampled resource metadata.
Rendering success alone does not establish optical correctness.

## Scene and measurement

The standalone app uses only native NVIDIA Kit extensions, one closed flat
water box, a constant white emissive target, black background and fixed dome.
There are no MARLIN imports, services, animal assets, references, payloads or
external textures. Standard `OmniSurface.mdl` and `OmniEmissive.mdl` are resolved
from the supplied SDK. The manifest's old MARLIN scene path is generation
provenance only; the provided USDA files run independently of that file.

Coordinates: Y up, .01 metres/unit; underwater camera Y=-.5 m; above camera Y=3 m.
The initial underwater target lies .5 m below the camera; above target depth is
1 m. Absorption colour at native depth=100 is (.6,.8,.9); the engineering variant
adds scattering colour .02. PathTracing uses fixed exposure, fog/firefly off,
16 bounces, a configured 512-sample limit and 1 sample/iteration. The harness
waits for native material/streaming readiness then 64 delivered rendered frames.
The actual accumulated sample count is not measured.

Read `hdr.npz` with NumPy; `rgba[184:200,248:264,:3].mean((0,1))` is the fixed ROI.
Compare absorption with clear from the same SDK/view/path. Expected direct
underwater ratio is `(.6,.8,.9)**path_m`, absolute error <=.03. Clear channels
must agree within 1%; engineering B/R must exceed 1.05. Require visible clear
emitters in both views (>100/channel), clear above/inside >.5 and a valid
above-water absorption control before interpreting underwater failures.

Display PNGs saturate at this emission level. Float data are authoritative;
the comparison preview uses a single fixed `log1p(RGB)/log1p(12000)` mapping.
Absolute radiometric calibration was not established.

See `REPRODUCTION_AMENDMENT.md` for protocol corrections and exploratory runs.
The current MARLIN installation was not upgraded. A valid negative result in
these two builds does not establish that every NVIDIA volume representation
or later SDK lacks camera-inside support.
