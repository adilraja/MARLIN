"""Temporary native-transform gallery for cetacean asset calibration."""

import math
from pathlib import Path

import omni.kit.app
import omni.timeline
import omni.usd
from pydantic import BaseModel, Field
from pxr import Gf, Usd, UsdGeom, Vt

from .api import router
from .camera import _active_viewport
from .cetacean import CetaceanSpawnDataModel, spawn_cetacean
from .cetacean_motion import (
    GALLERY_MOTION_PROFILES,
    inferred_model_forward_heading,
)
from .config import DEFAULT_DOLPHIN_SWIM_ANIMATION, PROJECT_ROOT
from .skeletal_animation import bind_baked_skeletal_animation


GALLERY_ASSETS = (
    ("Bottlenose_Carimam", "bottlenose_dolphin"),
    ("Cuvier_Whale", "cuvier_whale"),
    ("Frasers_Dolphin", "frasers_dolphin"),
    ("Humpback_Whale", "humpback_whale"),
    ("Manatee", "manatee"),
    ("Bottlenose_DigitalLife", "model_61a_-_bottlenose_dolphin"),
    ("Spotted_Dolphin", "pantropical_spotted_dolphin"),
    ("Pilot_Whale", "pilot_whale"),
    ("Pygmy_Sperm_Whale", "pygmy_sperm_whale"),
    ("Sperm_Whale", "sperm_whale"),
    ("Steno_Dolphin", "steno_dolphin"),
)

_gallery_swim_subscription = None
_gallery_swim_states = []
_gallery_swim_elapsed = 0.0
_gallery_deformation_elapsed = 0.0


class CetaceanGalleryDataModel(BaseModel):
    elevation: float = Field(
        default=500.0,
        description="World-space Y position above the ocean for inspection",
    )
    spacing: float = Field(
        default=1200.0,
        gt=0.0,
        description="X/Z spacing between gallery positions",
    )
    columns: int = Field(
        default=4,
        ge=1,
        le=6,
        description="Number of animals per gallery row",
    )
    native_scale_multiplier: float = Field(
        default=100.0,
        gt=0.0,
        description=(
            "Temporary common display multiplier applied to native USD "
            "scale; this is not a calibrated species scale"
        ),
    )
    activate_viewport_camera: bool = Field(
        default=True,
        description="Activate a static camera that frames the gallery grid",
    )
    apply_provisional_swim_pose: bool = Field(
        default=True,
        description=(
            "Rotate native assets into a common horizontal inspection pose; "
            "this is not a final per-species orientation calibration"
        ),
    )


class GallerySwimPreviewDataModel(BaseModel):
    depth: float = Field(
        default=-150.0,
        description="Common absolute Y depth used only by the gallery preview",
    )
    speed: float = Field(
        default=30.0,
        gt=0.0,
        description=(
            "Common presentation speed in scene units per second; this is "
            "not a biological species speed"
        ),
    )
    travel_half_extent: float = Field(
        default=6500.0,
        gt=0.0,
        description="Preview turn boundary along the world Z axis",
    )
    activate_viewport_camera: bool = Field(default=True)
    deformation_fps: float = Field(
        default=15.0,
        ge=5.0,
        le=30.0,
        description="Mesh-deformation refresh rate for static assets",
    )


def gallery_position(
    index: int,
    *,
    columns: int,
    spacing: float,
    elevation: float,
):
    row, column = divmod(index, columns)
    column_count = min(columns, len(GALLERY_ASSETS) - row * columns)
    x = (column - (column_count - 1) / 2.0) * spacing
    row_count = (len(GALLERY_ASSETS) + columns - 1) // columns
    z = (row - (row_count - 1) / 2.0) * spacing
    return (x, elevation, z)


def gallery_asset_path(species: str) -> Path:
    return (
        PROJECT_ROOT
        / "assets"
        / "cetaceans"
        / species
        / "usd"
        / f"{species}.usd"
    )


