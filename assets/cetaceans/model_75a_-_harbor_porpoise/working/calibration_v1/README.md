# Harbour porpoise calibration candidate

Prepared 2026-09-09. This is a reversible, static candidate, not an approved scientific surfacing asset. The primary USD, original glTF, licence and live MARLIN scene are unchanged.

## Source evidence

DigitalLife3D's [Model 75A source record](https://sketchfab.com/3d-models/model-75a-harbor-porpoise-eb02e57f17d741329a66844a3a8d2094), accessed through its [public metadata API](https://api.sketchfab.com/v3/models/eb02e57f17d741329a66844a3a8d2094) on 2026-09-09, identifies Freja, a female harbour porpoise with total length 155.5 cm. The publisher describes reconstruction from photogrammetry, photography and video at Fjord & Baelt, Denmark. This is publisher evidence, not our independent measurement of the living animal.

Licence: CC-BY-NC-4.0; attribution required and commercial use restricted. Preserve and consult `../../source/license.txt` for the original attribution and licence links.

## Inspection and measurement

- Body Object_7 and eyes Object_8 retained: 23,456 imported mesh vertices in total.
- Icosphere is a custom display shape referenced by all 20 armature bones, not animal anatomy. It is excluded from static export and measurement, not deleted from the original.
- Original rig remains in `harbour_porpoise_inspected.blend` and the original scene in `harbour_porpoise_calibration_candidate.blend`. The separate static candidate scene/USD has no animation or armature.
- Measure raw bind mesh vertices after parent world transforms, not animated frame 1.
- Candidate body vertex landmarks: rostrum 3703 and centreline fluke notch 7266. Straight-line separation is 1.498300626 native units. Their anatomical identification and correspondence to the publisher's total-length protocol still require review.
- Candidate factor: 1.037842455 metres/native unit, giving 1.555 m landmark distance. This is an input-anchored scale, not an independent validation of specimen length.
- Fin-inclusive XYZ bounds are 0.419237 × 1.601489 × 0.432788 m; the longest bounding-box dimension is not the rostrum-to-notch length.
- USD uses Z up, metresPerUnit=1, forward -Y. For a Y-up reference, XYZ rotation (-90, 0, 0) gives forward +Z. No live scene scale has been changed.

## Surfacing candidate and checks

Native Z=0.10 was chosen as an engineering reference waterline and translated to candidate Z=0. It is not a measured biological waterline. Blowhole clearance and surfacing posture are unverified. The side image's line is only a diagnostic reference, not simulated water or occlusion.

The export was reopened with USD: two meshes, no Icosphere, metre units, and world bounds agreeing with prepared geometry within 1e-5 m. Original glTF, binary, licence and primary USD SHA-256 values match `inspection.json`. Details and explicit readiness flags are in `calibration.json`.

Next review: confirm rostrum/notch landmark correspondence, then choose and inspect a biologically defensible surfacing pose/waterline. Do not use this candidate for detectability claims yet.
