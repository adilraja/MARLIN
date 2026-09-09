# Bird working-copy cleanup — 2026-09-08

Original glTF, USD and licence files are retained. Working copies live under each avian's working/ directory. Each contains an editable Blender file, exported USD, copied licence, native world-space vertex measurements, and front/back/oblique previews.

| Bird | Current copy | X / Y / Z extent (native Blender units) | Review |
| --- | --- | --- | --- |
| Guillemot | support_cleanup_v3 | 2.899592 / 1.902747 / 2.939486 | Visible original foot restored using a traced selection; underside follows a sloped boundary. Hidden contact anatomy remains unverified. |
| Gannet | support_cleanup_v1 | 0.528264 / 0.611312 / 1.173504 | Main pedestal removed; foot-contact boundary remains unverified. |
| Storm petrel | support_cleanup_v1 | 54.036100 / 34.625000 / 22.064610 | Labelled base removed; ends of feet/attachments are trimmed and require review. |
| Common tern | support_cleanup_v1 | 1.285725 / 0.228825 / 0.204585 | Unchanged geometry; no separate support visible. |

These are axis-aligned vertex extents after parent transforms, in Blender's Z-up world. They are not anatomical body lengths, physical metres, or MARLIN Y-up measurements. The guillemot numbers describe a cropped candidate, not a verified complete bird. No physical scale or biological size has been assigned.

The reproducible preprocessing script is tools/clean_bird_working_copies.py. It starts from originals, rejects an existing output directory, and records exact selection thresholds and removed vertex counts. Use a new --version for another iteration. Mesh fragments span both bird and support, so removing whole objects is unsafe. The present edits use spatial vertex selection: contact boundaries are open and no replacement anatomy or caps were invented.

Visual QA reviewed multiple textured views. The four current USDs reopen with default prims and mesh geometry, and their asset dependencies resolve. This does not prove an anatomically correct model or equivalent Kit material rendering. Blender .blend files were saved before inspection cameras were added. Existing live scene references were not switched.

The earlier guillemot support_cleanup_v1 retains a rock fragment and is superseded by v2. incomplete_export_attempt is an intermediate Blender save from an unsupported exporter keyword; it is not a deliverable. These intermediate files are retained for recovery.

## Contact refinement

Guillemot v3 starts again from the original glTF. A manually traced polygon in a 900-pixel orthographic contact view retains the visible foot surface on the front side (world Y < -0.25). A sloped boundary follows the underside toward the tail, replacing v2's flat crop. The selection is recorded in the preprocessing recipe. Front, rear and oblique renders show the main rock absent and the visible original foot retained. There is no synthesized anatomy or hole filling. The hidden attachment surface cannot be verified from this scan.

The original contact close-ups are saved in guillemot/inspection/contact_*.png. Gannet and petrel v1 retain their existing geometry: their preview evidence shows the bases removed, but foot tips and contact boundaries remain imperfect. Removing more geometry would not establish missing anatomy. These are conservative working copies for review, not watertight or scientifically approved assets. Previous guillemot versions remain recoverable.

Next work: review the refined copies in Kit, then choose anatomical measurement landmarks and evidence-backed physical reference dimensions. Flight/sitting pose suitability remains a separate unresolved requirement.
