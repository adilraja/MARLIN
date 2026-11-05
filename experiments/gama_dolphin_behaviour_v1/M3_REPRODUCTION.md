# Reproduce the M3 movement evidence

The model runs offline and has no MARLIN HTTP client. Its canonical source is
`integrations/gama/bottlenose_constrained_v1.gaml`. Run from the repository root
with the installed GAMA 2025.6.4 headless launcher on PATH.

## Verify preserved evidence without starting GAMA

```bash
/usr/bin/python3 -B experiments/gama_dolphin_behaviour_v1/qa/m3/verify_package.py
```

This checks pinned files, retained raw-output consistency, repeatability,
implementation/configuration/runtime identities and the accepted earlier packages.
It does not acquire an actor or regenerate plots over the preserved results.
The existing earlier checkpoint verifiers also require their local artifact store;
this is not a redistributed self-contained GAMA/Kit installation.

## Execute a fresh reference or seeded run

Choose a new run ID each time. Both the output directory and workspace must be
unused. Outputs go to `experiments/gama_dolphin_behaviour_v1/trajectories/<run_id>`;
the isolated workspace goes to `artifacts/gama_dolphin_behaviour_v1/workspaces/`.

```bash
/usr/bin/python3 -B tools/gama_bottlenose.py \
  --run-id m3_new_reference_001 --seed 184729 \
  --lock experiments/gama_dolphin_behaviour_v1/qa/m3/implementation_lock_attempt01.json

/usr/bin/python3 -B tools/gama_bottlenose.py \
  --run-id m3_new_seed42_001 --seed 42 --variation \
  --lock experiments/gama_dolphin_behaviour_v1/qa/m3/implementation_lock_attempt01.json
```

The second command enables the three declared initialization draws. First prove
the reference and its repeat before accepting a new stochastic campaign. Repeat
with another unused ID; compare canonical state bytes using
`tools.gama_bottlenose.canonical` (or add `tools` to Python's module path). Only
run IDs are excluded. Raw XML contains execution identities and is not expected
to have the same hash between independently named runs.

Each `execution.json` retains the actual launcher command. The wrapper follows
the established legacy-headless XML pattern with an explicit 1 GiB Java heap,
unique `-ws` path and 297 steps. Each XML plan includes all effective model
parameters, whose actual exported values are checked. Failed output directories
are retained. Do not rerun the completed campaign script in place: it deliberately
refuses its existing report and run/workspace identities.

## Recheck the acceptance implementation

```bash
/usr/bin/python3 -B tools/test_gama_bottlenose.py /tmp/m3_new_test_result.json
```

Use an unused output filename. This suite uses the retained actual GAMA reference
and injects failures to verify rejection. The first harness attempt and its
amendment remain in the evidence package. Numerical tolerances and the model
were unchanged by that correction.

## Recovery and later integration

No runtime recovery is needed for these offline runs. MARLIN stayed running with
its accepted scene and no v3 owner. Stopping or finishing GAMA does not start a
MARLIN swimmer. M3 does not call scene setup, change water/cameras or bind a clip.

The M1/M2 scene recovery procedures remain authoritative if a separate runtime
operation requires restoration. The M2 original and final scene copies remain
preserved. Gate B must be accepted before any M4 body-animation work. Biological,
optical, deformation and final visual acceptance remain separate decisions.
