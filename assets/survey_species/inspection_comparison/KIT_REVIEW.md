# Kit comparison — 2026-09-09

Eight review instances were added alongside the existing scene: ReviewOriginal_ and ReviewCleaned_ for guillemot, northern_gannet, european_storm_petrel and common_tern. Primary animal references were not replaced. Each pair shares the same display scale; each full bound's lowest point is placed at nominal Y=0. This is a support comparison, not a verified floating pose. Existing animated waves can change apparent water contact.

Settled viewport capture: kit_comparison.png. In this camera view the cleaned birds appear on the left and originals on the right, with guillemots closest and terns furthest away.

- Guillemot: both original USD and cleaned v3 had no exported shader. The source glTF imports as an unlit emission/mix network. Working v4 converts that material to Principled BSDF using the original image, with roughness 0.65. Geometry is unchanged from v3. Kit now shows the dark/white plumage on the cleaned bird; the original remains visibly untextured. This material is an appearance approximation, not calibrated optical data.
- Gannet: plumage is visible and the major pedestal is absent on the cleaned copy. It retains the standing specimen pose.
- Petrel: spread wings and plumage are visible; the labelled box remains on the original and is absent from the working copy. Foot ends still need review.
- Tern: both copies retain the folded-wing specimen shape; no support was removed.

The remaining grid overlay, waves, specimen poses, contact defects and uncalibrated display sizes prevent this comparison from serving as scientific GSD validation. No flying or sitting state was marked verified.

Repeat using source/extensions/cris.madil.render_service/config/compare_cleaned_birds.py while Kit is running. Rerunning replaces only the eight named review copies and sets BirdComparisonCamera active. The first capture may reflect an earlier frame; inspect the settled capture before drawing conclusions.
