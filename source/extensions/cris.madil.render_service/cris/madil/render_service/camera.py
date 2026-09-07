"""Smooth chase-camera controls for MARLIN's active Kit viewport."""

import omni.kit.app
import omni.usd
from pydantic import BaseModel, Field
from pxr import Gf, Sdf, Usd, UsdGeom

from .api import router
from .camera_math import (
    chase_camera_targets,
    damp_point,
    documentary_camera_transition,
    horizontal_distance,
    move_point_with_acceleration,
)


_chase_camera_subscription = None
_chase_camera_state = None


class ChaseCameraDataModel(BaseModel):
    target_name: str = Field(default="Dolphin_001")
    camera_name: str = Field(default="DolphinChaseCamera")
    distance: float = Field(default=1200.0, gt=0.0)
    height: float = Field(default=180.0)
    side_offset: float = Field(default=0.0)
    look_ahead: float = Field(default=150.0, ge=0.0)
    look_height: float = Field(default=15.0)
    responsiveness: float = Field(default=3.0, gt=0.0)
    aim_responsiveness: float = Field(default=4.5, gt=0.0)
    documentary_mode: bool = Field(default=True)
    hold_duration: float = Field(default=4.0, ge=0.0)
    dead_zone: float = Field(default=30.0, gt=0.0)
    reaction_delay: float = Field(default=0.8, ge=0.0)
    catch_up_speed: float = Field(default=14.0, gt=0.0)
    catch_up_acceleration: float = Field(default=8.0, gt=0.0)
    settle_distance: float = Field(default=12.0, gt=0.0)
    settle_duration: float = Field(default=1.2, ge=0.0)
    focal_length: float = Field(default=35.0, gt=0.0)
    activate_viewport: bool = Field(default=True)


class ChaseCameraUpdateDataModel(BaseModel):
    distance: float | None = Field(default=None, gt=0.0)
    height: float | None = None
    side_offset: float | None = None
    look_ahead: float | None = Field(default=None, ge=0.0)
    look_height: float | None = None
    responsiveness: float | None = Field(default=None, gt=0.0)
    aim_responsiveness: float | None = Field(default=None, gt=0.0)
    documentary_mode: bool | None = None
    hold_duration: float | None = Field(default=None, ge=0.0)
    dead_zone: float | None = Field(default=None, gt=0.0)
    reaction_delay: float | None = Field(default=None, ge=0.0)
    catch_up_speed: float | None = Field(default=None, gt=0.0)
    catch_up_acceleration: float | None = Field(default=None, gt=0.0)
    settle_distance: float | None = Field(default=None, gt=0.0)
    settle_duration: float | None = Field(default=None, ge=0.0)
    focal_length: float | None = Field(default=None, gt=0.0)


def _active_viewport():
    try:
        from omni.kit.viewport.utility import get_active_viewport

        return get_active_viewport()
    except Exception as exc:
        print(f"[CRIS Chase Camera] Viewport warning: {exc}")
        return None


def _target_pose(stage, target_path: str):
    target_prim = stage.GetPrimAtPath(target_path)

    if not target_prim or not target_prim.IsValid():
        return None

    matrix = UsdGeom.Xformable(
        target_prim
    ).ComputeLocalToWorldTransform(
        Usd.TimeCode.Default()
    )

    position = matrix.ExtractTranslation()
    forward = matrix.TransformDir(Gf.Vec3d(0.0, 0.0, 1.0))

    return (
        (float(position[0]), float(position[1]), float(position[2])),
        (float(forward[0]), float(forward[1]), float(forward[2])),
    )


def _set_camera_transform(stage, state):
    camera_prim = stage.GetPrimAtPath(state["camera_path"])

    if not camera_prim or not camera_prim.IsValid():
        return False

    eye = Gf.Vec3d(*state["camera_position"])
    target = Gf.Vec3d(*state["look_target"])

    # USD cameras look down local -Z with local +Y as up. SetLookAt builds
    # the view matrix, so invert it to author the camera's world transform.
    view_matrix = Gf.Matrix4d(1.0)
    view_matrix.SetLookAt(
        eye,
        target,
        Gf.Vec3d(0.0, 1.0, 0.0),
    )
    camera_matrix = view_matrix.GetInverse()

    transform_attr = camera_prim.GetAttribute("xformOp:transform")

    if not transform_attr or not transform_attr.IsValid():
        xformable = UsdGeom.Xformable(camera_prim)
        xformable.ClearXformOpOrder()
        transform_attr = xformable.AddTransformOp().GetAttr()

    transform_attr.Set(camera_matrix)
    return True