def activate_gallery_camera(
    data: CetaceanGalleryDataModel,
    *,
    oblique_swim_view: bool = False,
):
    stage = omni.usd.get_context().get_stage()

    if stage is None:
        return {"ok": False, "error": "No live USD stage is open."}

    camera_path = "/World/Cameras/CetaceanGalleryCamera"
    UsdGeom.Xform.Define(stage, "/World/Cameras")
    camera = UsdGeom.Camera.Define(stage, camera_path)
    camera.GetFocalLengthAttr().Set(35.0)
    camera.GetClippingRangeAttr().Set(Gf.Vec2f(1.0, 100000.0))

    horizontal_span = data.spacing * max(data.columns, 3)
    row_count = (len(GALLERY_ASSETS) + data.columns - 1) // data.columns
    depth_span = data.spacing * max(row_count, 2)
    camera_distance = max(6000.0, horizontal_span * 1.35, depth_span * 2.0)
    camera_height = data.elevation + max(2200.0, depth_span * 0.75)
    camera_x = camera_distance * 0.75 if oblique_swim_view else 0.0
    eye = Gf.Vec3d(camera_x, camera_height, -camera_distance)
    target = Gf.Vec3d(0.0, data.elevation, 0.0)

    view_matrix = Gf.Matrix4d(1.0)
    view_matrix.SetLookAt(eye, target, Gf.Vec3d(0.0, 1.0, 0.0))

    camera_xform = UsdGeom.Xformable(camera.GetPrim())
    camera_xform.ClearXformOpOrder()
    camera_xform.AddTransformOp().Set(view_matrix.GetInverse())

    viewport = _active_viewport()

    if viewport is None:
        return {
            "ok": False,
            "camera_path": camera_path,
            "error": "No active Kit viewport is available.",
        }

    previous_camera_path = str(viewport.camera_path)
    viewport.camera_path = camera_path

    return {
        "ok": True,
        "camera_path": camera_path,
        "previous_camera_path": previous_camera_path,
        "view_style": (
            "oblique_swim_view" if oblique_swim_view else "gallery_overview"
        ),
        "position": tuple(eye),
        "target": tuple(target),
    }


def _public_gallery_swim_states():
    return [
        {
            key: value
            for key, value in state.items()
            if not key.startswith("_")
        }
        for state in _gallery_swim_states
    ]


def _prepare_procedural_meshes(root_prim):
    """Cache static mesh points and infer local deformation axes."""

    try:
        import numpy as np
    except ImportError as exc:
        return [], f"NumPy is unavailable in Kit: {exc}"

    meshes = []

    for prim in Usd.PrimRange(root_prim):
        if not prim.IsA(UsdGeom.Mesh):
            continue

        mesh = UsdGeom.Mesh(prim)
        points = mesh.GetPointsAttr().Get(Usd.TimeCode.Default())

        if not points or len(points) < 4:
            continue

        original = np.asarray(points, dtype=np.float32).copy()
        minimum = original.min(axis=0)
        maximum = original.max(axis=0)
        dimensions = maximum - minimum
        longitudinal_axis = int(np.argmax(dimensions))
        transverse_axes = [
            axis for axis in range(3) if axis != longitudinal_axis
        ]
        vertical_axis = min(
            transverse_axes,
            key=lambda axis: float(dimensions[axis]),
        )
        length = float(dimensions[longitudinal_axis])

        if length <= 1e-6:
            continue

        coordinate = original[:, longitudinal_axis]
        low = float(minimum[longitudinal_axis])
        high = float(maximum[longitudinal_axis])
        normalized = (coordinate - low) / length
        centre = (minimum + maximum) * 0.5
        radial = np.sqrt(sum(
            (original[:, axis] - centre[axis]) ** 2
            for axis in transverse_axes
        ))
        low_values = radial[normalized <= 0.15]
        high_values = radial[normalized >= 0.85]
        low_score = float(np.percentile(low_values, 90)) if len(low_values) else 0.0
        high_score = float(np.percentile(high_values, 90)) if len(high_values) else 0.0
        tail_is_high = high_score >= low_score
        tail_fraction = normalized if tail_is_high else 1.0 - normalized

        meshes.append({
            "path": str(prim.GetPath()),
            "mesh": mesh,
            "original": original,
            "original_vt": Vt.Vec3fArray(points),
            "tail_fraction": tail_fraction,
            "longitudinal_axis": longitudinal_axis,
            "vertical_axis": vertical_axis,
            "body_length": length,
            "tail_end": "positive" if tail_is_high else "negative",
            "tail_is_high": tail_is_high,
            "vertex_count": len(points),
        })

    if not meshes:
        return [], "No deformable static meshes were found."

    return meshes, None


