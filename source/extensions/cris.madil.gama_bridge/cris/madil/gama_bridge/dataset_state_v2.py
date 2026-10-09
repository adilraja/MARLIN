"""Private frozen target-removal variants and honest direct amodal labels.

The M6 positive identity remains unchanged. A negative physically removes the
owned target subtree from a detached copy and binds its identity to that positive
snapshot. Common dependency records remain anchored to the positive, including
target textures. No Kit imports, rendering, file writes or live-stage mutation.
"""
import hashlib
import math
import struct

from .exchange_v2 import validate_step
from .stage_coordinates import inspect_stage
from . import paired_state_v2 as paired

TARGET_ROOT = "/MarlinGamaPorpoise"
TARGET_ACTOR = paired.ACTOR_PATH
NEGATIVE_VERSION = "gama_marlin_target_absent_v1"
BACKGROUND_VERSION = "gama_marlin_paired_background_v1"
ANNOTATION_VERSION = "gama_marlin_amodal_annotation_v1"
PROJECTION_MATRIX_TOLERANCE = 1e-7


def _context(stage, state, renderer, deps, clock):
    snapshot = validate_step(state)
    settings = paired._json_data(renderer, "renderer_settings")
    clocks = paired._json_data(clock, "environment_clock")
    if not isinstance(settings, dict) or not isinstance(clocks, dict):
        raise ValueError("Renderer settings and environment clock must be dictionaries")
    dependencies = paired._dependencies(deps)
    coordinates = inspect_stage(stage)
    if not coordinates["suitable_for_v2"]:
        raise ValueError("; ".join(coordinates["rejection_reasons"]))
    return snapshot, settings, dependencies, clocks, {key: coordinates[key] for key in (
        "meters_per_scene_unit", "up_axis", "mean_sea_level_world_y_m", "vertical_datum_source")}


def _physical(stage):
    layer, _ = paired._physical_flatten(stage)
    if layer.ListAllTimeSamples():
        raise ValueError("Dataset variants must contain zero remaining physical time samples")
    return layer


def _mesh_count(stage):
    from pxr import Usd, UsdGeom
    prim = stage.GetPrimAtPath(TARGET_ROOT)
    return sum(p.IsA(UsdGeom.Mesh) for p in Usd.PrimRange(prim)) if prim else 0


def _root_paths(stage):
    return sorted(str(prim.GetPath()) for prim in stage.GetPseudoRoot().GetChildren())


def background_record(stage, state, renderer, deps, clock):
    """Compare paired backgrounds using the common positive dependency records."""
    snapshot, settings, dependencies, clocks, coordinates = _context(stage, state, renderer, deps, clock)
    layer = _physical(stage)
    from pxr import Usd
    private = Usd.Stage.Open(layer)
    if private.GetPrimAtPath(TARGET_ROOT) and not private.RemovePrim(TARGET_ROOT):
        raise ValueError("Could not exclude the owned target from background identity")
    usd_digest = hashlib.sha256(layer.ExportToString().encode("utf-8")).hexdigest()
    record = {"version": BACKGROUND_VERSION, "background_usd_sha256": usd_digest,
              "gama_source_state": snapshot, "stage_coordinates": coordinates,
              "renderer_settings": settings, "dependencies": dependencies, "environment_clock": clocks,
              "excluded_target_subtree": TARGET_ROOT}
    return {"background_hash": paired._hash(record), "identity": record,
            "dependency_policy": "Common full positive dependency records, including removed target textures"}


def variant_record(stage, state, renderer, deps, clock, target_present, parent_hash=None):
    """Recompute positive M6 identity or the explicitly bound negative identity."""
    if type(target_present) is not bool:
        raise ValueError("target_present must be a boolean")
    if target_present:
        _physical(stage)
        return paired.resolved_record(stage, state, renderer, deps, clock)
    if not isinstance(parent_hash, str) or not paired.SHA256.fullmatch(parent_hash):
        raise ValueError("A negative requires its parent positive scene-state SHA-256")
    snapshot, settings, dependencies, clocks, coordinates = _context(stage, state, renderer, deps, clock)
    if stage.GetPrimAtPath(TARGET_ROOT) or stage.GetPrimAtPath(TARGET_ACTOR):
        raise ValueError("A negative must physically remove the entire owned target subtree")
    layer = _physical(stage)
    removal = {"operation": "RemovePrim", "prim_path": TARGET_ROOT, "scope": "private_frozen_variant"}
    record = {"version": NEGATIVE_VERSION, "parent_positive_scene_state_hash": parent_hash,
              "gama_source_state": snapshot, "removal_operation": removal,
              "frozen_usd_sha256": hashlib.sha256(layer.ExportToString().encode("utf-8")).hexdigest(),
              "stage_coordinates": coordinates, "renderer_settings": settings,
              "dependencies": dependencies, "environment_clock": clocks,
              "target_present": False, "target_mesh_count": 0,
              "biological_approval": False,
              "pose_mapping": "target_removed_counterpart_of_static_pose_proxy_v1"}
    background = background_record(stage, snapshot, settings, dependencies, clocks)
    return {"schema_version": NEGATIVE_VERSION, "resolved_scene_state_hash": paired._hash(record),
            "identity": record, "background_hash": background["background_hash"], "target_present": False,
            "remaining_time_samples": 0, "pixel_identical_rgb_verified": False,
            "negative_semantics": "Target physically removed; a submerged or invisible present target is not a negative"}


