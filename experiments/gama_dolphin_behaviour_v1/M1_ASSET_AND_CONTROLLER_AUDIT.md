# M1 — Audit the existing dolphin and preserve a baseline

Date: **5 November 2026**. Sprint: **MARLIN — GAMA–Omniverse Bottlenose
Dolphin Behaviour and Animation**.

**Technical audit ready; Gate A pending.** This report supplies the audit and
smallest proposed implementation scope. It does not record milestone
acceptance or authorise M2. No behaviour or animation changes were made.

## Baseline and execution boundary

The starting commit was `09186b3` on `main`. The full commit ID and dirty
worktree inventory were saved in [pre_work_state.json](qa/pre_work_state.json).
The user's sprint-document move, unfinished ocean M4 diagnostics, live logs,
presentations and other pre-existing work were preserved. No commit, push,
Kit restart, extension enablement or new GAMA execution was performed.

The audit used existing HTTP GET routes, two calls to the existing frozen
checkpoint endpoint, one existing viewport-preview call, and CPU-only reads
of the saved USD, glTF and baked samples. It did not acquire a GAMA actor,
start swimming, bind a clip, replace a rig or change a material.

## M1.1 — Existing GAMA and replay paths

The installed engine declares GAMA **2025.6.4**, commit
`ab35ccb69a12b3e2ac9e0b902662f24a82367995`, with bundled Temurin JDK
**21.0.7+6**. The launcher resolves to
`/opt/gama-platform/headless/gama-headless.sh`. Targeted launcher,
configuration and JDK-release reads are recorded in
[gama_runtime_inventory.json](qa/gama_runtime_inventory.json) and
[runtime_versions.json](qa/runtime_versions.json). No dependency was installed
or upgraded; no generated runtime directory was inspected.

The current MARLIN API exposed **zero `/integration/gama` routes**. Its
launch command enabled the render service, not the optional GAMA bridge.
There was therefore no active GAMA actor in this baseline. Source availability
and earlier execution evidence must be distinguished from current operation.

| Existing path | What it actually supports | Limitation for this sprint |
|---|---|---|
| `integrations/gama/trajectory.gaml` and `trajectory.xml` | Engineering circular bottlenose fixture; fixed shallow depth; v1 exchange | No controlled turn/descent/ascent sequence or body-animation state |
| `trajectory_live.gaml`, `tools/gama_live.py` | Existing WebSocket route for the legacy fixture | Uses that fixture's model/identity; not an executed Model 61A animation result |
| `tools/gama_trajectory.py` | Converts genuine GAMA XML, compares repeats and optionally replays v1 states | Replay targets the older allowlisted bottlenose asset |
| `integrations/gama/porpoise_behaviour.gaml`, `tools/gama_porpoise.py` | Record-first timed FSM, actual GAMA outputs, v2 clock/run identity and retained trajectories | Explicitly one harbour porpoise; circular horizontal path and static pose proxy |
| `tools/build_gama_porpoise_demo.py`, existing v2 capture/replay tools | Existing record/replay/freeze and capture plumbing | Species, asset and pose assumptions remain porpoise-specific |

The historical M3 raw XML and execution records under
`../gama_marlin_v1/trajectories/m3_seed_184729_a/` and `_b/` are actual prior
GAMA outputs. All 27 M3 manifest outputs verified against their sealed hashes.
They were not rerun or relabelled as this sprint's bottlenose result.
`integrations/gama/examples/step_v1.json` and `step_v2.json` are manually
authored contract fixtures, not GAMA execution evidence.

The v1 validator uses `time_s`, seed and agent pose; its scene actor accepts
only `shallow_swim`. The v2 contract adds run/agent identity, step index,
simulation clock and mean-sea-level depth, but rejects species other than
`harbour_porpoise`. Its five labels all map to the same static mesh.
Neither existing scene actor supplies the requested Model 61A manoeuvre and
body-animation contract unchanged.

