# M8 offline regression scope and historical failure disposition

All **360 unittest cases passed**, with zero skips. The extra Pilot metric self-check also passed. The original run-level `passed:false` remains unchanged because a separate historical packaging entrypoint failed.

| Scope | Passed cases |
| --- | ---: |
| existing_marlin_service | 77 |
| existing_camera | 30 |
| bridge | 100 |
| capture | 145 |
| existing_pilot | 8 |

The USD suites used Blender Python 3.11.13 with USD 0.25.8 for real stages, layers, calibrated assets, transforms, removals and projections. Kit viewport, renderer, timeline, HTTP and GPU boundaries were injected fakes where those suites required them; image fixtures do not constitute rendered or biological validation. Pure suites used system Python 3.14.4. Exact commands, runtimes, durations and stdout/stderr hashes are in [results.json](results.json) and each execution record.

All 283 pinned source/input files stayed unchanged. AST syntax checks passed for 139 Python files, and `git diff --check` returned 0. This offline command made no live Kit calls, GPU renders, GAMA executions or ML training runs.

The historical [m7_package.py](../../../gsd_pilot_v1/qa/m7_package.py) stopped at line 33: `assert spec["schema_version"] == "1.6.0"`. The current preserved final specification is **1.7.0**, SHA-256 `6a0035aabf42cb1ce1caa64668c2dee0e0506215def673bd35e771bc00f12471`; its archived M7 specification is **1.6.0**, SHA-256 `c6c777cc19de3b7084b314a76c6c2ce92ef0ee18b938bf33a34e4ab5fc9f815d`. Both match their entries in the preserved baseline manifest.

No package outputs were written: the failing assertion preceded the script's sole output write at line 93, and the existing M7 package manifest matched both pre/post execution pins and its preserved baseline hash. The [original traceback](pilot_sealed_package.stderr.log) and failed execution remain unchanged. No source fix, Pilot rewrite or successful rerun was substituted.

This extra historical failure does not invalidate the 360 current regression passes or an independently retained live demonstration audit. These offline artifacts do not certify live rendering, optics, biology or completion of the blocked M7 150-view dataset.

[Machine-readable disposition](historical_package_disposition.json) contains the assertion, original command/result, current and historical specification pins, baseline evidence and write-boundary analysis.
