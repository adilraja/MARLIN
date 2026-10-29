# M2 controlled transmission/refraction plan

Recorded before the first M2 capture, 29 October 2026.

Use the current installed renderer and the existing isolated calibration capture
helper. The production ocean, animal assets and camera profiles are not edited.
The fixture uses a separate USD context, explicit Y-up and 0.01 metres per unit.
The single white emissive fiducial is 0.18 x 0.18 m, centred at (0,-1,0) m on an
opaque black background at y=-1.02 m. Fixed red/green environment markers lie at
z=-4 m, y=4..6 m; they are outside the direct target view and diagnose reflection.

The water boundary is one closed, outward-wound six-face box, bounds
(-5,-2,-5)..(5,0,5) m, with no duplicate top interface and no normal detail.
Check each edge has two faces, each face normal points outward, and the target
lies inside. Use existing OmniSurface authoring, thin_walled=false, fully present
geometry, transmission=1, white transmission colour, zero scatter colour/depth,
base_weight=0, roughness=0.001. Do not claim zero physical absorption has been
calibrated from the depth control. Air index 1.0 and water index 1.333 are declared
engineering assumptions; the matched control uses index 1.0 throughout.

Capture 512 x 384, 35 mm focal length, 40 micrometre pitch, camera 4 m vertically
above the target. Nadir pitch is 0 degrees; oblique pitch is 40 degrees using the
existing calibration-camera basis. Thus camera y=3 m and oblique z=4*tan(40°).
The focal length in pixels is 875, and authored apertures match image aspect.
Verify projection through the existing helper, not by trusting window dimensions.

Conditions: dry/no water, closed index-matched medium, closed water candidate.
Capture nadir and oblique views for each, one warm-up and one retained RGB per
condition. Target mesh/material/pose, lighting and camera remain fixed within
each view. The dry control omits only the water, not the submerged target.
Disable the existing global height-fog cue and auto exposure only for this
isolated diagnostic, record actual settings, and restore them in finally.

Predict refraction by solving Snell's law at the horizontal y=0 interface from
the camera to the target centre, then project the interface intersection into
the existing pinhole camera. Evaluate the direct no-water target separately.
Predeclared tolerance: larger of 2 pixels and 1% of predicted displacement.
Require a nonzero oblique displacement exceeding 2 pixels, an observable target
in water, and a matched-index control within 2 pixels of dry.

Locate the central white target in a fixed central ROI, columns 128..384 and
rows 80..320. Select neutral pixels with minimum RGB channel >128 and maximum
minus minimum channel <40, then use the largest four-connected component of at
least 50 pixels. Report centroid, area and comparison to prediction; if this
procedure fails, retain the failure instead of tuning it to the candidate.
Inspect the fixed red/green marker reflection and retain water/dry comparisons.
Saved RGB measurements are geometric/display-domain evidence, not radiometry.

Each request retains the 768 MiB preflight guard, a 90 second coroutine timeout,
the existing capture helper's settling protocol, saved-image dimension checks,
and a bounded wait for PNG disk completion. Stop on resource failure without
raising ray budgets, reducing resolution or omitting the medium. Preserve failed
requests. At the end, verify all saved M1 evidence hashes and restore the original
marine scene/configuration. No M2 pass is inferred from a blue transparent sheet.