def _deform_gallery_meshes(state):
    import numpy as np

    profile = state["motion_profile"]
    phase = state["_animation_phase"]

    for cache in state.get("_deformation_meshes", []):
        tail_fraction = cache["tail_fraction"]
        start = profile["flex_start"]
        normalized = np.clip(
            (tail_fraction - start) / max(1e-9, 1.0 - start),
            0.0,
            1.0,
        )
        smooth = normalized * normalized * (3.0 - 2.0 * normalized)
        envelope = smooth * smooth
        wave = np.sin(
            phase
            - math.tau * profile["wave_cycles"] * tail_fraction
        )
        offset = (
            cache["body_length"]
            * profile["tail_amplitude_ratio"]
            * envelope
            * wave
        )
        deformed = cache["original"].copy()
        deformed[:, cache["vertical_axis"]] += offset
        cache["mesh"].GetPointsAttr().Set(
            Vt.Vec3fArray.FromNumpy(deformed)
        )


def shutdown_gallery_swimming():
    global _gallery_swim_subscription
    global _gallery_swim_states
    global _gallery_swim_elapsed
    global _gallery_deformation_elapsed

    for state in _gallery_swim_states:
        for cache in state.get("_deformation_meshes", []):
            try:
                cache["mesh"].GetPointsAttr().Set(cache["original_vt"])
            except Exception:
                pass

    _gallery_swim_subscription = None
    _gallery_swim_states = []
    _gallery_swim_elapsed = 0.0
    _gallery_deformation_elapsed = 0.0


def _update_gallery_swimming(event):
    global _gallery_swim_elapsed
    global _gallery_deformation_elapsed

    try:
        dt = float(event.payload["dt"])
    except Exception:
        dt = 1.0 / 60.0

    if dt <= 0.0:
        return

    stage = omni.usd.get_context().get_stage()

    if stage is None:
        return

    _gallery_swim_elapsed += dt
    _gallery_deformation_elapsed += dt
    update_deformation = False

    if _gallery_swim_states:
        interval = 1.0 / _gallery_swim_states[0]["deformation_fps"]

        if _gallery_deformation_elapsed >= interval:
            _gallery_deformation_elapsed %= interval
            update_deformation = True

    for state in _gallery_swim_states:
        prim = stage.GetPrimAtPath(state["prim_path"])

        if not prim or not prim.IsValid():
            continue

        z = state["z"] + state["direction"] * state["speed"] * dt
        limit = state["travel_half_extent"]

        if z > limit:
            z = limit - (z - limit)
            state["direction"] = -1.0
        elif z < -limit:
            z = -limit + (-limit - z)
            state["direction"] = 1.0

        state["z"] = z
        state["heading"] = 0.0 if state["direction"] > 0.0 else 180.0
        state["model_yaw"] = (
            state["heading"] - state["model_forward_heading"]
        ) % 360.0

        xform = UsdGeom.XformCommonAPI(prim)
        xform.SetTranslate(Gf.Vec3d(state["x"], state["depth"], z))
        xform.SetRotate(
            Gf.Vec3f(0.0, state["model_yaw"], 0.0),
            UsdGeom.XformCommonAPI.RotationOrderXYZ,
        )

        state["_animation_phase"] = (
            state["_animation_phase"]
            + math.tau * state["motion_profile"]["cadence_hz"] * dt
        ) % math.tau

        if update_deformation and state["animation_backend"] == "procedural_mesh":
            _deform_gallery_meshes(state)

    skeletal_states = [
        state
        for state in _gallery_swim_states
        if state["animation_backend"] == "skeletal"
        and state.get("skeletal_animation", {}).get("ok", False)
    ]

    if skeletal_states:
        state = skeletal_states[0]
        animation = state["skeletal_animation"]
        duration = animation["duration_seconds"]
        animation_time = (
            animation["start_time_seconds"]
            + (state["_animation_phase"] / math.tau) * duration
        )
        omni.timeline.get_timeline_interface().set_current_time(animation_time)