def _update_chase_camera(event):
    global _chase_camera_state

    state = _chase_camera_state

    if state is None:
        return

    try:
        dt = float(event.payload["dt"])
    except Exception:
        dt = 1.0 / 60.0

    if dt <= 0.0:
        return

    stage = omni.usd.get_context().get_stage()

    if stage is None:
        return

    pose = _target_pose(stage, state["target_path"])

    if pose is None:
        state["target_available"] = False
        return

    state["target_available"] = True
    state["total_time"] += dt
    state["mode_elapsed"] += dt
    target_position, forward = pose

    desired_position, desired_look_target = chase_camera_targets(
        target_position=target_position,
        forward=forward,
        distance=state["distance"],
        height=state["height"],
        side_offset=state["side_offset"],
        look_ahead=state["look_ahead"],
        look_height=state["look_height"],
    )

    # Aiming remains responsive even while the camera position is held.
    # This creates a stationary tripod/boat shot that pans with the animal.
    state["look_target"] = damp_point(
        state["look_target"],
        desired_look_target,
        state["aim_responsiveness"],
        dt,
    )

    if not state["documentary_mode"]:
        state["motion_mode"] = "CONTINUOUS"
        state["camera_position"] = damp_point(
            state["camera_position"],
            desired_position,
            state["responsiveness"],
            dt,
        )
        state["camera_velocity"] = (0.0, 0.0, 0.0)
    else:
        position_error = horizontal_distance(
            state["camera_position"],
            desired_position,
        )
        next_mode = documentary_camera_transition(
            mode=state["motion_mode"],
            mode_elapsed=state["mode_elapsed"],
            horizontal_error=position_error,
            hold_duration=state["hold_duration"],
            dead_zone=state["dead_zone"],
            reaction_delay=state["reaction_delay"],
            settle_distance=state["settle_distance"],
            settle_duration=state["settle_duration"],
        )

        if next_mode != state["motion_mode"]:
            state["motion_mode"] = next_mode
            state["mode_elapsed"] = 0.0

            if next_mode in ("HOLD", "DELAY"):
                state["camera_velocity"] = (0.0, 0.0, 0.0)

        if state["motion_mode"] == "CATCH_UP":
            (
                state["camera_position"],
                state["camera_velocity"],
            ) = move_point_with_acceleration(
                current=state["camera_position"],
                target=desired_position,
                velocity=state["camera_velocity"],
                max_speed=state["catch_up_speed"],
                acceleration=state["catch_up_acceleration"],
                dt=dt,
            )
        elif state["motion_mode"] == "SETTLE":
            previous_position = state["camera_position"]
            state["camera_position"] = damp_point(
                previous_position,
                desired_position,
                state["responsiveness"],
                dt,
            )
            state["camera_velocity"] = tuple(
                (
                    state["camera_position"][index]
                    - previous_position[index]
                ) / dt
                for index in range(3)
            )

        state["position_error"] = horizontal_distance(
            state["camera_position"],
            desired_position,
        )

    _set_camera_transform(stage, state)


@router.post(
    "/scene/camera/chase/start",
    summary="Create and start a documentary-style dolphin camera",
)
async def start_chase_camera(data: ChaseCameraDataModel):
    global _chase_camera_subscription
    global _chase_camera_state

    stage = omni.usd.get_context().get_stage()

    if stage is None:
        return {"ok": False, "error": "No live USD stage is open."}

    if not Sdf.Path.IsValidIdentifier(data.target_name):
        return {"ok": False, "error": "Invalid chase-camera target name."}

    if not Sdf.Path.IsValidIdentifier(data.camera_name):
        return {"ok": False, "error": "Invalid chase-camera name."}

    target_path = f"/World/Cetaceans/{data.target_name}"
    pose = _target_pose(stage, target_path)

    if pose is None:
        return {"ok": False, "error": f"Target not found: {target_path}"}

    shutdown_chase_camera(restore_viewport=True)

    UsdGeom.Xform.Define(stage, "/World")
    UsdGeom.Xform.Define(stage, "/World/Cameras")

    camera_path = f"/World/Cameras/{data.camera_name}"
    camera = UsdGeom.Camera.Define(stage, camera_path)
    camera.GetFocalLengthAttr().Set(data.focal_length)
    camera.GetClippingRangeAttr().Set(Gf.Vec2f(1.0, 100000.0))

    camera_xform = UsdGeom.Xformable(camera.GetPrim())
    camera_xform.ClearXformOpOrder()
    camera_xform.AddTransformOp()

    target_position, forward = pose
    camera_position, look_target = chase_camera_targets(
        target_position=target_position,
        forward=forward,
        distance=data.distance,
        height=data.height,
        side_offset=data.side_offset,
        look_ahead=data.look_ahead,
        look_height=data.look_height,
    )

    viewport = _active_viewport()
    previous_camera_path = None

    if viewport is not None:
        previous_camera_path = str(viewport.camera_path)

    _chase_camera_state = {
        "target_name": data.target_name,
        "target_path": target_path,
        "target_available": True,
        "camera_name": data.camera_name,
        "camera_path": camera_path,
        "distance": float(data.distance),
        "height": float(data.height),
        "side_offset": float(data.side_offset),
        "look_ahead": float(data.look_ahead),
        "look_height": float(data.look_height),
        "responsiveness": float(data.responsiveness),
        "aim_responsiveness": float(data.aim_responsiveness),
        "documentary_mode": bool(data.documentary_mode),
        "hold_duration": float(data.hold_duration),
        "dead_zone": float(data.dead_zone),
        "reaction_delay": float(data.reaction_delay),
        "catch_up_speed": float(data.catch_up_speed),
        "catch_up_acceleration": float(data.catch_up_acceleration),
        "settle_distance": float(data.settle_distance),
        "settle_duration": float(data.settle_duration),
        "focal_length": float(data.focal_length),
        "camera_position": camera_position,
        "look_target": look_target,
        "camera_velocity": (0.0, 0.0, 0.0),
        "motion_mode": (
            "HOLD"
            if data.documentary_mode
            else "CONTINUOUS"
        ),
        "mode_elapsed": 0.0,
        "total_time": 0.0,
        "position_error": 0.0,
        "viewport_active": False,
        "previous_camera_path": previous_camera_path,
    }

    _set_camera_transform(stage, _chase_camera_state)

    if data.activate_viewport and viewport is not None:
        viewport.camera_path = camera_path
        _chase_camera_state["viewport_active"] = True

    _chase_camera_subscription = (
        omni.kit.app
        .get_app()
        .get_update_event_stream()
        .create_subscription_to_pop(
            _update_chase_camera,
            name="CRIS Dolphin Chase Camera",
        )
    )

    return {"ok": True, **_chase_camera_state}