## M1.2 — Exact target, provenance and dimensions

The selected animal is **DigitalLife3D — Model 61A - Bottlenose Dolphin**:

```text
assets/cetaceans/model_61a_-_bottlenose_dolphin/
    source/scene.gltf
    source/scene.bin
    source/license.txt
    usd/model_61a_-_bottlenose_dolphin.usd
    usd/textures/Dolphin_Body_baseColor.png
    usd/textures/Dolphin_Body_normal.png
```

The USD SHA-256 is
`ab9d77b06378b834231ec4f815f4f0eb532f7b1623cb401c37079ccddd0e5c93`.
The retained licence identifies DigitalLife3D and CC-BY-NC-4.0 and carries the
original model URL and attribution. Source files and both texture hashes are
listed in [asset_provenance.json](qa/asset_provenance.json). No licence or
anatomical identity was inferred from the generic word "bottlenose".

The source USD, the frozen live `/World/Cetaceans/Dolphin_001`, and the accepted
water demonstration have identical mesh point/topology signatures and joint
names. There are **two skinned meshes, 21,504 authored vertices and 40,208
faces**, with one 20-joint skeleton. No Icosphere/helper mesh was present in
this selected glTF/USD; nothing was removed. The original source remains
untouched.

The live stage is **Y up, 0.01 m per scene unit**. The source USD is **Z up,
1 m per unit**. The existing animal has root translation `[0,-20,0]`, root
rotation `[0,0,0]`, root scale `[100,100,100]`, and a separate Model correction
of `[-90,0,0]` degrees. Composed source-parent transforms were included in
measurement. Authored head and tail joint positions support +Z as forward in
this corrected instance; anatomical landmark approval was not asserted.

Three different bounds were measured separately:

| Method, live frozen instance | X × Y × Z in metres | Interpretation |
|---|---|---|
| Authored mesh vertices after composed transforms | 0.753470 × 0.604234 × 2.491631 | Mesh coordinates before skeletal rest-pose evaluation |
| CPU `UsdSkel` evaluation of the existing rest pose | 0.764557 × 0.611640 × 2.464569 | Evaluated skin vertices; independent of an RTX pixel measurement |
| Composed `BBoxCache` extents | 0.826694 × 0.837127 × 2.586461 | The bound used by live inspection and the earlier water demonstration |

These are geometry bounds, not rostrum-to-notch length or biological size
validation. The earlier 2.586 m bound was not silently substituted with a new
scale. The initial raw-vertex audit is retained; its measurement description
was refined to distinguish skinning and cached extents in later audit records.
No acceptance tolerance was changed to obtain these results.