@router.post(
    "/scene/cetaceans/gallery",
    summary="Spawn the uncalibrated cetacean asset inspection gallery",
)
async def create_cetacean_gallery(data: CetaceanGalleryDataModel):
    shutdown_gallery_swimming()
    animals = []
    model_rotation = (
        (-90.0, 0.0, 0.0)
        if data.apply_provisional_swim_pose
        else (0.0, 0.0, 0.0)
    )
    calibration_status = (
        "provisional_common_swim_pose"
        if data.apply_provisional_swim_pose
        else "uncalibrated_native_transform"
    )

    for index, (name, species) in enumerate(GALLERY_ASSETS):
        asset_path = gallery_asset_path(species)
        position = gallery_position(
            index,
            columns=data.columns,
            spacing=data.spacing,
            elevation=data.elevation,
        )

        if not asset_path.is_file():
            animals.append(
                {
                    "ok": False,
                    "name": name,
                    "species": species,
                    "asset_path": str(asset_path),
                    "error": "Converted USD asset not found.",
                }
            )
            continue

        result = await spawn_cetacean(
            CetaceanSpawnDataModel(
                name=name,
                asset_path=str(asset_path),
                position=position,
                rotation=(0.0, 0.0, 0.0),
                model_rotation=model_rotation,
                scale=data.native_scale_multiplier,
            )
        )

        animals.append(
            {
                **result,
                "species": species,
                "calibration_status": calibration_status,
            }
        )

    loaded_count = sum(animal.get("ok", False) for animal in animals)
    camera = {
        "ok": True,
        "activated": False,
    }

    if data.activate_viewport_camera:
        camera = activate_gallery_camera(data)
        camera["activated"] = camera.get("ok", False)

    try:
        omni.usd.get_context().get_selection().set_selected_prim_paths(
            [],
            False,
        )
    except Exception as exc:
        camera["selection_warning"] = str(exc)

    return {
        "ok": loaded_count == len(GALLERY_ASSETS),
        "message": "MARLIN cetacean calibration gallery created.",
        "calibration_status": calibration_status,
        "loaded_count": loaded_count,
        "requested_count": len(GALLERY_ASSETS),
        "inspection_scale_multiplier": data.native_scale_multiplier,
        "camera": camera,
        "animals": animals,
    }


