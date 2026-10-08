# First M4 live run: visual evidence rejected

The retained `m4_live_01/results.json` passed its automated transform, failure,
coexistence and cleanup assertions. The raw six viewport frames were then
inspected and showed the gallery overview rather than the requested porpoise
diagnostic view. The automated `passed` flag is therefore **insufficient for M4
acceptance**, and this run is not the final visual demonstration.

The camera property and restoration assertions did not prove that the renderer
had delivered the new camera. Keep these files unchanged as the original
observation. The corrected capture must wait for delivered frames and verify the
render-product camera before a new run is accepted. Final acceptance is recorded
separately after inspecting the new actual frames.
