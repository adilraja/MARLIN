# M4 underwater-camera follow-up: unresolved

Fifteen native captures completed. All twelve inside-camera views remained
neutral; three above-water controls showed that material attenuation was active.
A flat closed enclosure reproduced the inside failure, including clear-water
and disabled-cache controls. The original scene and settings were restored.

Read `../../reports/M4_UNDERWATER_CAMERA_FOLLOWUP.md` and
`NVIDIA_SUPPORT_CASE.md`. The latter is an unsent draft. The original M4 package
and its historical evidence remain unchanged; its source pins describe the
earlier implementation. This follow-up changes bounded diagnostics only and
does not qualify or enable a production underwater-camera fix.

The existing fixed capture endpoint now accepts `underwater_followup:true`
to write a fresh directory here. It does not overwrite the initial M4 package.
Probe names are a finite allowlist in `CaptureRequest`; no arbitrary setting,
shader, input file or output path can be supplied. The default `medium_probe`
remains `none`. Non-default probes require a frozen engineering-preset request
and the follow-up flag. Native shader probes deliberately change the temporary
diagnostic water material; they are not production water presets.

Example, with the existing marine scene and both animal/chase controllers
stopped:

```bash
curl -sS -X POST http://localhost:8011/scene/ocean/material/preset/diagnostic/batch-preview \
  -H 'Content-Type: application/json' -d '{"action":"begin"}'
curl -sS -X POST http://localhost:8011/scene/ocean/material/preset/diagnostic/capture \
  -H 'Content-Type: application/json' \
  -d '{"selection":"engineering_v1","view":"inside","phase_seconds":1,"underwater_followup":true,"medium_probe":"flat_box"}'
curl -sS -X POST http://localhost:8011/scene/ocean/material/preset/diagnostic/batch-preview \
  -H 'Content-Type: application/json' -d '{"action":"end"}'
```

Always end the bounded preview session, including after a capture failure.
The 768 MiB guard remains enabled. A new capture allocates a new directory;
the retained fifteen-record validation describes this recorded run only.

`qa/analyse_followup.py` reproduces the saved-data/restoration checks and the
labelled fixed-scale HDR comparison. It asserts that the failed inside views
are still failed; successful file/geometry checks do not constitute an optical
pass. `manifest.json` pins final diagnostic source, exact pre-follow-up source,
the patch, figures, records and sealed logs. Mutable app logs are ignored.

No runtime upgrade, vendor modification, artificial camera shell, new density
grid or image-space attenuation was introduced. M4 remains open pending a
supported inside-medium rendering solution.