@router.post(
    "/scene/cetaceans/gallery/swim/start",
    summary="Start species-specific gallery swimming animation",
)
async def start_gallery_swimming(data: GallerySwimPreviewDataModel):
    global _gallery_swim_subscription
    global _gallery_swim_states

    stage = omni.usd.get_context().get_stage()

    if stage is None:
        return {"ok": False, "error": "No live USD stage is open."}

    shutdown_gallery_swimming()
    missing = []

    for index, (name, species) in enumerate(GALLERY_ASSETS):
        prim_path = f"/World/Cetaceans/{name}"
        prim = stage.GetPrimAtPath(prim_path)

        if not prim or not prim.IsValid():
            missing.append(name)
            continue

        transform = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(
            Usd.TimeCode.Default()
        )
        position = transform.ExtractTranslation()
        direction = 1.0 if index % 2 == 0 else -1.0
        heading = 0.0 if direction > 0.0 else 180.0
        motion_profile = dict(GALLERY_MOTION_PROFILES[species])
        animation_backend = motion_profile["backend"]
        deformation_meshes = []
        deformation_error = None
        skeletal_animation = None

        if animation_backend == "procedural_mesh":
            deformation_meshes, deformation_error = (
                _prepare_procedural_meshes(prim)
            )
        else:
            skeletal_animation = bind_baked_skeletal_animation(
                stage,
                cetacean_path=prim_path,
                animation_file=DEFAULT_DOLPHIN_SWIM_ANIMATION,
            )

        model_forward_heading = 0.0

        if deformation_meshes:
            primary_mesh = max(
                deformation_meshes,
                key=lambda mesh: mesh["vertex_count"],
            )
            model_forward_heading = inferred_model_forward_heading(
                primary_mesh["longitudinal_axis"],
                primary_mesh["tail_is_high"],
            )

        model_yaw = (heading - model_forward_heading) % 360.0

        state = {
            "name": name,
            "species": species,
            "prim_path": prim_path,
            "x": float(position[0]),
            "z": float(position[2]),
            "depth": float(data.depth),
            "speed": float(data.speed),
            "direction": direction,
            "heading": heading,
            "model_forward_heading": model_forward_heading,
            "model_yaw": model_yaw,
            "travel_half_extent": float(data.travel_half_extent),
            "body_animation": bool(
                deformation_meshes
                or (skeletal_animation or {}).get("ok", False)
            ),
            "animation_backend": animation_backend,
            "motion_profile_basis": "research_informed_visual_preview",
            "motion_profile": motion_profile,
            "deformation_fps": float(data.deformation_fps),
            "deformable_mesh_count": len(deformation_meshes),
            "deformed_vertex_count": sum(
                mesh["vertex_count"] for mesh in deformation_meshes
            ),
            "deformation_error": deformation_error,
            "skeletal_animation": skeletal_animation,
            "_deformation_meshes": deformation_meshes,
            "_animation_phase": math.tau * index / len(GALLERY_ASSETS),
        }
        _gallery_swim_states.append(state)

        xform = UsdGeom.XformCommonAPI(prim)
        xform.SetTranslate(Gf.Vec3d(state["x"], state["depth"], state["z"]))
        xform.SetRotate(
            Gf.Vec3f(0.0, model_yaw, 0.0),
            UsdGeom.XformCommonAPI.RotationOrderXYZ,
        )

    if missing:
        shutdown_gallery_swimming()
        return {
            "ok": False,
            "error": "Create the complete gallery before starting preview motion.",
            "missing": missing,
        }

    _gallery_swim_subscription = (
        omni.kit.app
        .get_app()
        .get_update_event_stream()
        .create_subscription_to_pop(
            _update_gallery_swimming,
            name="MARLIN Gallery Swimming Preview",
        )
    )

    camera = {"ok": True, "activated": False}

    if data.activate_viewport_camera:
        camera = activate_gallery_camera(
            CetaceanGalleryDataModel(elevation=data.depth),
            oblique_swim_view=True,
        )
        camera["activated"] = camera.get("ok", False)

    return {
        "ok": True,
        "running": True,
        "mode": "species_specific_gallery_animation",
        "animal_count": len(_gallery_swim_states),
        "body_animation": all(
            state["body_animation"] for state in _gallery_swim_states
        ),
        "animation_backends": {
            "skeletal": sum(
                state["animation_backend"] == "skeletal"
                for state in _gallery_swim_states
            ),
            "procedural_mesh": sum(
                state["animation_backend"] == "procedural_mesh"
                for state in _gallery_swim_states
            ),
        },
        "camera": camera,
        "animals": _public_gallery_swim_states(),
    }


@router.get(
    "/scene/cetaceans/gallery/swim/status",
    summary="Inspect gallery swimming preview state",
)
async def gallery_swimming_status():
    return {
        "running": _gallery_swim_subscription is not None,
        "mode": "species_specific_gallery_animation",
        "animal_count": len(_gallery_swim_states),
        "animals": _public_gallery_swim_states(),
    }


@router.post(
    "/scene/cetaceans/gallery/swim/stop",
    summary="Stop gallery swimming preview motion",
)
async def stop_gallery_swimming():
    was_running = _gallery_swim_subscription is not None
    shutdown_gallery_swimming()
    return {"ok": True, "was_running": was_running}
