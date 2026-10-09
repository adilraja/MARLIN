# Paired five-GSD captures of one GAMA v2 state

The opt-in porpoise bridge can capture several camera conditions from one
resolved biological and environmental snapshot. It uses the existing NVIDIA
Kit Services bridge and MARLIN viewport renderer. Biological suitability
remains provisional; the static porpoise pose is an engineering proxy.

Acquire `/integration/gama/v2/actor/acquire`, replay actual version-2 states
through `/integration/gama/v2/actor/step`, then call:

```text
POST /integration/gama/v2/actor/paired-capture
```

```json
{
  "ownership_token": "<the acquired token>",
  "orders": [[0.5, 1, 2, 3, 4], [4, 3, 2, 1, 0.5]],
  "delay_s": 2
}
```

One to three orders are accepted; every order must contain each of the five
conditions exactly once. The bounded delay, between zero and five seconds,
is applied before every capture in the second and later orders. Ownership
must subsequently be released through the existing actor release endpoint.
The endpoint returns a unique output directory and `manifest.json`; it never
accepts arbitrary asset paths, code, camera scripts or renderer commands.

The transaction acquires the existing capture lock, gates application-driven
controllers and pauses the timeline. Before its first asynchronous wait, it
flattens the composed scene and evaluates all animated USD attributes at the
recorded source time. It retains current procedural ocean geometry. Every
condition is rendered from this same private frozen stage; the live stage is
retained strongly for restoration. The GAMA simulation clock is recorded
separately from ocean and USD timeline clocks, with no synchronization claim.

Camera geometry follows Pilot v1's validated generic 1024 × 768 route:
nadir ideal perspective, 50 mm focal length and 5 µm pixel pitch on the
explicit Y-up centimetre stage. Camera X/Z is chosen once from the selected
animal root and held constant. The animal is never repositioned between
conditions. The horizontal reference plane is the animal root's resolved Y,
which is minus its mean-sea-level depth in metres.

| GSD (cm/px) | Camera separation from root plane (m) | Reference footprint (m) |
| --- | --- | --- |
| 0.5 | 50 | 5.12 × 3.84 |
| 1 | 100 | 10.24 × 7.68 |
| 2 | 200 | 20.48 × 15.36 |
| 3 | 300 | 30.72 × 23.04 |
| 4 | 400 | 40.96 × 30.72 |

Only camera Y varies across the set. Height and footprint both vary. These
are direct pinhole sampling values at the root plane; underwater refraction
and anatomical-surface GSD remain uncalibrated. Actual composed optics,
camera matrices, viewport resolution and render-product delivery are checked
independently of the requested condition labels.

The frozen current presentation environment is retained. This preserves
pairing but does not reproduce Pilot v1's flat-water, diffuse-light survey
environment. No M4 diagnostic underwater light or follow camera is added.
Full native HiDef/Sony rendering is outside this integration check.

`resolved_state.json` binds the actual GAMA state, static pose mapping,
composed animal matrix, all resolved non-camera USD geometry/material/light
content, source clocks, renderer settings and dependency records. The
resolved scene-state hash excludes all Camera subtrees and `/Render`.
Camera-condition hashes and actual projections are recorded separately.
Local dependency bytes are rehashed during the transaction. Unresolved
runtime dependency paths/status are recorded explicitly and their bytes are
not inspected.

The wrapper checks scene identity and clocks before/after artificial delays,
warmup and every capture probe. It retains at least three probes per
condition and accepts consecutive full-image mean absolute RGB change below
1/255, with at most seven probes. This checks settling; it does not certify
RTX sample counts or pixel-identical replay. All probes, accepted PNGs,
image hashes and camera metadata are retained.

Each probe uses a new output path with the same generic
`capture_viewport_to_file` backend. The wrapper waits for the PNG to decode
completely, avoiding a stale image from the shared diagnostic `/tmp` path.
After stage attachment it also allows Kit to commit timeline setters before
requiring exact equality with the recorded source clock.

Cleanup restores the original stage, camera, resolution, fill mode,
selection, settings, display options, timeline and controller gates. The
original non-camera scene content and ocean clock are checked before live
updates resume. Capture errors and cancellation still execute cleanup. If
restoration cannot be verified, gates remain closed, a strong recovery
reference is retained, and the failure manifest reports `recovery_required`.

The bounded live acceptance client declares seed 184729, actual GAMA step 8
(t = 4 s, shallow swimming), both orders and the artificial delay before
inspecting images. It verifies the sealed M5 evidence and raw GAMA export,
captures the group, releases ownership and checks that the original eleven
demonstration animals and ocean resumed:

```bash
/usr/bin/python3 -B tools/verify_gama_paired_live.py \
  --output experiments/gama_marlin_v1/qa/m6_live_01
```

Use a new output directory for every attempt. `--preflight-only` performs
read-only scene/controller checks. Capture selection failures and unsuccessful
groups are retained; the client does not substitute more attractive states.
