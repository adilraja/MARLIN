"""Deterministic, Kit-free scene proposals for the provisional GSD pilot.

The bounded distributions below are engineering choices, not observations of
animal behaviour. Sampling never depends on GSD, rendering, visibility, or ML
results. Candidate IDs are explicit: callers retain rejected candidates and
request the next integer ID; this module never silently rejects or resamples.
"""

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_EXPERIMENT_ROOT = PROJECT_ROOT / "experiments/gsd_pilot_v1"
SEED_SOURCE = "source/extensions/cris.madil.render_service/cris/madil/render_service/survey_spec.py"
MASTER_SEED = 20260929
GSD_LEVELS = [0.5, 1.0, 2.0, 3.0, 4.0]
SEPARATIONS_M = [50.0, 100.0, 200.0, 300.0, 400.0]
SPECIES = ("european_storm_petrel", "harbour_porpoise")
STATES = {"european_storm_petrel": "static_spread_wing_proxy",
          "harbour_porpoise": "static_shallow_swim"}
# These pin the delivered, unchanged M2 calibration records. A recalibration
# requires an explicit new sampling version; it cannot silently replace them.
CALIBRATION_SHA256 = {
    "european_storm_petrel": "6c024be4246ebd155a91731d89091726568880df35491c4baf5cb7992f8138a7",
    "harbour_porpoise": "898aa89c6faa87d07f66e7f8de1cc0e9c90f90d9c2d5571ddef71f665c2f8171",
}
SAMPLING_RANGES = {
    "x_m": [-0.6, 0.6], "z_m": [-0.6, 0.6], "heading_deg": [0.0, 360.0],
    "petrel_root_altitude_m": [0.75, 1.25],
    "porpoise_top_clearance_m": [0.02, 0.08],
}
RANGE_PROVENANCE = "provisional_engineering_sampling_not_biological_distributions"


def _strict_json(value):
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is list:
        for item in value:
            _strict_json(item)
        return
    if type(value) is dict and all(type(key) is str for key in value):
        for item in value.values():
            _strict_json(item)
        return
    raise ValueError("Only finite JSON data with string object keys is permitted")


