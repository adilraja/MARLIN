# Survey specification v1

The specification is a draft implementing Ger's research-specification milestone. It is not a renderer or an approved experimental protocol. Existing Kit APIs are unaffected.

Load and validate with the standard-library-only survey_spec.load_spec(). CameraConfig is the typed camera schema. Unknown camera fields raise TypeError; invalid values raise ValueError. Physical helpers use metres and ideal nadir geometry only. Never use them to claim HiDef local GSD validation: that requires calibrated oblique ray projection, sensor pitch, crop and explicit rotation conventions.

All camera reference numbers come from Ger's root-level instruction file; they have not been independently verified. Null values are unresolved, never zero or assumed calibration. CameraConfig.readiness_gaps() lists missing camera fields. Sony swath is an approximate reference, not a sensor specification. Scene units are still unresolved.

The full taxonomy lives in assets/survey_species/*/manifest.json, with stable category IDs. Six manifests point to existing converted models and licences without moving or duplicating assets. Five species are missing. The six avian group labels come from Ger; non-avian group labels remain null pending definition. A filename alone does not verify the exact species. No imported pose is asserted to support both flight and sitting.

Randomisation uses paired strata across all five GSD levels. condition_seed() deliberately excludes GSD. The future generator must balance equal counts per stratum and reuse conditions across levels. Assign connected groups sharing ANY protected split identifier before expanding GSD variants. validate_split_records() detects cross-split reuse. An instance ID denotes the persistent instance, not a fresh ID per render; additional models will be needed to test asset-level generalisation.

Detection recall 0.90 is a candidate. Classification metrics, thresholds, detection IoU, sample counts, strata, flight-altitude range, split proportions and sweep mechanism await decisions. Generation should remain blocked until these and asset/camera calibration are resolved. The fixed water preset is a specification identifier awaiting implementation.

Annotation fields and COCO/optional YOLO conventions are output contracts for the next milestone; no dataset exporter is added here. Pixels-on-target distinguishes visible mask area from bounding-box dimensions. For planning, report the coarsest acceptable GSD (largest cm/px), avoiding the ambiguity of “minimum acceptable GSD”.

Run tests from the repository root:

    python3 -B -m unittest discover -s source/extensions/cris.madil.render_service/cris/madil/render_service/tests -p test_survey_spec.py

