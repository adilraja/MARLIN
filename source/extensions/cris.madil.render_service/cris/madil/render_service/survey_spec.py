"""Versioned survey specification, independent of Kit and third-party packages.

Physical calculations use metres; they do not infer MARLIN's scene-unit scale.
"""

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path


SPEC_PATH = Path(__file__).resolve().parents[3] / "config" / "survey_v1.json"
PROJECT_ROOT = Path(__file__).resolve().parents[6]


def positive(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite positive number")
    return value


@dataclass(frozen=True)
class CameraConfig:
    model: str
    focal_length_mm: float
    altitude_m: float
    nominal_gsd_cm_px: float
    image_size_px: object
    pixel_pitch_um: object
    pitch_deg: object
    roll_cases_deg: tuple
    pose_convention: object
    expected_local_gsd_cm_px: object
    approximate_swath_m: object

    def __post_init__(self):
        for name in ("focal_length_mm", "altitude_m", "nominal_gsd_cm_px"):
            positive(getattr(self, name), name)
        if self.pixel_pitch_um is not None:
            positive(self.pixel_pitch_um, "pixel_pitch_um")
        if self.image_size_px is not None:
            if len(self.image_size_px) != 2 or any(type(n) is not int or n <= 0 for n in self.image_size_px):
                raise ValueError("image_size_px must contain two positive integers")
        for angle in (self.pitch_deg, *self.roll_cases_deg):
            if angle is not None and (type(angle) not in (int, float) or not math.isfinite(angle) or abs(angle) >= 90):
                raise ValueError("camera angles must be finite and between -90 and 90 degrees")
        if self.approximate_swath_m is not None:
            positive(self.approximate_swath_m, "approximate_swath_m")
        if self.expected_local_gsd_cm_px is not None:
            low, high = self.expected_local_gsd_cm_px
            positive(low, "local GSD minimum")
            positive(high, "local GSD maximum")
            if low > high:
                raise ValueError("local GSD interval is reversed")

    def readiness_gaps(self):
        return [name for name in ("image_size_px", "pixel_pitch_um", "pitch_deg", "pose_convention") if getattr(self, name) is None] + ([] if self.roll_cases_deg else ["roll_cases_deg"])


def nadir_gsd_cm_px(altitude_m, focal_length_mm, pixel_pitch_um, target_altitude_m=0):
    """Flat target plane, ideal pinhole, nadir only; not the HiDef replica."""
    positive(altitude_m, "altitude_m")
    positive(focal_length_mm, "focal_length_mm")
    positive(pixel_pitch_um, "pixel_pitch_um")
    if type(target_altitude_m) not in (float, int) or not math.isfinite(target_altitude_m) or not 0 <= target_altitude_m < altitude_m:
        raise ValueError("target altitude must be finite, nonnegative and below the camera")
    return (altitude_m - target_altitude_m) * pixel_pitch_um / focal_length_mm * 0.1


def nadir_altitude_m(gsd_cm_px, focal_length_mm, pixel_pitch_um, target_altitude_m=0):
    positive(gsd_cm_px, "gsd_cm_px")
    positive(focal_length_mm, "focal_length_mm")
    positive(pixel_pitch_um, "pixel_pitch_um")
    if type(target_altitude_m) not in (float, int) or not math.isfinite(target_altitude_m) or target_altitude_m < 0:
        raise ValueError("target altitude must be finite and nonnegative")
    return target_altitude_m + gsd_cm_px * focal_length_mm / (0.1 * pixel_pitch_um)


def projected_length_pixels(projected_length_m, local_gsd_cm_px):
    """Length on a sampled plane, not a 3D body length or visible mask area."""
    return 100 * positive(projected_length_m, "projected_length_m") / positive(local_gsd_cm_px, "local_gsd_cm_px")


def condition_seed(master_seed, scene_id):
    """GSD deliberately excluded: paired conditions share nuisance draws."""
    if type(master_seed) is not int or master_seed < 0 or not isinstance(scene_id, str) or not scene_id:
        raise ValueError("seed must be a nonnegative integer and scene_id nonempty")
    payload = json.dumps([master_seed, scene_id], separators=(",", ":")).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def validate_split_records(records):
    """Reject identifiers crossing splits, including paired GSD variants."""
    seen = {}
    for record in records:
        split = record["split"]
        if split not in ("train", "validation", "test"):
            raise ValueError("unknown split")
        for field in ("scene_id", "asset_instance_id", "sequence_id", "condition_id"):
            value = record[field]
            if not isinstance(value, str) or not value:
                raise ValueError(f"{field} must be a nonempty string")
            key = (field, value)
            if key in seen and seen[key] != split:
                raise ValueError(f"split leakage: {field}={value}")
            seen[key] = split


def load_spec(path=SPEC_PATH):
    data = json.loads(Path(path).read_text())
    if data["schema_version"] != "1.0.0":
        raise ValueError("unsupported survey schema version")
    if data["gsd_levels_cm_px"] != [0.5, 1.0, 2.0, 3.0, 4.0]:
        raise ValueError("v1 requires the five PI-specified GSD levels")
    if data["environment"] != {"sea": "calm", "lighting": "overcast_diffuse", "sun_glint": False, "water_preset": "survey_fixed_v1", "precipitation": False, "randomisation": False}:
        raise ValueError("v1 requires the fixed survey environment")
    for camera in data["cameras"].values():
        CameraConfig(**camera)
    if set(data["cameras"]) != {"hidef", "sony"}:
        raise ValueError("both camera configurations are required")
    hidef = data["cameras"]["hidef"]
    if hidef["pitch_deg"] != 30 or hidef["roll_cases_deg"] != [7.77, 23.17]:
        raise ValueError("HiDef validation geometry must retain its oblique cases")
    if set(data["tasks"]) != {"detection", "group_classification", "species_classification"}:
        raise ValueError("all three tasks are required")
    for task in data["tasks"].values():
        threshold = task["threshold"]
        if threshold is not None and (type(threshold) not in (int, float) or not math.isfinite(threshold) or not 0 < threshold <= 1):
            raise ValueError("threshold must be null or in (0, 1]")
    condition_seed(data["randomisation"]["master_seed"], "validation")
    if data["randomisation"]["strategy"] != "paired_stratified_across_gsd":
        raise ValueError("GSD conditions must share balanced nuisance strata")
    if set(data["randomisation"]["variables"]) != {"pose", "heading", "image_position", "surfacing_state", "bird_state", "bird_altitude_m", "individual_placement"}:
        raise ValueError("all specified nuisance variables are required")
    count = data["randomisation"]["samples_per_stratum"]
    if count is not None and (type(count) is not int or count <= 0):
        raise ValueError("samples_per_stratum must be null or a positive integer")
    annotations = data["annotations"]
    if annotations["source"] != "simulator_ground_truth" or set(annotations["required_formats"]) != {"coco_json", "frame_metadata_json"}:
        raise ValueError("simulator ground truth and required export formats must be preserved")
    required = {"frame_id", "species_id", "group_id", "task_labels", "world_position", "image_position", "orientation", "heading_deg", "state", "bird_altitude_m", "camera_id", "camera_pose", "nominal_gsd_cm_px", "local_gsd_x_cm_px", "local_gsd_y_cm_px", "visible_mask_area_px", "bbox_xywh_px", "scene_id", "asset_instance_id", "sequence_id", "condition_id", "split", "seed", "spec_version"}
    if not required.issubset(annotations["required_fields"]):
        raise ValueError("required reconstruction/annotation fields are missing")
    units = data["coordinate_system"]
    if units["up_axis"] != "Y" or units["heading_zero"] != "+Z" or units["heading_90"] != "+X":
        raise ValueError("MARLIN coordinate conventions must be retained")
    if units["meters_per_scene_unit"] is not None:
        positive(units["meters_per_scene_unit"], "meters_per_scene_unit")
    if data["splits"]["group_by"] != ["scene_id", "asset_instance_id", "sequence_id", "condition_id"]:
        raise ValueError("split grouping must protect scenes, instances, sequences and conditions")
    ratios = data["splits"]["ratios"]
    if ratios is not None:
        if set(ratios) != {"train", "validation", "test"} or any(positive(v, "split fraction") > 1 for v in ratios.values()) or not math.isclose(sum(ratios.values()), 1):
            raise ValueError("split fractions must sum to one")
    return data


def asset_inventory(root=PROJECT_ROOT):
    result = []
    for path in sorted((root / "assets" / "survey_species").glob("*/manifest.json")):
        manifest = json.loads(path.read_text())
        available = bool(manifest["usd_path"] and (root / manifest["usd_path"]).is_file())
        result.append({**manifest, "available": available, "render_ready": available and manifest["calibration"]["status"] == "verified"})
    return result