def canonical_json(value):
    """Return UTF-8-independent canonical JSON text; no NaN or coercions."""
    _strict_json(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _digest(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def manifest_hash(manifest):
    """Hash all content except the one top-level manifest_sha256 field."""
    if type(manifest) is not dict:
        raise ValueError("Manifest must be a JSON object")
    _strict_json(manifest)
    return _digest({key: value for key, value in manifest.items()
                    if key != "manifest_sha256"})


def _file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(path):
    value = json.loads(path.read_text(encoding="utf-8"),
                       object_pairs_hook=_unique_pairs)
    _strict_json(value)
    return value


def _identity(species, index):
    if type(species) is not str or species not in SPECIES:
        raise ValueError("Unknown or unsupported species")
    if type(index) is not int or not 0 <= index <= 999999999:
        raise ValueError("Candidate index must be an integer from 0 to 999999999")
    return f"{species}_{index:04d}"


def _load_seed_helper():
    # Loading by filename avoids the Kit-dependent package initializer.
    name = "_marlin_m3_survey_spec"
    module = sys.modules.get(name)
    if module is None:
        spec = importlib.util.spec_from_file_location(name, PROJECT_ROOT / SEED_SOURCE)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module  # dataclasses consult the module registry.
        spec.loader.exec_module(module)
    return module.condition_seed


def _contract(spec):
    """Validate and retain only protocol fields used for scene sampling."""
    if type(spec) is not dict or spec.get("schema_version") not in ("1.1.0", "1.2.0"):
        raise ValueError("Unsupported experiment specification schema")
    camera = spec["camera"]
    expected_camera = {
        "image_size_px": [1024, 768], "focal_length_mm": 50.0,
        "pixel_pitch_um": 5.0, "pitch_deg": 0.0, "roll_deg": 0.0,
        "gsd_reference_plane": "horizontal_plane_at_recorded_animal_root_y",
        "camera_to_reference_plane_separations_m": SEPARATIONS_M,
        "paired_variable": "camera_world_y_only",
    }
    # Canonical comparison rejects bools in numeric fields and wrong JSON types.
    actual_camera = {key: camera[key] for key in expected_camera}
    if canonical_json(actual_camera) != canonical_json(expected_camera):
        raise ValueError("Camera sampling contract differs from the frozen pilot")
    if canonical_json(spec["gsd_levels_cm_px"]) != canonical_json(GSD_LEVELS):
        raise ValueError("The five ordered GSD levels must remain frozen")
    if type(spec["scene_generation"]["master_seed"]) is not int or spec["scene_generation"]["master_seed"] != MASTER_SEED:
        raise ValueError("Master seed differs from the frozen pilot")
    if spec["scene_generation"]["gsd_in_biological_seed"] is not False:
        raise ValueError("GSD cannot enter scene sampling")
    if spec["coordinates"]["up_axis"] != "Y" or spec["coordinates"]["required_stage_meters_per_unit"] != 0.01:
        raise ValueError("The pilot requires a Y-up centimetre stage")
    targets = spec["targets"]
    if targets["selected_bird"] != SPECIES[0] or targets["selected_cetacean"] != SPECIES[1]:
        raise ValueError("Selected targets differ from the frozen pilot")
    if targets["permitted_states"] != {species: [STATES[species]] for species in SPECIES}:
        raise ValueError("Only the calibrated static states are permitted")
    if spec["schema_version"] == "1.2.0":
        expected_ranges = {"values": SAMPLING_RANGES, "status": RANGE_PROVENANCE,
                           "pitch_deg": 0, "roll_deg": 0, "pose_time_code": 1}
        if canonical_json(targets["state_conditioned_sampling_ranges"]) != canonical_json(expected_ranges):
            raise ValueError("State-conditioned sampling ranges differ from the frozen M3 contract")
    return {"camera": actual_camera, "gsd_levels_cm_px": GSD_LEVELS,
            "master_seed": MASTER_SEED, "stage_meters_per_unit": 0.01,
            "up_axis": "Y", "permitted_states": targets["permitted_states"]}


def _inputs(species, experiment_root):
    experiment_root = Path(experiment_root).resolve()
    spec = _read_json(experiment_root / "specification.json")
    contract = _contract(spec)
    record_path = f"wildlife/{species}.json"
    record_file = experiment_root / record_path
    record_sha = _file_sha256(record_file)
    if record_sha != CALIBRATION_SHA256[species]:
        raise ValueError(f"Frozen M2 calibration hash changed: {record_path}")
    record = _read_json(record_file)
    if record["species"] != species or record["verification"]["passed"] is not True:
        raise ValueError("Calibration identity or verification is invalid")
    asset = record["asset"]
    dependencies = asset["dependencies"]
    seen = set()
    for dependency in dependencies:
        relative = Path(dependency["path"])
        path = (PROJECT_ROOT / relative).resolve()
        if relative.is_absolute() or ".." in relative.parts or not path.is_relative_to(PROJECT_ROOT / "assets"):
            raise ValueError("Asset dependency must remain within canonical assets")
        if dependency["path"] in seen:
            raise ValueError("Duplicate asset dependency")
        seen.add(dependency["path"])
        if _file_sha256(path) != dependency["sha256"]:
            raise ValueError(f"Asset dependency hash changed: {relative}")
    if {"path": asset["path"], "sha256": asset["sha256"]} not in dependencies:
        raise ValueError("Primary asset is missing from dependencies")
    return spec, contract, record, record_path, record_sha


def _draw(seed, label, interval):
    # Each named draw has its own SHA256 stream, so order and extra future draws
    # cannot consume another draw's random state. Top 53 bits are exact in a
    # Python binary64 float, with upper endpoint excluded even after rounding.
    digest = hashlib.sha256(canonical_json(["marlin_m3_draw_v1", seed, label]).encode()).digest()
    draw_seed = int.from_bytes(digest[:8], "big")
    unit = (draw_seed >> 11) / (1 << 53)
    low, high = interval
    value = min(low + (high - low) * unit, math.nextafter(high, low))
    return value, {"seed_uint64": draw_seed, "sha256": digest.hex(),
                   "unit_interval_value": unit, "range": list(interval)}


def _sample(species, index, experiment_root):
    scene_id = _identity(species, index)
    spec, contract, record, record_path, record_sha = _inputs(species, experiment_root)
    seed = _load_seed_helper()(MASTER_SEED, scene_id)
    labels = ["x_m", "z_m", "heading_deg", "petrel_root_altitude_m" if species == SPECIES[0] else "porpoise_top_clearance_m"]
    values, draws = {}, {}
    for label in labels:
        values[label], draws[label] = _draw(seed, label, SAMPLING_RANGES[label])
    bounds = record["geometry"]["corrected_metric_bounds_relative_to_root"]
    clearance = values.get("porpoise_top_clearance_m")
    root_y = values["petrel_root_altitude_m"] if species == SPECIES[0] else -bounds["maximum"][1] - clearance
    animal = {
        "asset_path": record["asset"]["path"], "scale": record["spawn"]["scale"],
        "model_rotation_deg": record["spawn"]["model_rotation"],
        "position_m": [values["x_m"], root_y, values["z_m"]],
        "heading_deg": values["heading_deg"], "pitch_deg": 0.0, "roll_deg": 0.0,
        "state": STATES[species], "pose_time_code": 1, "animation": "none",
        "clearance_m": clearance,
        "world_y_bounds_m": [root_y + bounds["minimum"][1], root_y + bounds["maximum"][1]],
        "physical_reference_status": "provisional",
    }
    variants = [{"requested_gsd_cm_px": gsd,
                 "position_m": [0.0, root_y + separation, 0.0],
                 "reference_plane_y_m": root_y, "separation_m": separation}
                for gsd, separation in zip(GSD_LEVELS, SEPARATIONS_M)]
    manifest = {
        "schema_version": "1.0.0", "experiment_id": "gsd_pilot_v1",
        "scene_id": scene_id, "species": species, "candidate_index": index,
        "asset_instance_id": scene_id + "_animal", "sequence_id": scene_id + "_sequence",
        "condition_id": scene_id + "_condition",
        "candidate_role": "initial" if index < 25 else "replacement_requires_retained_rejection_record",
        "specification": {"path": "specification.json", "schema_version": spec["schema_version"],
                          "sampling_contract_sha256": _digest(contract)},
        "calibration": {"path": record_path, "sha256": record_sha,
                        "asset_dependencies": record["asset"]["dependencies"]},
        "random": {"master_seed": MASTER_SEED, "condition_seed": seed,
                   "seed_helper": "survey_spec.condition_seed", "seed_helper_path": SEED_SOURCE,
                   "seed_helper_sha256": _file_sha256(PROJECT_ROOT / SEED_SOURCE),
                   "draw_algorithm": "sha256_named_uint64_top53_uniform_v1",
                   "subdraws": draws, "gsd_used": False,
                   "renderer_seed": None, "renderer_seed_reason": "record_separately_if_supported"},
        "sampling": {"version": "m3_engineering_v1", "distribution": "independent_uniform_lower_inclusive_upper_exclusive",
                     "ranges": {label: list(SAMPLING_RANGES[label]) for label in labels},
                     "provenance": RANGE_PROVENANCE,
                     "biological_distribution_validated": False,
                     "silent_rejection_or_resampling": False,
                     "replacement_policy": "retain_rejection_reason_then_request_next_numeric_candidate_id"},
        "coordinates": {"units": "metres", "stage_meters_per_unit": 0.01,
                        "up_axis": "Y", "heading_zero": "+Z", "heading_90": "+X"},
        "reference_plane": {"id": "animal_root_horizontal_plane", "y_m": root_y,
                            "sea_plane_y_m": 0.0},
        "animal": animal,
        "camera": {"shared": {"image_size_px": [1024, 768], "focal_length_mm": 50.0,
                              "pixel_pitch_um": 5.0, "x_m": 0.0, "z_m": 0.0,
                              "view_direction": "-Y", "image_up_world_axis": "-Z",
                              "pitch_deg": 0.0, "roll_deg": 0.0,
                              "orientation": "nadir", "distortion": "zero_assumption"},
                   "paired_variable": "camera_world_y_only", "variants": variants},
        "time": {"pose_time_code": 1, "timeline": "frozen",
                 "application_driven_geometry": "must_be_frozen_by_replay_before_capture"},
        "validation_scope": "deterministic_geometric_proposal_capture_visibility_pending_milestone_4",
    }
    manifest["manifest_sha256"] = manifest_hash(manifest)
    return manifest


def sample_scene(species, index, experiment_root=DEFAULT_EXPERIMENT_ROOT):
    """Return one frozen proposal. First 25 IDs per species are initial scenes.

    No files are written and no Kit modules or HTTP calls are used. Missing,
    altered, non-finite, or incompatible inputs fail closed with ValueError.
    """
    try:
        return _sample(species, index, experiment_root)
    except (OSError, KeyError, TypeError, IndexError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid sampling input: {error}") from error


def validate_manifest(manifest, experiment_root=DEFAULT_EXPERIMENT_ROOT):
    """Return True only for exact deterministic content and current input hashes.

    Recomputing also rejects added/removed fields, changed draws or GSDs, and
    fabricated positions even if a caller recomputes the self hash afterward.
    """
    try:
        _strict_json(manifest)
        if type(manifest) is not dict or manifest.get("manifest_sha256") != manifest_hash(manifest):
            raise ValueError("Manifest SHA256 mismatch")
        expected = sample_scene(manifest["species"], manifest["candidate_index"], experiment_root)
        if canonical_json(manifest) != canonical_json(expected):
            raise ValueError("Manifest differs from the deterministic frozen proposal")
        return True
    except (KeyError, TypeError, IndexError) as error:
        raise ValueError(f"Invalid manifest schema: {error}") from error