@router.post(
    "/scene/camera/chase/update",
    summary="Update documentary-camera framing and motion",
)
async def update_chase_camera(data: ChaseCameraUpdateDataModel):
    global _chase_camera_state

    if _chase_camera_state is None:
        return {"ok": False, "error": "No chase camera is running."}

    changed = {}

    for field in (
        "distance",
        "height",
        "side_offset",
        "look_ahead",
        "look_height",
        "responsiveness",
        "aim_responsiveness",
        "hold_duration",
        "dead_zone",
        "reaction_delay",
        "catch_up_speed",
        "catch_up_acceleration",
        "settle_distance",
        "settle_duration",
        "focal_length",
    ):
        value = getattr(data, field)

        if value is not None:
            _chase_camera_state[field] = float(value)
            changed[field] = float(value)

    if data.documentary_mode is not None:
        _chase_camera_state["documentary_mode"] = bool(
            data.documentary_mode
        )
        _chase_camera_state["motion_mode"] = (
            "HOLD"
            if data.documentary_mode
            else "CONTINUOUS"
        )
        _chase_camera_state["mode_elapsed"] = 0.0
        _chase_camera_state["camera_velocity"] = (0.0, 0.0, 0.0)
        changed["documentary_mode"] = data.documentary_mode

    if data.focal_length is not None:
        stage = omni.usd.get_context().get_stage()

        if stage is not None:
            camera = UsdGeom.Camera.Get(
                stage,
                _chase_camera_state["camera_path"],
            )
            camera.GetFocalLengthAttr().Set(data.focal_length)

    return {
        "ok": True,
        "changed": changed,
        "state": _chase_camera_state,
    }


@router.post(
    "/scene/camera/chase/stop",
    summary="Stop the chase camera and restore the previous viewport camera",
)
async def stop_chase_camera():
    was_running = _chase_camera_subscription is not None
    shutdown_chase_camera(restore_viewport=True)
    return {"ok": True, "was_running": was_running}


@router.get(
    "/scene/camera/chase/status",
    summary="Inspect the dolphin chase camera",
)
async def chase_camera_status():
    if _chase_camera_state is None:
        return {"ok": True, "running": False}

    return {"ok": True, "running": True, **_chase_camera_state}


@router.post(
    "/debug/viewport/capture",
    summary="Capture the active MARLIN viewport for visual diagnostics",
)
async def capture_active_viewport():
    from omni.kit.viewport.utility import capture_viewport_to_file

    viewport = _active_viewport()

    if viewport is None:
        return {"ok": False, "error": "No active viewport is available."}

    file_path = "/tmp/marlin_viewport.png"
    capture = capture_viewport_to_file(viewport, file_path=file_path)
    await capture.wait_for_result(completion_frames=5)

    return {"ok": True, "file_path": file_path}


def shutdown_chase_camera(restore_viewport=True):
    """Release the chase-camera update subscription."""

    global _chase_camera_subscription
    global _chase_camera_state

    state = _chase_camera_state
    _chase_camera_subscription = None

    if restore_viewport and state is not None:
        viewport = _active_viewport()
        previous_path = state.get("previous_camera_path")

        if viewport is not None and previous_path:
            viewport.camera_path = previous_path

    _chase_camera_state = None
