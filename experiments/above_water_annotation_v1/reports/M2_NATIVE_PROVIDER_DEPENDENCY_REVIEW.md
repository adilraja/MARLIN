# Native-provider dependency review — preparation stopped before installation

Date: 9 November 2026. **Not ready to approve installation.** The required exact
provider package and dependency closure have not been resolved. No installation,
main runtime upgrade or default-service dependency change was performed.

The accepted [Gate A proposal](IMPLEMENTATION_PROPOSAL.md) requires a stop before
new dependencies and a concrete package/version, graph, compatibility evidence,
disk estimate, isolation destination, preservation pins and rollback. This
record distinguishes what is known from what still has to be obtained.

| Item | Established evidence / remaining requirement |
|---|---|
| Existing runtime | Kit 110.2.0, build hash `698af100`, Linux x86_64, CPython 3.12 extension variants; driver 595.99.02 |
| Installed provider | Neither `omni.replicator.core` nor `omni.syntheticdata` in the configured 224-entry MARLIN inventory or the separately queried 102-entry existing isolated SDK inventory |
| Intended API | Supported Replicator instance segmentation, HDR and boxes, subject to the unchanged dry/native and marine gates |
| Replicator root pin | **Unresolved**; the 110-line 1.13.27 documentation listing is not accepted as a 110.2 binary pin |
| SyntheticData support pin | **Unresolved**; the 110.2 SDK page links to 0.6.15 documentation, without supplying a resolved package ID, checksum and closure here |
| Dependency graph | **Unresolved**; no fabricated version choices or sizes |
| Existing core components | Local inventory records exact package IDs for USD, RTX, renderer capture, OmniGraph and other dependencies; these remain preserved inputs |
| Disk estimate | **Unresolved** until metadata provides archive and expanded byte counts; existing capture budget is not an extension-size estimate |
| Proposed private destination | `experiments/above_water_annotation_v1/dependencies/native_provider_1102/`, not created or populated by this work |
| Main installation | No package written into its generated folders; no main app/source/driver change proposed |

## Smallest next action

Obtain **metadata only** from a supported official registry path or NVIDIA,
without pulling or unpacking extension content. Two initial queries kept index
access disabled; two further probes temporarily allowed private index access,
including an explicit refresh, restored that gate and verified unchanged
installed package IDs. All returned no usable metadata / sync false. The
limited direct metadata endpoint checks returned 404. A supported metadata
access path or package information is still needed. It must separate
index access from any enable/pull/precache operation and retain the configured
110.2 registry URLs, failures and returned metadata. Do not treat these limited
404s as a confirmed registry outage or select a different Kit ABI to bypass it.

Before asking to install anything, produce all of:

1. Exact provider and supporting package IDs, package versions and platform /
   Python / Kit build filters, source URLs and checksums. Demonstrate that the
   selected closure matches `698af100`, not merely another Kit 110 release.
2. The full resolved dependency graph and a difference against the saved local
   package inventory. Identify any core replacement. Stop for a new scope
   decision if a main Kit, USD, renderer or driver replacement is required.
3. Compressed and expanded disk estimates based on metadata, a finite disk cap,
   a private registry/cache/profile destination, and exact proposed commands
   that cannot write to the normal MARLIN installation.
4. Source, preset and accepted-evidence pins verified immediately before that
   action; the present preservation pins and M1 acceptance verifier are the
   starting reference, not permission to overwrite later work.
5. Rollback confined to the proposed isolated dependency/profile directory,
   owned-process cleanup and a fresh normal-service/resource check. Retain
   failures and do not delete the original M1/M2 evidence.

Only after review of that concrete proposal should dependency content be
installed in isolation. Re-run the provider/lifecycle and resource checks before
the sixteen declared dry bundles. A provider that cannot satisfy native mask,
identity, occlusion and same-frame provenance requirements does not pass Gate B.

The exact current stop is a dependency/compatibility boundary. It is not the
separate ocean-material underwater-camera issue and does not authorize changing
the accepted dolphin or water implementations.
