# Local support addendum — retested with NVIDIA driver 595.99.02

Prepared 3 November 2026 for the existing [RTX Renderer forum case](https://forums.developer.nvidia.com/t/rtx-pathtracing-omnisurface-attenuation-missing-when-camera-starts-inside-closed-water-kit-110-2-0-and-110-4-1/387771). This addendum has not been posted.

After a system reboot resolved an NVIDIA driver/NVML mismatch, we repeated the six initial frozen standalone reproduction scenes using the same private Kit 110.2 build, `110.2.0+feature.342835.698af100.gl`, on the RTX A2000. The loaded driver now reports **595.99.02**; the Linux kernel is **7.0.0-42-generic**. The previous test used driver 595.91.07 and an earlier kernel. This establishes persistence on the current host configuration, not a single-variable causal experiment.

The source scene hashes, standalone app configuration, per-product optical controls, 512 × 384 output and 64-rendered-frame protocol were retained. The capture harness's only change skipped an optional direct vendor-MDL file hash, to comply with repository restrictions on reading generated caches; rendering controls were unchanged. Native HDR arrays and EXRs were retained and independently checked.

| Test | Absorption / clear native HDR RGB | Expected RGB | Result |
| --- | --- | --- | --- |
| Above-water camera, 1 m water path | [0.600536, 0.800048, 0.898451] | [0.6, 0.8, 0.9] | Passed the existing 0.03 absolute ratio tolerance |
| Inside-water camera, 0.5 m water path | [1, 1, 1] | [0.774597, 0.894427, 0.948683] | Failed; no measured absorption |

The above-water emissive/absorption positive controls passed. For the inside camera, the clear, absorption and engineering cases all had centre ROI RGB **[11336, 11336, 11336]**. The engineering medium's blue/red ratio was 1 inside versus approximately 1.498 above water. The original inside-medium attenuation defect therefore remains reproducible with driver 595.99.02. No longer distance sweep was performed in this bounded retest.

The application installation and previous evidence were preserved. A support response identifying the supported camera-initial-medium configuration, a renderer fix or another minimal diagnostic remains useful. This result does not close the animated-ocean underwater qualification.
