# M2 — Native-provider feasibility and clean lifecycle

Date: 9 November 2026. Status: **feasibility checks executed; stopped before new
dependency installation; M2 incomplete and Gate B not eligible**.

## Result

The existing Kit runtime supported a minimal, private renderer application with
normal startup, an owned anonymous USD stage and normal shutdown. Two renderer
processes completed without watchdog signals or logged errors. Neither
`omni.replicator.core` nor `omni.syntheticdata` was found among the 224 installed
extension/package entries returned by the supported extension manager. The
previously used isolated 110.2 SDK also had neither provider in its separately
queried 102-entry package inventory. The
sixteen dry annotation bundles therefore remain unexecuted.

No annotation provider was imported or enabled, no new extension or pip package
was installed, and no production source, accepted preset, animal asset or prior
acceptance record was edited. No live MARLIN process or HTTP service existed at
preflight, so there was no user scene to close, replace or restore.

## Lifecycle evidence and retained failures

The individual launch, worker, configuration, inventory, resource samples and
exit records are retained under `diagnostics/m2_feasibility/runs/`.

| Probe | Outcome | Elapsed |
|---|---|---:|
| `metadata01` | Failed diagnostic: app exited without running the query because no run loop was loaded; return code 0 was correctly insufficient for a pass | 6.09 s |
| `metadata02` | Installed metadata query returned and normal shutdown completed | 5.09 s |
| `renderer01` | Failed: NVIDIA IOMMU/zenity information dialog blocked startup; 120 s watchdog sent SIGTERM only to the owned group | 122.22 s including cleanup |
| `renderer02` | Failed: removing DISPLAY/WAYLAND_DISPLAY alone still allowed default Wayland discovery; same bounded cleanup | 122.34 s including cleanup |
| `renderer03` | Passed private stage creation/closure and normal `IApp.post_quit`; no cleanup signals | 65.29 s |
| `registry01` | Metadata-only registry queries returned; registry fallback stayed disabled; no compatible package metadata established | 7.12 s |
| `renderer04` | Passed a second fresh-process stage lifecycle and normal exit | 7.20 s |
| `registry02` | Explicit index sync returned false with the registry gate disabled; package pin remained unresolved | 7.14 s |
| `registry03` | Private index access temporarily enabled after offline startup, then restored; sync still returned false and installed package IDs were unchanged | 7.15 s |
| `registry04` | Explicit metadata refresh and sync with private index access; sync returned false, no package pin resolved, gate restored and installed package IDs unchanged | 6.12 s |
| `sdk1102_metadata01` | Failed offline dependency resolution: the new profile did not discover the SDK's previously populated package folder; no query ran and no download occurred | 7.14 s |
| `sdk1102_metadata02` | Passed metadata query against that existing folder, whose location came from retained runtime logs; 102 entries, neither provider, same exact Kit build, normal exit | 5.09 s |

The successful renderer app loads already installed USD, RTX, viewport, capture,
settings and update-loop extensions. It excludes the unrelated asset-importer /
converter application path. A normal file-import dialog dependency is not the
known asset converter. Registry fallback and startup registry synchronization
remain disabled.

