# Gentle overcast environment review

Apply to an already running marine ocean and gallery:

```sh
curl -sS -X POST http://localhost:8011/scene/environment/gentle-overcast
```

Restore the saved water/lighting settings in the same Kit session:

```sh
curl -sS -X POST http://localhost:8011/scene/environment/gentle-overcast/restore
```

The preset uses the existing Gerstner ocean with a 20 scene-unit amplitude
budget (20 cm for this stage), 900-unit primary wavelength, choppiness 0.12,
speed 0.3, 128 grid subdivisions and 15 updates/s. These are engineering
appearance choices, not a validated Beaufort sea state or wind simulation.
The diffuse neutral sky has intensity 500, with directional sun disabled.
One blue-green transmissive water material is used. Soft environmental
reflections remain; direct sun glint is absent. Fog is disabled for this view.

The original flat scientific preset and demonstration endpoints are unchanged.
No animal assets, swimming algorithms or camera controls are edited by the
new endpoints. Existing specimen poses/scale issues remain out of scope.

Verification: four scope/preset tests pass; source syntax checks pass. Live
apply/restore preserved 11 running gallery swimmers. The initial source hot
reload stopped animation callbacks; the existing marine/gallery controls were
resumed for testing, without recreating animal assets. `before.png` is the
restored baseline, `after.png` the final overcast view; animal positions differ
because motion continues. `swimming_status.json` records the final status.

Restoration is session-local and requires the same stage and loaded extension.
It restores the saved composed environment/material and wave parameters, not
animal positions or ocean elapsed time: wave phases restart. The live ocean
uses variable wall-clock updates, so fixed phase/parameters are repeatable
initial conditions, not a frame-deterministic dataset. Do not change stages or
reload the extension before restoring. No data-generation milestone is claimed.
