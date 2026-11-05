# Bottlenose v3 constrained movement demonstration

`bottlenose_constrained_v1.gaml` is the canonical M3 model for the **MARLIN —
GAMA–Omniverse Bottlenose Dolphin Behaviour and Animation** sprint. It adapts the
existing record-first porpoise clock/export pattern and uses the accepted v3
single-bottlenose boundary. Existing v1/v2 models and endpoints remain unchanged.

The model executes a 74 s sequence of steady motion, turn, descent, submerged
motion, ascent and return to steady motion. Quintic controls and explicit SI
variables define its movement; global x/z/depth outputs are authoritative, rather
than native display/GIS coordinates. Recorded speed is horizontal speed.

The runner is `tools/gama_bottlenose.py`; the independent acceptance oracle is
`tools/analyze_gama_bottlenose.py`. Both work offline without a MARLIN HTTP client.
The engineering parameters, frozen movement bounds, actual raw GAMA runs, figures,
repeatability checks and Gate B packet are retained under
`experiments/gama_dolphin_behaviour_v1/`.

See that experiment's `M3_MOVEMENT_MODEL_AND_PARAMETER_REGISTER.md` and
`M3_REPRODUCTION.md` for the exact provenance, commands and limitations. All animal
movement numbers are explicit engineering assumptions; no biological validation
or body-animation integration is claimed. Gate B acceptance is required before
M4 body-animation work.