For the successful headless processes, DISPLAY and WAYLAND_DISPLAY are absent,
XDG_RUNTIME_DIR is an empty private directory and GDK_BACKEND is x11 with no X11
display. GTK can otherwise discover `wayland-0` through XDG_RUNTIME_DIR. These
settings belong only to the diagnostic child. The workstation's Wayland session,
IOMMU, kernel, driver and main Kit configuration were not changed. NVIDIA
[documents the blocking informational dialog](https://docs.omniverse.nvidia.com/dsx/latest/troubleshooting.html),
and GTK documents [backend selection](https://docs.gtk.org/gtk4/running.html) and
[Wayland socket discovery](https://docs.gtk.org/gtk4/wayland.html).

Both successful workers waited for app readiness, created only an anonymous cube
stage, advanced four updates, closed that stage, verified the context was empty,
and requested normal cancellable quit. The first included shader compilation;
the second is a fresh process/profile, **not proof of a cold driver/shader cache**.
This proves the finite diagnostic application's lifecycle. It does not prove
full MARLIN GUI shutdown, annotation attachment/detachment or image/AOV cleanup.
The original M1 timeout remains retained as a failure.

## Provider and compatibility boundary

The runtime reports `110.2.0+feature.342835.698af100.gl`; the host driver is
595.99.02 on an NVIDIA RTX A2000 with 6138 MiB. Supported manager queries were
`get_extensions`, `get_extension_packages`, `get_registry_extensions` and
`get_registry_extension_packages`; paths were obtained only as runtime metadata.
Generated runtime/cache directories were not manually inspected.
The alternate SDK was queried through its already installed package location
observed in earlier diagnostic logs. A new writable profile was used, with no
restoration or mutation of the earlier diagnostic scene/profile settings.

The already installed registry extension was enabled only in its private query
app, whose startup dependency resolution remained offline. It advertised the official 110.2 shared
and SDK `698af100` registries. Its fetch/version calls returned no metadata and
its metadata-only solver reported no solution. Explicit `sync_registry()`
returned false while the registry gate remained disabled. Two subsequent probes
temporarily allowed index access after offline startup; the last explicitly
refreshed metadata before synchronization. Both still returned false / no
solution, restored the gate and verified identical installed package IDs.
Those empty responses
**do not establish that NVIDIA has no compatible provider**. They establish no
usable local provider and no resolved package pin in these probes. No extension
pull, remote annotation-provider enable, precache mode or pip installer was invoked.

The official [110.2.0 SDK registry reference](https://docs.omniverse.nvidia.com/kit/docs/kit-registry-reference/latest/110.2/110.2.0/sdk.html)
matches hash `698af100` and lists SyntheticData, linking to 0.6.15 documentation.
The [separate 110 shared registry reference](https://docs.omniverse.nvidia.com/kit/docs/kit-registry-reference/latest/110/shared.html)
lists Replicator core 1.13.27; the 110.2 shared listing did not supply that entry.
Neither documentation pointer is a complete, compatible binary package pin.
NVIDIA's [SyntheticData overview](https://docs.omniverse.nvidia.com/kit/docs/omni.syntheticdata/0.6.15/Overview.html)
directs applications to the higher-level Replicator API. A direct deprecated
SyntheticData implementation is not adopted as a workaround.

Exploratory HEAD requests to the two runtime-advertised registry roots plus
`/index.zip` and `/3/index.zip`, and a bounded public listing request for the SDK
`/v2` metadata prefix, returned HTTP 404. These limited endpoint results do not
prove a registry-wide outage or that no other supported access path exists.
See `registry_header_probe.json`. No usable package metadata was obtained here.

The exact package, transitive dependency graph, compatibility and disk estimate
are therefore **unresolved**, rather than invented. The bounded next step is
specified in [M2_NATIVE_PROVIDER_DEPENDENCY_REVIEW.md](reports/M2_NATIVE_PROVIDER_DEPENDENCY_REVIEW.md).
This packet is not an installation approval request for an unknown package.

## Resources, preservation and capture accounting

Admission required 2048 MiB free GPU memory and 10 GiB free disk. The two passing
renderer probes observed minima of 1023 and 1022 MiB free, above the 768 MiB floor.
Memory returned after each process exited. This modest remaining margin does not
qualify the additional memory cost of native annotation AOVs; remeasure after
any separately reviewed dependency change. Resource samples are observations at
approximately one-second intervals, not continuous peak measurements.

Twelve finite diagnostic processes were executed. They retained **zero images,
zero rendered capture-bundle attempts and zero annotation outputs**, so the
120-planned / 144-maximum capture declaration and its 24-bundle reserve remain
unused. Stage updates during lifecycle checks are not retained capture bundles.
The sealed M1 attempt ledger remains unchanged; subsequent progress lives in a
new status and feasibility probe ledger.

The before/after M1 acceptance verifier checks the same 38-file technical packet,
119 canonical source files, 60 evidence pins and retained historical acceptance
evidence. The current source/preset preservation result is reported separately
from the still-historical M1 status fields. No M2 dry-camera, segmentation,
occlusion, same-frame HDR/EXR/annotation or marine label pass is claimed.

## Reproduce or verify

Read-only evidence verification:

```bash
/usr/bin/python3 -B experiments/above_water_annotation_v1/qa/m2/verify_feasibility.py
```

Re-execution is optional, creates a new labelled run and requires host GPU/process
access. It refuses an existing Kit, insufficient resources or a reused profile:

```bash
/usr/bin/python3 -B experiments/above_water_annotation_v1/qa/m2/launch_probe.py new_renderer_probe renderer
```

There is no production rollback to apply. Owned failed groups were terminated;
passing processes exited themselves. No Kit remained after the probes. The
temporary profiles are explicitly listed in each `launch.json` and are retained
for diagnosis; deleting those exact owned temporary profiles is optional and
does not remove the retained evidence. Do not delete generic user cache folders.