def prepare_variants(frozen, state, renderer, deps, clock):
    """Create only a private removed-target stage and prove background equality."""
    present = variant_record(frozen, state, renderer, deps, clock, True)
    before_paths, count = _root_paths(frozen), _mesh_count(frozen)
    if count < 1:
        raise ValueError("The positive target requires at least one mesh")
    from pxr import Usd
    absent = Usd.Stage.Open(frozen.Flatten(False))
    if absent is None or not absent.RemovePrim(TARGET_ROOT) or absent.GetPrimAtPath(TARGET_ROOT):
        raise ValueError("Could not physically remove the target from its private frozen copy")
    negative = variant_record(absent, state, renderer, deps, clock, False, present["resolved_scene_state_hash"])
    positive_background = background_record(frozen, state, renderer, deps, clock)
    negative_background = background_record(absent, state, renderer, deps, clock)
    if positive_background["background_hash"] != negative_background["background_hash"]:
        raise ValueError("Target removal changed the paired background")
    removal = {"operation": "RemovePrim", "prim_path": TARGET_ROOT, "scope": "private_frozen_variant",
               "parent_positive_scene_state_hash": present["resolved_scene_state_hash"],
               "before_target_present": True, "after_target_present": False,
               "before_target_mesh_count": count, "after_target_mesh_count": _mesh_count(absent),
               "before_root_paths": before_paths, "after_root_paths": _root_paths(absent)}
    return {"present_record": present, "absent_stage": absent, "absent_record": negative,
            "background_hash": positive_background["background_hash"], "removal_record": removal}


def _projection_context(stage, projection):
    """Reuse MARLIN's image-projection API and check the retained actual matrices."""
    from pxr import Gf, Usd, UsdGeom
    from cris.madil.render_service.capture_projection import image_projection
    if not isinstance(projection, dict):
        raise ValueError("Actual capture projection metadata is required")
    camera_path = projection.get("render_product", {}).get("camera", projection.get("camera_path"))
    resolution = projection.get("actual_viewport_resolution", projection.get("resolution_px"))
    if not isinstance(camera_path, str) or not isinstance(resolution, (list, tuple)) or len(resolution) != 2:
        raise ValueError("Projection must identify its actual camera and image resolution")
    if any(type(value) is not int or value <= 0 for value in resolution):
        raise ValueError("Projection resolution must contain positive integers")
    camera = UsdGeom.Camera(stage.GetPrimAtPath(camera_path))
    if not camera or camera.GetProjectionAttr().Get() != "perspective":
        raise ValueError("An existing ideal perspective capture camera is required")
    actual = image_projection(stage, camera_path, tuple(resolution), Usd.TimeCode.Default())
    for field in ("capture_view_matrix", "capture_projection_matrix"):
        matrix = paired._json_data(projection.get(field), "projection matrix")
        if not isinstance(matrix, list) or len(matrix) != 4 or any(not isinstance(row, list) or len(row) != 4 for row in matrix):
            raise ValueError("Projection matrices must be 4 by 4")
        if any(type(value) not in (int, float) for row in matrix for value in row):
            raise ValueError("Projection matrices must contain finite numeric values")
        if max(abs(matrix[i][j] - actual[field][i][j]) for i in range(4) for j in range(4)) > PROJECTION_MATRIX_TOLERANCE:
            raise ValueError("Retained actual camera projection disagrees with composed USD")
    view = Gf.Matrix4d(tuple(tuple(row) for row in actual["capture_view_matrix"]))
    projection_matrix = Gf.Matrix4d(tuple(tuple(row) for row in actual["capture_projection_matrix"]))
    return camera_path, list(resolution), view, projection_matrix


