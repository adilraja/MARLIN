# Bartlett flat-plane reproduction — 2026-09-09

Outcome: close, but not exact, reproduction without parameter fitting. This is an offline MARLIN camera-geometry calculation, **not** a new renderer, live Kit scene or calibrated historical-camera measurement. The active survey specification and animal calibration are unchanged. No message was sent to Ger. Stop at this milestone.

## Exact inputs and provenance

`bartlett_geometry_v1.json` contains only geometry and explicit reconstruction assumptions: camera-to-plane separation 549 m, focal length 150 mm, effective sensor 36 × 12 mm, output 6576 × 2192, pitch 30° from nadir, and inferred rolls 7.7675° / 23.1748°. The numeric comparison ranges live separately in `bartlett_validation_targets_v1.json` and are read **after** geometry computation. MARLIN does not solve for or tune any parameter using those ranges or the 20 m gap.

Rolls originate from the paper's footprint reconstruction, not physical mounting measurements. Camera model identity is inferred from metadata. Acquisition is unresolved, with half-height ROI more plausible than vertical binning; centred projection here does not confirm a centred deployed ROI. Historical barometric altitude is not known frame-by-frame camera-to-sea separation. Full provenance and the eight unsent questions are in `CAMERA_EVIDENCE.md`.

## Coordinates, rays and assumptions

All calculations use metres, world Y up, and a flat target plane Y=0. Camera centre is C=(0,549,0). Local nadir basis is right=(1,0,0), up=(0,0,-1), forward=(0,-1,0). Apply positive roll about world +Z first, then positive pitch about world +X: `Rx(pitch) Rz(roll) R_nadir`, using column-vector rotations. This makes roll a cross-track tilt, **not optical-axis image rotation** as in the earlier generic fixture. Combined roll and pitch means total off-nadir angle exceeds the unrolled pitch component.

This rotation composition is an explicit reconstruction assumption, not a newly confirmed physical installation convention. Four footprint cameras share an assumed optical centre and use mirrored rolls [-23.1748,-7.7675,7.7675,23.1748]. Mechanical baselines are unknown. World heading is arbitrary on the infinite flat plane; no exact historical yaw convention is claimed and no glare reversal is simulated.

Intrinsics: fx=150×6576/36=27400 px, fy=150×2192/12=27400 px, principal point=(3288,1096) in image-edge coordinates. Pixel centre (column i,row j) is (i+0.5,j+0.5). With camera right R, up U and forward F:

`d = F + ((u-cx)/fx) R - ((v-cy)/fy) U`

`P = C + t d`, with `t = -549/d_y`.

Only forward intersections with the flat plane are accepted. No distortion, waves, Earth curvature, refraction or aircraft-attitude dynamics. Output offsets are zero by declared assumption, not fitted calibration.

## Full-resolution maps

For every valid forward-neighbour pair, width GSD is `100*|P(u+1,v)-P(u,v)|`; height GSD is `100*|P(u,v+1)-P(u,v)|`, both in cm/px. Last-column width and last-row height have no in-image forward neighbour and are stored as NaN, never extrapolated into the reported extrema. Anisotropy is height/width. Effective pixel area is the area of its projected four-corner polygon, not the product of neighbour distances.

Each roll has four full-resolution 2192 × 6576 float32 NPY arrays. Calculations and extrema use float64 in 64-row chunks. Eight maps total occupy approximately 440 MiB per run. Diagnostic PNGs sample every eighth pixel; statistics use the entire valid grid. This computes per-pixel geometry without allocating a full 3D scene or altering Kit.

## Nominal and oblique results

Nominal pinhole/nadir GSD is **2.0036496 cm/px** in both directions; nominal nadir footprint is 131.76 × 43.92 m. The separate manufacturer-native-pitch calculation of 2.013 is not used here.

| Inferred roll | Direction | Simulated min–max cm/px | Published min–max | Absolute errors min / max cm/px | Relative errors min / max |
| --- | --- | --- | --- | --- | --- |
| 7.7675° | Width | 2.230198–2.496944 | 2.22–2.49 | 0.010198 / 0.006944 | 0.4594% / 0.2789% |
| 7.7675° | Height | 2.535429–2.899999 | 2.53–2.89 | 0.005429 / 0.009999 | 0.2146% / 0.3460% |
| 23.1748° | Width | 2.413005–3.142100 | 2.40–3.14 | 0.013005 / 0.002100 | 0.5419% / 0.0669% |
| 23.1748° | Height | 2.664823–3.364277 | 2.66–3.36 | 0.004823 / 0.004277 | 0.1813% / 0.1273% |

The comparison endpoints are the paper-review targets, also checked against section 5.3 of [Bartlett et al.](https://doi.org/10.1016/j.ecoinf.2025.103242). Absolute error is |simulated−published|; relative error divides by the published endpoint (fractions in JSON, percentages above). These are discrepancies, not values used to fit the simulation. Exact agreement has **not** been achieved. Possible contributors include pixel sampling/range aggregation, published rounding and unresolved pose/intrinsic conventions; their contributions have not been isolated.

Area ranges: 5.654354–7.174485 cm² at 7.7675°, and 6.377645–10.099893 cm² at 23.1748°. Anisotropy ranges: 1.109498–1.190032 and 1.026223–1.152178 respectively. No valid directional neighbour spacing in this reconstruction reaches 2 cm/px. This does not establish historical frame geometry.

## Simulated swaths and footprint gaps

| Inferred roll | Bottom / top image-edge ground lengths | World-X extent | World-Z extent |
| --- | --- | --- | --- |
| 7.7675° | 151.4229 / 158.7895 m | 159.2558 m | 60.1196 m |
| 23.1748° | 175.4141 / 185.9481 m | 194.7981 m | 67.1966 m |

These oblique image-edge lengths and axis-aligned extents are different swath descriptions; neither is silently substituted for the other. Signed rolls mirror the footprints.

Gap definition: world-X clearance between facing side edges at common world Z, over the overlap of those side edges. This avoids treating isolated slanted outer tips as adjacent-strip separation.

- Centre pair (−7.7675°, +7.7675°): **20.0057–20.9448 m**.
- Either outer adjacent pair: **20.0363–21.0089 m**.

Thus the roughly 20 m bottom constraint is closely reproduced without refitting. Under this explicit common-Z definition the centre pair's top gap remains below 21 m, whereas outer pairs exceed 21 m. Do not claim exact reproduction of the paper's top-gap description for all pairs. Corner-to-corner distances or a different footprint sampling definition are distinct quantities.

## Artifacts, run and tests

Final reviewed run: `artifacts/camera_validation/bartlett_uruix33o/`. It contains `report.json`, input/target snapshots, eight NPY maps, two four-panel heatmaps and `footprints.png`. JSON includes endpoint absolute/relative errors, footprint coordinates, gap sections and unresolved assumptions. The earlier `bartlett_v4d82u70` report is superseded because it used whole-polygon sections for gaps; its directional GSD outputs were unaffected.

From the repository root:

```bash
/home/madil/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B tools/validate_bartlett_camera.py
```

Requires NumPy and Pillow; Kit need not be running. Six NumPy regression tests cover nominal GSD, nadir spacing/area, boundary NaNs, rotation/intersection, chunk invariance, anisotropy and gap definition. Evidence tests preserve inferred/unresolved categories. No biological detectability experiments were performed.
