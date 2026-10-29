# Corrected effective-settings protocol, before acceptance rerun

The first 14 planned captures (five controls and nine absorption comparisons)
are retained under `captures/` and the original `qa/*_execution.json` files.
Their exported USD render products retained fog=true despite carb fog=false;
target HDR luminance also stayed nearly constant as channel colour changed.
Global settings alone did not establish the requested optical controls.
Those captures are diagnostic attempts, excluded from acceptance and any
physical coefficient interpretation. `qa/uncontrolled_medium_source.py`
preserves their source. M1/M2 packages are not rewritten.

The corrected run uses the same predeclared physical fixture, ROIs, sweep,
3% equivalence/effect tolerance and 768 MiB GPU guard. It explicitly authors
the **registered** USD attributes on the isolated camera and render product:
autoExposure=false; exposure=0 stops; exposure:time=1, fStop=1, iso=100,
responsivity=1; product fog=false and tonemap operator=acesApproximation.
The installed schema names/types/defaults were queried via the registry and
retained in `qa/schema_capabilities.json`. No speculative settings or vendor
edits. Each capture retains effective camera/product attributes, including
schema defaults, and asserts fog and auto exposure are still false after
settling. HDR is explicitly requested on that product. A raw-operator probe
and a separate +1-stop camera exposure probe check the output domain.

Corrected captures go to `captures_controlled/`, execution logs to
`qa/controlled/`; historical attempts remain in place. No scene-unit change
to MARLIN, restart, extra ray budget or production preset change.