def annotation(stage, projection, state, target_present):
    """Return direct amodal JSON and class-0 YOLO text, with visibility unknown.

    Every evaluated Mesh vertex below the owned actor is projected using its
    complete composed world transform and the actual capture-camera matrices.
    Two-dimensional boxes are clipped to the image; no visible/refraction mask
    is inferred. A present out-of-frame animal keeps its presence metadata and
    empty label text, rather than becoming a target-absent observation.
    """
    if type(target_present) is not bool:
        raise ValueError("target_present must be a boolean")
    snapshot = validate_step(state)
    coordinates = inspect_stage(stage)
    if not coordinates["suitable_for_v2"]:
        raise ValueError("; ".join(coordinates["rejection_reasons"]))
    _physical(stage)
    camera_path, resolution, view, projection_matrix = _projection_context(stage, projection)
    actor = stage.GetPrimAtPath(TARGET_ACTOR)
    if target_present and not actor:
        raise ValueError("The declared positive target is not physically present")
    if not target_present and stage.GetPrimAtPath(TARGET_ROOT):
        raise ValueError("A declared negative still contains the owned target subtree")
    agent = snapshot["agents"][0]
    record = {"schema_version": ANNOTATION_VERSION, "target_present": target_present,
              "species": agent["species"], "class_id": 0, "run_id": snapshot["run_id"],
              "step_index": snapshot["step_index"], "simulation_time_s": snapshot["simulation_time_s"],
              "original_gama_depth_m": agent["depth_m"], "vertical_reference": agent["vertical_reference"],
              "behavioural_state": agent["behavioural_state"], "resolution_px": resolution,
              "camera_path": camera_path, "annotation_semantics": "amodal_direct_evaluated_mesh_projection",
              "class_scope": "Owned harbour porpoise only; unrelated demonstration animals remain unlabelled background",
              "biological_approval": False, "pose_mapping": "static_pose_proxy_v1",
              "pose_scope": "Direct geometry only; body animation, breathing and biological dive pose were not certified",
              "rendered_visibility": "unknown", "visible_mask": None, "refraction_calibrated": False,
              "projected_silhouette_area_px": None, "visible_target_area_px": None,
              "area_semantics": "Rectangle box area only; neither visible pixels nor silhouette area",
              "mesh_paths": [], "vertex_count": 0, "raw_amodal_bbox_xyxy_px": None,
              "amodal_bbox_xyxy_px": None, "amodal_bbox_coco_xywh_px": None,
              "intersects_image": False, "bbox_clipped_to_image": False,
              "annotation_status": "target_physically_removed"}
    if not target_present:
        return {"annotation": record, "yolo_label": ""}
    from pxr import Gf, Usd, UsdGeom
    xs, ys, world_points, mesh_paths = [], [], [], []
    projected_digest = hashlib.sha256()
    units = coordinates["meters_per_scene_unit"]
    for prim in sorted(Usd.PrimRange(actor), key=lambda item: str(item.GetPath())):
        if not prim.IsA(UsdGeom.Mesh):
            continue
        points = UsdGeom.Mesh(prim).GetPointsAttr().Get(Usd.TimeCode.Default())
        if points is None or not len(points):
            continue
        mesh_paths.append(str(prim.GetPath()))
        world_transform = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        for point in points:
            world = Gf.Vec4d(float(point[0]), float(point[1]), float(point[2]), 1) * world_transform
            clip = world * view * projection_matrix
            if any(not math.isfinite(value) for value in (*world, *clip)) or clip[3] <= 0:
                raise ValueError("All target vertices must be finite and in front of the capture camera")
            x = (clip[0] / clip[3] + 1) * resolution[0] / 2
            y = (1 - clip[1] / clip[3]) * resolution[1] / 2
            xs.append(x); ys.append(y)
            world_points.append([float(world[i]) * units for i in range(3)])
            projected_digest.update(struct.pack("<2d", x, y))
    if not xs:
        raise ValueError("The positive target has no evaluated mesh vertices")
    raw = [min(xs), min(ys), max(xs), max(ys)]
    clipped = [max(0, raw[0]), max(0, raw[1]), min(resolution[0], raw[2]), min(resolution[1], raw[3])]
    intersects = clipped[0] < clipped[2] and clipped[1] < clipped[3]
    record.update(mesh_paths=mesh_paths, vertex_count=len(xs), raw_amodal_bbox_xyxy_px=raw,
                  intersects_image=intersects, bbox_clipped_to_image=intersects and clipped != raw,
                  projected_vertices_sha256=projected_digest.hexdigest(),
                  world_bounds_min_m=[min(point[i] for point in world_points) for i in range(3)],
                  world_bounds_max_m=[max(point[i] for point in world_points) for i in range(3)],
                  target_usd_visibility=str(UsdGeom.Imageable(actor).ComputeVisibility()),
                  annotation_status="physically_present_direct_amodal_box" if intersects else "physically_present_outside_image")
    label = ""
    if intersects:
        x0, y0, x1, y1 = clipped
        record.update(amodal_bbox_xyxy_px=clipped, amodal_bbox_coco_xywh_px=[x0, y0, x1 - x0, y1 - y0],
                      bbox_rectangle_area_px=(x1 - x0) * (y1 - y0))
        label = "0 " + " ".join(f"{value:.12f}" for value in (
            (x0 + x1) / (2 * resolution[0]), (y0 + y1) / (2 * resolution[1]),
            (x1 - x0) / resolution[0], (y1 - y0) / resolution[1])) + "\n"
    return {"annotation": paired._json_data(record, "annotation"), "yolo_label": label}
