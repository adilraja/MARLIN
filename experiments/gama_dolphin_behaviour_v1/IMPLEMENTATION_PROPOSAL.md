# Gate A — smallest proposed implementation scope

**Proposal only, 5 November 2026. Approval pending.**

This proposal follows the [completed technical audit](M1_ASSET_AND_CONTROLLER_AUDIT.md).
It is the review input for Gate A, not an implemented contract or a new
biological parameter specification.

## Recommended scope

1. **Keep the exact Model 61A asset and its current engineering scale/material.**
   Use the hashed USD and textures already demonstrated in the water sprint.
   Preserve the Model child's `[-90,0,0]` correction and the equivalent scale
   for the inspected 0.01 m/unit stage. Keep source calibration separate from
   dynamic attitude. No source mesh, texture or licence edit is proposed.

2. **Extend the existing optional GAMA bridge for one private Model 61A actor.**
   Reuse removable-layer ownership, explicit tokens, validation-before-mutation,
   duplicate/stale handling, capture gating and release. Use an explicit new
   version or endpoint family for the new bottlenose contract. Keep the old
   v1 bottlenose and v2 porpoise contracts and their accepted evidence intact.
   Do not broaden the old porpoise schema's species field silently. Enabling
   the optional extension is later integration work after this gate.

3. **Make GAMA simulation time authoritative.**
   After Gate A, M2 should define the clock, state-entry/transition information,
   coordinate mapping, one vertical input, orientation ownership, interpolation
   rules and locked numerical tolerances. A mean-sea-level datum is the
   recommended starting point because the existing v2 route uses it; M2 must
   explicitly resolve its suitability. Use the wave sampler for declared
   checks where needed, with no accidental second vertical controller.

4. **Reuse the existing skeleton and baked swim-cycle data.**
   Reuse the existing rest-relative conversion and joint-order checks. Add a
   per-instance pose evaluation path whose phase is derived from recorded
   simulation state. It must not advance the shared Kit timeline or create a
   second world translation/heading. Verify root-joint and `MAIN_18` effects
   separately from the motion root. Sampled loop closure and matching joint
   names are sufficient to justify trying this path, not to accept its
   rendered deformation or manoeuvre response.

5. **Limit animation adaptation to demonstrated needs.**
   First execute and inspect the retained swim cycle after the ownership/time
   contract and trajectory gate. Test local body response for turning,
   descent and ascent, blends, pauses and loop boundaries. If the existing
   data cannot support coordinated motion, mark the state limited and return
   with a specific refinement proposal. A rig replacement, substantial new
   skinning or a replacement animal requires a separate review decision.

6. **Use a small, reversible demonstration and the accepted water route.**
   Select the unchanged `engineering_v1` preset explicitly during the later
   experiment, with cameras above water, bounded captures and the existing
   memory guard. Restore the saved original-preset baseline afterward. Preserve
   prior camera/annotation contracts. Complete evaluated body-state freeze,
   seek, reload and lifecycle evidence in M5; the existing visual checkpoint
   alone does not satisfy that future requirement.

## Expected implementation locations after approval

| Location | Bounded change under the later milestone |
|---|---|
| `source/extensions/cris.madil.gama_bridge/` | New explicit bottlenose contract/owned actor, reusing existing lifecycle and state checks |
| `source/extensions/cris.madil.render_service/` | Small reusable instance-pose evaluation helper if needed; preserve existing swimmer/gallery entry points |
| `integrations/gama/` | Versioned bottlenose reference model after M2, based on inspected existing GAMA patterns |
| This experiment's `config/`, `gama/`, `trajectories/`, `animation/`, `snapshots/`, `qa/` | New configuration, actual runs, comparisons and review evidence, without rewriting earlier packages |

File names and schema version numbers should be selected in M2 after checking
the compatibility surface. This proposal does not preapprove arbitrary API
expansion, remote code execution or general species/character frameworks.

## Dependencies and boundaries for the next gates

- Gate A accepts this asset/controller assessment and bounded change scope.
- M2 establishes and tests the contract and freezes tolerances before new
  acceptance runs. No M2 code has been written in this audit.
- M3 must retain actual new GAMA executions: the controlled sequence and three
  declared seeds with fresh-process repeats. Prior porpoise states remain
  historical evidence and reusable infrastructure examples.
- Gate B reviews realised trajectories before animation integration.
- M4 must demonstrate supported coordinated body motion and seek Gate C
  review; a root-only proxy cannot silently satisfy that requirement.
- M5/M6 must demonstrate body-state reproducibility, capture/cleanup and named
  visual review. Engineering correctness, visual plausibility and biological
  support retain separate statuses.

The proposed initial implementation needs no source-asset derivative or new
rig. Its feasibility remains conditional on the later executed body-motion
tests. Biological speeds, tail-beat rates, banking angles and dive limits are
not prescribed here; their evidence status belongs in the later parameter
register and review.
