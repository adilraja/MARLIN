"""Read-only USD identities for paired GSD capture of one frozen GAMA state.

USD and Kit imports are deliberately deferred. The caller must freeze its
transaction before using this module. Camera definitions and /Render are
excluded from biological/environment identity; image-condition identity is
recorded separately. Matching hashes do not promise pixel-identical rendering.
"""
import hashlib
import json
import math
import re

from .exchange_v2 import validate_step
from .stage_coordinates import inspect_stage

ACTOR_PATH = "/MarlinGamaPorpoise/Porpoise_001"
IDENTITY_VERSION = "gama_marlin_resolved_scene_v1"
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _json_data(value, label):
    """Make a detached finite JSON value, without silently converting dict keys."""
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(label + " must contain finite JSON values")
        return value
    if isinstance(value, (list, tuple)):
        return [_json_data(item, label) for item in value]
    if isinstance(value, dict):
        if any(type(key) is not str for key in value):
            raise ValueError(label + " must use string dictionary keys")
        return {key: _json_data(item, label) for key, item in value.items()}
    raise ValueError(label + " must contain only JSON values")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False, ensure_ascii=True).encode("utf-8")


def _hash(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _dependencies(value):
    if not isinstance(value, list):
        raise ValueError("dependencies must be a list of recorded asset dependencies")
    result = _json_data(value, "dependencies")
    seen = set()
    for item in result:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not item["path"]:
            raise ValueError("Each dependency requires a nonempty path")
        if item["path"] in seen:
            raise ValueError("Dependency paths must be unique")
        seen.add(item["path"])
        digest = item.get("sha256")
        if digest is None:
            if item.get("status") != "runtime_or_unresolved":
                raise ValueError("Unhashed dependencies require explicit runtime_or_unresolved status")
        elif not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise ValueError("Dependency sha256 must be a lowercase 64-digit digest")
    return sorted(result, key=lambda item: item["path"])


def _matrix_record(matrix):
    values = [[float(matrix[row][column]) for column in range(4)] for row in range(4)]
    return _json_data(values, "Composed transform")


def _physical_flatten(stage):
    """Detach complete composed USD and exclude Camera subtrees plus /Render."""
    if stage is None:
        raise ValueError("An active USD stage is required")
    from pxr import Usd, UsdGeom
    camera_paths = [prim.GetPath() for prim in stage.TraverseAll() if prim.IsA(UsdGeom.Camera)]
    for prim in stage.TraverseAll():
        path = prim.GetPath()
        if path.HasPrefix("/Render") or any(path.HasPrefix(camera) for camera in camera_paths):
            continue
        if prim.HasPayload() and not prim.IsLoaded():
            raise ValueError("All non-camera payloads must be loaded before resolving scene identity")
    flattened = stage.Flatten(False)
    if flattened is None:
        raise ValueError("Could not flatten the USD stage")
    detached = Usd.Stage.Open(flattened)
    if detached is None:
        raise ValueError("Could not inspect the detached flattened USD stage")
    excluded = []
    for path in sorted(camera_paths, key=lambda value: len(str(value)), reverse=True):
        if detached.GetPrimAtPath(path):
            if not detached.RemovePrim(path):
                raise ValueError("Could not exclude a camera from scene identity")
            excluded.append(str(path))
    if detached.GetPrimAtPath("/Render"):
        if not detached.RemovePrim("/Render"):
            raise ValueError("Could not exclude transient /Render content")
    return flattened, sorted(excluded)


def source_content_hash(stage):
    """Hash physical source USD for restoration checks, retaining animation.

    Return one SHA-256 hex string. Unlike resolved_record(), this permits and
    preserves time-sampled values so an original animated scene can be checked
    before/after a capture transaction without evaluating or changing its pose.
    Camera subtrees and /Render remain excluded by the same identity boundary.
    """
    flattened, _ = _physical_flatten(stage)
    return hashlib.sha256(flattened.ExportToString().encode("utf-8")).hexdigest()


def resolved_record(stage, source_state, renderer_settings, dependencies, environment_clock):
    """Hash one resolved biological/environment snapshot without changing source.

    ``source_state`` is the complete actual GAMA v2 snapshot. ``dependencies``
    follows hidef_marine.asset_dependencies(): hashed local paths or explicitly
    unresolved/runtime entries. No dependency file is opened here. Renderer
    settings and clock/state records must be finite JSON dictionaries.

    The detached flattened layer contains every remaining prim, property and
    metadata opinion after all Camera subtrees and /Render are removed. Any
    remaining time samples or unloaded payload cause rejection; the caller must
    resolve them first. The flattened serialization is hashed in full, rather
    than selecting just animal-root variables.
    """
    snapshot = validate_step(source_state)
    settings = _json_data(renderer_settings, "renderer_settings")
    clocks = _json_data(environment_clock, "environment_clock")
    if not isinstance(settings, dict) or not isinstance(clocks, dict):
        raise ValueError("renderer_settings and environment_clock must be dictionaries")
    recorded_dependencies = _dependencies(dependencies)
    coordinates = inspect_stage(stage)
    if not coordinates["suitable_for_v2"]:
        raise ValueError("; ".join(coordinates["rejection_reasons"]))
    from pxr import Usd, UsdGeom
    actor = stage.GetPrimAtPath(ACTOR_PATH)
    if not actor or not actor.IsActive() or not actor.IsDefined():
        raise ValueError("A defined active bridge-owned porpoise is required")
    if not actor.IsA(UsdGeom.Xform):
        raise ValueError("The bridge-owned porpoise root must be an Xform")
    flattened, excluded = _physical_flatten(stage)
    samples = list(flattened.ListAllTimeSamples())
    if samples:
        raise ValueError("Frozen biological/environment USD must contain zero remaining time samples")
    usd_text = flattened.ExportToString()
    matrix = UsdGeom.Xformable(actor).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    identity = {"version": IDENTITY_VERSION,
                "frozen_usd_sha256": hashlib.sha256(usd_text.encode("utf-8")).hexdigest(),
                "gama_source_state": snapshot,
                "pose_mapping": "static_pose_proxy_v1",
                "pose_scope": "One upright static mesh for every state; no rig animation, breathing or dive-pitch claim",
                "animation_phase": {"kind": "static_mesh", "phase": None, "applicability": "not_applicable"},
                "stage_coordinates": {key: coordinates[key] for key in ("meters_per_scene_unit", "up_axis", "mean_sea_level_world_y_m", "vertical_datum_source")},
                "actor_path": ACTOR_PATH, "composed_actor_matrix": _matrix_record(matrix),
                "renderer_settings": settings, "dependencies": recorded_dependencies,
                "environment_clock": clocks}
    unresolved = [item["path"] for item in recorded_dependencies if item.get("sha256") is None]
    return {"schema_version": IDENTITY_VERSION, "resolved_scene_state_hash": _hash(identity),
            "identity": identity, "frozen_usd_bytes": len(usd_text.encode("utf-8")),
            "remaining_time_samples": 0, "excluded_camera_paths": sorted(excluded),
            "excluded_render_subtree": "/Render", "unresolved_dependencies": unresolved,
            "content_identity_limitation": "External/runtime dependency bytes were not inspected; their recorded paths/status and resolved USD values remain in the identity",
            "pixel_identical_rgb_verified": False}


def camera_condition(stage, camera_path, gsd_cm_px, anchor_m, reference_plane_y_m=0.0, resolution=None):
    """Record the actual composed camera independently of frozen scene identity.

    GSD is explicitly nominal, at the declared horizontal reference plane.
    Capture callers should supply their actual [width,height] resolution and
    independently verify render-product delivery using record_projection().
    This function does not position cameras or assert refracted underwater GSD.
    """
    if not isinstance(camera_path, str) or not camera_path.startswith("/"):
        raise ValueError("camera_path must be an absolute USD prim path")
    if type(gsd_cm_px) not in (int, float) or not math.isfinite(gsd_cm_px) or gsd_cm_px <= 0:
        raise ValueError("Nominal GSD must be finite and positive")
    if not isinstance(anchor_m, (list, tuple)) or len(anchor_m) != 3:
        raise ValueError("anchor_m must be [x,y,z] in metres")
    anchor = _json_data(anchor_m, "anchor_m")
    if any(type(value) not in (int, float) for value in anchor):
        raise ValueError("anchor_m must contain numeric coordinates")
    if type(reference_plane_y_m) not in (int, float) or not math.isfinite(reference_plane_y_m):
        raise ValueError("reference_plane_y_m must be finite")
    if resolution is not None:
        if not isinstance(resolution, (list, tuple)) or len(resolution) != 2 or any(type(value) is not int or value <= 0 for value in resolution):
            raise ValueError("resolution must be two positive integer pixel dimensions")
        resolution = list(resolution)
    coordinates = inspect_stage(stage)
    if not coordinates["suitable_for_v2"]:
        raise ValueError("; ".join(coordinates["rejection_reasons"]))
    from pxr import Usd, UsdGeom
    prim = stage.GetPrimAtPath(camera_path)
    if not prim or not prim.IsA(UsdGeom.Camera):
        raise ValueError("camera_path must identify an existing USD Camera")
    if any(attribute.GetNumTimeSamples() for attribute in prim.GetAttributes()):
        raise ValueError("The capture camera must be resolved to static attributes")
    camera = UsdGeom.Camera(prim)
    exposure = {}
    for attribute in prim.GetAttributes():
        name = attribute.GetName()
        if "exposure" in name.lower() and attribute.HasAuthoredValueOpinion():
            value = attribute.Get(Usd.TimeCode.Default())
            if type(value) not in (int, float):
                raise ValueError("Authored camera exposure attributes must be finite numeric scalars")
            exposure[name] = value
    record = {"version": "gama_marlin_camera_condition_v1", "camera_path": camera_path,
              "nominal_gsd_cm_px": gsd_cm_px, "reference_plane_y_m": reference_plane_y_m,
              "anchor_m": anchor, "resolution_px": resolution,
              "meters_per_scene_unit": coordinates["meters_per_scene_unit"],
              "composed_camera_matrix": _matrix_record(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())),
              "projection": str(camera.GetProjectionAttr().Get()),
              "focal_length": camera.GetFocalLengthAttr().Get(),
              "horizontal_aperture": camera.GetHorizontalApertureAttr().Get(),
              "vertical_aperture": camera.GetVerticalApertureAttr().Get(),
              "horizontal_aperture_offset": camera.GetHorizontalApertureOffsetAttr().Get(),
              "vertical_aperture_offset": camera.GetVerticalApertureOffsetAttr().Get(),
              "clipping_range_scene_units": list(camera.GetClippingRangeAttr().Get()),
              "focus_distance_scene_units": camera.GetFocusDistanceAttr().Get(),
              "f_stop": camera.GetFStopAttr().Get(),
              "authored_exposure_attributes": exposure,
              "gsd_scope": "Nominal reference-plane sampling; no underwater refraction or anatomical-surface GSD claim"}
    record = _json_data(record, "camera_condition")
    return {"camera_condition_hash": _hash(record), "camera_condition": record,
            "actual_render_product_camera_verified": False}