The skinning calculation used the installed USD API on CPU with the existing
bound skeleton and default pose. The transform-space interpretation follows
the [OpenUSD skinning query documentation](https://openusd.org/release/api/class_usd_skel_skinning_query.html).
The [geometry sheet](baseline/figures/geometry_views.png) shows saved geometry
and authored joint labels; it is not an RTX render or a new anatomical review.

## M1.3 — Animation inventory

The source glTF contains one 20-joint skin and a **Swim Cycle** action with
56 channels. The selected USD, accepted water snapshot and current live
checkpoint each contain **zero `UsdSkelAnimation` prims, zero time-sampled
attributes under the animal and no animation clip metadata**. The skeleton's
animation-source relationship is empty. A source action did not survive as
an active clip in this USD.

The existing reusable bake is:

```text
assets/cetaceans/bottlenose_dolphin/animation/swim_cycle.json
```

Despite that older directory name, the bake tool's legacy input glTF and binary
are byte-identical to the selected Model 61A source files. This provenance was
checked independently; no rebake was run. The file contains **31 samples,
frames 1–31 at 24 fps, a 1.25 s loop, and 20 rest-relative joint TRS tracks**.
All normalized bone names match the selected USD skeleton in order. Nineteen
joint rotation tracks change. The synthetic top root is stationary; `MAIN_18`
has changing rotation and constant local translation. No varying locomotion
translation was found on those two tracks.

Endpoint translation and quaternion comparisons returned zero differences for
the sampled tracks. This is a file-level loop check; velocity continuity,
evaluated animated skinning, rendered deformation and a credible turn/dive
response remain unverified. The two existing baked-animation tests passed.
No clip was bound during this audit.

`skeletal_animation.bind_baked_skeletal_animation` already checks joint order,
converts rest-relative samples against USD rest transforms and authors an
animation-source relationship. Both the single-swimmer and gallery controllers
can call it. Their playback uses frame-event `dt` and writes the **shared Kit
timeline**. Reusing that clock directly would conflict with this sprint's
simulation-time and per-instance ownership requirements.

The source glTF, USD skeleton, existing baked samples, loop observations and
live rig response are retained in [asset_inventory.json](qa/asset_inventory.json)
and [rig_Dolphin_001.json](baseline/live_before/rig_Dolphin_001.json).

## M1.4 — Movement and pose ownership

| Mechanism | Possible writes | Observed baseline / conflict |
|---|---|---|
| Single cetacean swimmer in `cetacean.py` | Root translation, heading, dive/surface Y, pitch/bank, optional shared timeline | Stopped. Combines autonomous movement and animation; cannot run alongside a GAMA world owner for the same instance |
| Gallery callback in `cetacean_gallery.py` | Gallery roots; procedural mesh points; shared timeline for skeletal target | Stopped, zero gallery controller entries. Its catalogued DigitalLife target is a separate name, not an active controller for `Dolphin_001` |
| GAMA v1 `actor.py` | Private root position/heading on validated messages | Extension inactive. Selects `assets/cetaceans/bottlenose_dolphin/usd/bottlenose_dolphin.usd`, a different USD from Model 61A; no body animation |
| GAMA v2 `actor_v2.py` | Private porpoise root position/heading, static pose | Extension inactive. Owns a different species/asset; no automatic movement between messages |
| Authored animation / timeline | Bound joints or time-sampled attributes when present | No active clip or samples on the baseline animal. Future global timeline writes could affect unrelated actors |
| Manual transform, spawn and marine setup endpoints | Change or replace named `/World/Cetaceans` instances | Explicit operations, not observed autonomous writers. Must be excluded from an owned experimental run |
| Ocean callback / sampler | Ocean vertices; heights consumed by a following swimmer | Running. No direct animal writer; GAMA's authoritative depth must not accidentally acquire wave-following motion |
| Chase camera | Camera pose and framing | Running in HOLD; does not write the animal |

Only one animal was observed in this live stage. This audit does not claim a
new coexistence test with eleven active swimmers. The existing private-layer
actor lifecycle provides an appropriate starting point for isolating one
experimental instance after Gate A. No controller subscription was stopped,
started or redirected during M1.

## M1.5 — Water, hardware and capture configuration

The live process is Kit **110.2.0+feature.342835.698af100.gl**, app `cris.madil`
0.1.0. The GPU is an **RTX A2000, 6,138 MiB**, driver **595.99.02**. The
baseline observations left about **1.8 GiB free**. Immediately before and after
the single preview, sampled use was 3,927 MiB with 1,872 MiB free. These two
samples are not an exact allocation peak.

The inherited live water selection was **`original`**, with thin-walled
OmniSurface on the top ocean grid; the accepted `engineering_v1` preset was
available but not selected. The audit preserved this live selection and
verified the accepted preset, dependencies and M5/M6 evidence separately.
Later controlled demonstrations should explicitly select the unchanged
`engineering_v1` preset and restore this saved baseline on cleanup.

The ocean remained running at size 16,000, resolution 128, speed 0.7,
choppiness 0.55 and target 15 updates/s. The active preview remained
1280 × 720 with the existing chase camera. Its wave phase continued advancing.

The qualified saved-image route remains the prior **512 × 384 PathTracing
HDR/EXR with fixed display conversion**:

```text
round(255 * clip(HDR_RGB / 12000, 0, 1) ** (1 / 2.2))
```

The existing capture helpers and accepted M5/M6 procedures were inspected,
not rerun. The current public preview endpoint returns PNG only. The new
[viewport preview](baseline/preview_01/current_viewport.png) is washed out and
the dolphin is small; it is retained as operational baseline evidence and
cannot judge animated deformation or qualify native LDR output. M1 did not
add a new capture endpoint or restart Kit to run a different capture script.
The [prior accepted material comparison](../ocean_material_v1/diagnostics/m6/figures/material_comparison.png)
is linked as historical evidence of this same asset, not a new M1 rendering.
No motion recording was started because the observed animal controllers were
stopped. Camera-inside attenuation and native survey resolution remain outside
this audit's acceptance.

The first sandboxed localhost/GPU probes failed due to restricted access;
approved host-side reads succeeded. Those probe failures did not establish a
new driver mismatch or require a driver change.

## M1.6 — Preservation and baseline recovery

The first saved scene was **`checkpoint_qippped8`**. Its verified bytes and
metadata were also copied to `baseline/live_before/`. A final checkpoint and
the independent before/after HTTP observations are in `baseline/live_after/`.
CPU USD reopening and skin queries succeeded.

[Twenty preservation checks](qa/final_preservation.json) passed: the same live
layer stack, animal transforms, stopped animal controllers, material selection,
chase configuration/pose, camera, resolution, render settings and timeline
value remained, while the ocean continued advancing. All **250 pinned source,
integration and tool files** remained byte-identical. The accepted water
M5/M6 package verifier passed before and after the audit.

Historical GAMA M3, M8 and final closeout outputs verified. A literal M7 hash
check reported four historical production-source version mismatches. Each
current hash exactly matches the pre-M1 source inventory; all four predated
this work. Non-source outputs verified. The raw failed result and
[explicit disposition](qa/historical_gama_source_pin_disposition.json) are
retained; no historical seal was rewritten to turn the check green.

The checkpoint saves a frozen visual scene and selected settings, not live
Python controller subscriptions, tokens or an atomic simulation-clock snapshot.
Public controller status was recorded on either side of serialization.
The [recovery instructions](BASELINE_RECOVERY.md) distinguish reopening frozen
geometry from restarting configured controllers; exact wave-phase continuation
is not claimed. A live restore/restart was unnecessary and was not performed.

## M1.7 — Capability assessment and Gate A proposal

| Capability | Assessment |
|---|---|
| Exact Model 61A identity, source and accepted water-demo match | Passed CPU geometry/joint checks and dependency hashes |
| Existing rig and matching baked swim data | Available; 20-joint compatibility and sampled loop closure verified |
| Current visible swimming | Inactive; no bound clip or running swimmer |
| Existing isolated GAMA lifecycle and prior engine outputs | Implemented and historically executed for other fixed actor contracts; inactive in current session |
| Model 61A GAMA manoeuvre contract | Missing |
| Simulation-time-indexed independent body pose | Missing; existing frame-driven shared timeline is conflicting |
| Local turn/descent/ascent body response and blending | Unverified; the swim loop alone does not establish these capabilities |
| Complete future animation snapshots, seek and replay | Unverified; current frozen-scene checkpoint is insufficient alone |
| Biological suitability | Provisional; no new biological approval |

The [implementation proposal](IMPLEMENTATION_PROPOSAL.md) recommends reusing
the selected asset, existing rig and baked cycle, a private actor using the
current bridge lifecycle, and a simulation-time-controlled pose evaluator.
It proposes no replacement rig or new animation framework. Any later need for
substantial asset work must return for a bounded review decision.

**Gate A remains pending.** The required decision and evidence links are in
[GATE_A_REVIEW.md](reviews/GATE_A_REVIEW.md). No M2 contract, new GAMA model,
animation binding or controller refactor has begun.
