# Ocean material sprint

The sprint specification is preserved in `specification.md`.

Milestone 1 audit and baseline evidence were collected on 29 October 2026.
Start with `reports/M1_OCEAN_MATERIAL_AUDIT.md`, followed by
`reports/ACCEPTANCE_PLAN.md`, its explicit version 2 amendment and `reports/ROLLBACK.md`.

- `baseline/frozen_02/` is the accepted, frozen appearance baseline: one warm-up,
  three measured repeat images, exact sampled scene and checkpoint metadata.
- `baseline/material.json` and `baseline/installed_material_definition.json`
  identify the effective binding, geometry and installed shader declarations.
- Earlier baseline exports and `frozen_01/` are retained diagnostic/failed-attempt
  evidence. Their wave phases must not be substituted for `frozen_02/`.
- `qa/` preserves startup logs, script versions, failures, restoration checks,
  source/integrity checks and hardware observations.

The current ocean already uses OmniSurface, with thin-walled transmission on an
open mesh. M1 did not implement a new material. Physical shader-distance scaling,
finite-medium correctness and metric viewport conformance remain unverified.
The next milestone is the isolated transmission/refraction diagnostic, not a new
dataset or training run. No human review acceptance has been inferred.

Tests executed:

```bash
python3 -B -m unittest discover -s source/extensions/cris.madil.render_service/cris/madil/render_service/tests -p test_water_material.py -v
python3 -B -m unittest discover -s source/extensions/cris.madil.render_service/cris/madil/render_service/tests -p test_renderer_snapshot.py -v
```

Run those from the repository root. Nine tests passed. Production source was not
edited. All 4,859 previous closeout-sealed inputs still matched their hashes.

Kit is left running with the original marine setup and restored ocean/chase
controllers; swimming is disabled as declared for this reconstructed baseline.
Active Kit logs may continue growing and are marked mutable in the manifest.

Committed `qa/*_snapshot.log` files preserve the active logs at commit preparation.
Their live counterparts remain local and may continue growing. `.gitattributes`
preserves exact evidence bytes rather than normalizing line endings.
