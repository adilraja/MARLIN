"""Cetacean spawning, transforms, and live swimming APIs."""

import math
import os

import omni.kit.app
import omni.timeline
import omni.usd
from pydantic import BaseModel, Field
from pxr import Gf, Sdf, UsdGeom

from .api import router
from .config import (
    DEFAULT_DOLPHIN_ASSET,
    DEFAULT_DOLPHIN_SWIM_ANIMATION,
)
from .movement import (
    move_toward,
    natural_swim_attitude,
    normalize_heading,
    turn_toward,
)
from .ocean import _sample_ocean_surface_height
from .skeletal_animation import bind_baked_skeletal_animation

# =========================================================================
# CRIS Cetacean Spawning
# =========================================================================


class CetaceanSpawnDataModel(BaseModel):
    name: str = Field(
        default="Dolphin_001",
        description="USD prim name for the cetacean",
    )

    asset_path: str = Field(
        default=DEFAULT_DOLPHIN_ASSET,
        description="Absolute path to the cetacean USD asset",
    )

    position: tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0),
    )

    rotation: tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0),
        description="World-space XYZ rotation on the motion root",
    )

    model_rotation: tuple[float, float, float] = Field(
        default=(-90.0, 0.0, 0.0),
        description=(
            "Fixed XYZ correction that keeps the animated dolphin "
            "horizontal, dorsal-side up, and facing MARLIN's forward axis"
        ),
    )

    scale: float = Field(
        default=1.0,
        gt=0.0,
    )


@router.post(
    "/scene/cetacean/spawn",
    summary="Spawn a cetacean USD asset into the live stage",
)
async def spawn_cetacean(
    data: CetaceanSpawnDataModel,
):
    import os
    from pxr import Usd

    stage = omni.usd.get_context().get_stage()

    if stage is None:
        return {
            "ok": False,
            "error": "No live USD stage is open.",
        }

    asset_path = os.path.abspath(
        os.path.expanduser(data.asset_path)
    )

    if not os.path.isfile(asset_path):
        return {
            "ok": False,
            "error": f"Cetacean asset not found: {asset_path}",
        }

    if not Sdf.Path.IsValidIdentifier(data.name):
        return {
            "ok": False,
            "error": f"Invalid cetacean name: {data.name}",
        }

    # Make sure the scene hierarchy exists.
    UsdGeom.Xform.Define(
        stage,
        "/World",
    )

    UsdGeom.Xform.Define(
        stage,
        "/World/Cetaceans",
    )

    cetacean_path = (
        f"/World/Cetaceans/{data.name}"
    )

    # Replace an existing cetacean with the same name.
    existing = stage.GetPrimAtPath(
        cetacean_path
    )

    if existing and existing.IsValid():
        stage.RemovePrim(
            cetacean_path
        )

    # ---------------------------------------------------------------
    # Inspect the source USD and determine which source prim to reference.
    # ---------------------------------------------------------------

    source_stage = Usd.Stage.Open(
        asset_path
    )

    if source_stage is None:
        return {
            "ok": False,
            "error": f"Could not open USD asset: {asset_path}",
        }

    source_prim = source_stage.GetDefaultPrim()

    if not source_prim or not source_prim.IsValid():

        root_prims = list(
            source_stage
            .GetPseudoRoot()
            .GetChildren()
        )

        if not root_prims:
            return {
                "ok": False,
                "error": "USD asset contains no root prims.",
            }

        source_prim = root_prims[0]

    source_prim_path = (
        source_prim.GetPath()
    )

    # ---------------------------------------------------------------
    # Create a motion root and a child containing the referenced model.
    # Keeping these transforms separate prevents heading yaw from mixing
    # with the asset's fixed orientation correction.
    # ---------------------------------------------------------------

    cetacean = UsdGeom.Xform.Define(
        stage,
        cetacean_path,
    )

    model_path = f"{cetacean_path}/Model"
    model = UsdGeom.Xform.Define(
        stage,
        model_path,
    )

    reference = Sdf.Reference(
        asset_path,
        source_prim_path,
    )

    model.GetPrim().GetReferences().AddReference(
        reference
    )

    model_xform = UsdGeom.XformCommonAPI(
        model
    )

    model_xform.SetRotate(
        Gf.Vec3f(*data.model_rotation),
        UsdGeom.XformCommonAPI.RotationOrderXYZ,
    )

    # ---------------------------------------------------------------
    # Apply MARLIN-controlled transform.
    # ---------------------------------------------------------------

    xform = UsdGeom.XformCommonAPI(
        cetacean
    )

    xform.SetTranslate(
        Gf.Vec3d(*data.position)
    )

    xform.SetRotate(
        Gf.Vec3f(*data.rotation),
        UsdGeom.XformCommonAPI.RotationOrderXYZ,
    )

    xform.SetScale(
        Gf.Vec3f(
            data.scale,
            data.scale,
            data.scale,
        )
    )

    print(
        "[CRIS Render Service] "
        f"Spawned cetacean {data.name} "
        f"from {asset_path}"
    )

    return {
        "ok": True,
        "name": data.name,
        "prim_path": cetacean_path,
        "model_path": model_path,
        "asset_path": asset_path,
        "source_prim": str(source_prim_path),
        "position": data.position,
        "rotation": data.rotation,
        "model_rotation": data.model_rotation,
        "scale": data.scale,
    }

# =========================================================================
# CRIS Live Cetacean Transform Control
# =========================================================================


class CetaceanTransformDataModel(BaseModel):
    name: str = Field(
        default="Dolphin_001",
    )

    position: tuple[float, float, float] | None = Field(
        default=None,
        description="New XYZ position",
    )

    rotation: tuple[float, float, float] | None = Field(
        default=None,
        description="New XYZ rotation in degrees",
    )

    scale: float | None = Field(
        default=None,
        gt=0.0,
    )


@router.post(
    "/scene/cetacean/transform",
    summary="Move or rotate an existing cetacean",
)
async def transform_cetacean(
    data: CetaceanTransformDataModel,
):

    stage = omni.usd.get_context().get_stage()

    if stage is None:
        return {
            "ok": False,
            "error": "No live USD stage is open.",
        }

    cetacean_path = (
        f"/World/Cetaceans/{data.name}"
    )

    cetacean_prim = stage.GetPrimAtPath(
        cetacean_path
    )

    if not cetacean_prim or not cetacean_prim.IsValid():
        return {
            "ok": False,
            "error": f"Cetacean not found: {cetacean_path}",
        }

    xform = UsdGeom.XformCommonAPI(
        cetacean_prim
    )

    changed = {}

    if data.position is not None:
        xform.SetTranslate(
            Gf.Vec3d(*data.position)
        )
        changed["position"] = data.position

    if data.rotation is not None:
        xform.SetRotate(
            Gf.Vec3f(*data.rotation),
            UsdGeom.XformCommonAPI.RotationOrderXYZ,
        )
        changed["rotation"] = data.rotation

    if data.scale is not None:
        xform.SetScale(
            Gf.Vec3f(
                data.scale,
                data.scale,
                data.scale,
            )
        )
        changed["scale"] = data.scale

    if not changed:
        return {
            "ok": False,
            "error": "No transform parameters supplied.",
        }

    print(
        "[CRIS Render Service] "
        f"Updated {cetacean_path}: {changed}"
    )

    return {
        "ok": True,
        "prim_path": cetacean_path,
        "changed": changed,
    }

# =========================================================================
# CRIS Cetacean Swimming
# =========================================================================


@router.get(
    "/scene/cetacean/rig/status",
    summary="Inspect the imported dolphin skeleton and skin bindings",
)
async def cetacean_rig_status(name: str = "Dolphin_001"):
    from pxr import Usd, UsdGeom, UsdSkel

    stage = omni.usd.get_context().get_stage()

    if stage is None:
        return {"ok": False, "error": "No live USD stage is open."}

    root_path = f"/World/Cetaceans/{name}"
    root_prim = stage.GetPrimAtPath(root_path)

    if not root_prim or not root_prim.IsValid():
        return {"ok": False, "error": f"Cetacean not found: {root_path}"}

    skeletons = []
    skel_roots = []
    animations = []
    meshes = []

    for prim in Usd.PrimRange(root_prim):
        path = str(prim.GetPath())

        if prim.IsA(UsdSkel.Root):
            skel_roots.append(path)

        if prim.IsA(UsdSkel.Skeleton):
            skeleton = UsdSkel.Skeleton(prim)
            binding = UsdSkel.BindingAPI(prim)
            skeletons.append({
                "path": path,
                "joints": [
                    str(joint)
                    for joint in skeleton.GetJointsAttr().Get() or []
                ],
                "rest_transform_count": len(
                    skeleton.GetRestTransformsAttr().Get() or []
                ),
                "animation_sources": [
                    str(target)
                    for target in binding.GetAnimationSourceRel().GetTargets()
                ],
            })

        if prim.IsA(UsdSkel.Animation):
            animation = UsdSkel.Animation(prim)
            animations.append({
                "path": path,
                "joints": [
                    str(joint)
                    for joint in animation.GetJointsAttr().Get() or []
                ],
            })

        if prim.IsA(UsdGeom.Mesh):
            binding = UsdSkel.BindingAPI(prim)
            meshes.append({
                "path": path,
                "applied_schemas": [
                    str(schema)
                    for schema in prim.GetAppliedSchemas()
                ],
                "skeleton_targets": [
                    str(target)
                    for target in binding.GetSkeletonRel().GetTargets()
                ],
            })

    return {
        "ok": True,
        "root_path": root_path,
        "skel_roots": skel_roots,
        "skeletons": skeletons,
        "animations": animations,
        "meshes": meshes,
    }

_cetacean_swim_subscription = None
_cetacean_swim_state = None


class CetaceanSwimDataModel(BaseModel):
    name: str = "Dolphin_001"

    speed: float = Field(
        default=5.0,
        ge=0.0,
        le=500.0,
    )

    heading: float = Field(
        default=0.0,
        description="Heading in degrees. 0 = +Z.",
    )

    depth: float = Field(
        default=60.0,
        description="Current absolute Y position for now.",
    )

    world_half_extent: float = Field(
        default=2500.0,
        gt=0.0,
    )

    turn_margin: float = Field(
        default=400.0,
        gt=0.0,
        description="Distance from boundary where automatic turning begins.",
    )

    turn_rate: float = Field(
        default=30.0,
        gt=0.0,
        description="Maximum turning rate in degrees per second.",
    )
    follow_ocean_surface: bool = Field(
        default=False,
        description=(
            "If true, dolphin Y follows the animated ocean surface."
        ),
    )

    surface_offset: float = Field(
        default=60.0,
        description=(
            "Vertical offset relative to ocean surface. "
            "Positive is above surface; negative is below."
        ),
    )

    vertical_follow_rate: float = Field(
        default=40.0,
        gt=0.0,
        description=(
            "Maximum vertical adjustment in scene units per second."
        ),
    )

    depth_below_surface: float | None = Field(
        default=None,
        ge=0.0,
        description=(
            "Target depth below the moving ocean surface. "
            "0 = surface, positive values = underwater."
        ),
    )

    dive_rate: float = Field(
        default=20.0,
        gt=0.0,
        description=(
            "Maximum descent rate in scene units per second."
        ),
    )

    ascent_rate: float = Field(
        default=15.0,
        gt=0.0,
        description=(
            "Maximum ascent rate in scene units per second."
        ),
    )

    body_animation: bool = Field(
        default=True,
        description="Play the authored skeletal swim cycle while moving",
    )

    animation_reference_speed: float = Field(
        default=5.0,
        gt=0.0,
        description="World speed that plays the authored cycle at 1x",
    )

    animation_min_rate: float = Field(
        default=0.35,
        ge=0.0,
        description="Slowest cycle rate while the dolphin is moving",
    )

    animation_max_rate: float = Field(
        default=2.5,
        gt=0.0,
        description="Fastest allowed skeletal animation rate",
    )

    max_pitch: float = Field(
        default=16.0,
        ge=0.0,
        description="Maximum body pitch while diving or surfacing",
    )

    max_bank: float = Field(
        default=12.0,
        ge=0.0,
        description="Maximum body bank while turning",
    )

    pose_follow_rate: float = Field(
        default=45.0,
        gt=0.0,
        description="Pitch/bank smoothing rate in degrees per second",
    )




class CetaceanSwimUpdateDataModel(BaseModel):
    name: str = "Dolphin_001"

    speed: float | None = Field(
        default=None,
        ge=0.0,
        le=500.0,
    )

    heading: float | None = None

    depth: float | None = None

    depth_below_surface: float | None = Field(
        default=None,
        ge=0.0,
    )

    dive_rate: float | None = Field(
        default=None,
        gt=0.0,
    )

    ascent_rate: float | None = Field(
        default=None,
        gt=0.0,
    )

    body_animation: bool | None = None


def _discover_authored_animation(stage, root_prim):
    """Find composed time samples under the referenced dolphin model."""

    from pxr import Usd, UsdSkel

    time_samples = set()
    animation_paths = []
    time_sampled_attributes = 0

    for prim in Usd.PrimRange(root_prim):
        if prim.IsA(UsdSkel.Animation):
            animation_paths.append(str(prim.GetPath()))

        for attribute in prim.GetAttributes():
            try:
                samples = attribute.GetTimeSamples()
            except Exception:
                continue

            if samples:
                time_sampled_attributes += 1
                time_samples.update(float(sample) for sample in samples)

    if not time_samples:
        return {
            "available": False,
            "animation_paths": animation_paths,
            "time_sampled_attributes": time_sampled_attributes,
            "start_time_code": None,
            "end_time_code": None,
            "start_time_seconds": None,
            "end_time_seconds": None,
            "duration_seconds": 0.0,
        }

    start_time_code = min(time_samples)
    end_time_code = max(time_samples)
    time_codes_per_second = float(stage.GetTimeCodesPerSecond())

    if time_codes_per_second <= 0.0:
        time_codes_per_second = 24.0

    start_time_seconds = start_time_code / time_codes_per_second
    end_time_seconds = end_time_code / time_codes_per_second

    return {
        "available": end_time_seconds > start_time_seconds,
        "animation_paths": animation_paths,
        "time_sampled_attributes": time_sampled_attributes,
        "start_time_code": start_time_code,
        "end_time_code": end_time_code,
        "start_time_seconds": start_time_seconds,
        "end_time_seconds": end_time_seconds,
        "duration_seconds": max(
            0.0,
            end_time_seconds - start_time_seconds,
        ),
    }


def _update_cetacean_swimming(event):

    global _cetacean_swim_state

    state = _cetacean_swim_state

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

    prim = stage.GetPrimAtPath(
        state["prim_path"]
    )

    if not prim or not prim.IsValid():
        return

    x = state["x"]
    z = state["z"]
    previous_heading = state["heading"]
    previous_y = state["current_y"]

    half_extent = state["world_half_extent"]
    turn_margin = state["turn_margin"]

    safe_limit = (
        half_extent - turn_margin
    )

    # -------------------------------------------------------------
    # Normal steering follows the user-requested heading.
    # Near a boundary, MARLIN steers the dolphin toward the centre.
    # -------------------------------------------------------------

    target_heading = state["requested_heading"]

    near_boundary = (
        abs(x) >= safe_limit
        or
        abs(z) >= safe_limit
    )

    if near_boundary:

        # Vector from current position toward world centre.
        dx_to_center = -x
        dz_to_center = -z

        target_heading = math.degrees(
            math.atan2(
                dx_to_center,
                dz_to_center,
            )
        )

        target_heading = normalize_heading(
            target_heading
        )

        state["boundary_avoidance"] = True

    else:
        state["boundary_avoidance"] = False

    # -------------------------------------------------------------
    # Smooth turn instead of instantaneous rotation.
    # -------------------------------------------------------------

    maximum_turn = (
        state["turn_rate"] * dt
    )

    state["heading"] = turn_toward(
        state["heading"],
        target_heading,
        maximum_turn,
    )

    heading_rad = math.radians(
        state["heading"]
    )

    # Our current convention:
    # heading 0 degrees -> +Z
    dx = math.sin(
        heading_rad
    )

    dz = math.cos(
        heading_rad
    )

    state["x"] += (
        dx
        * state["speed"]
        * dt
    )

    state["z"] += (
        dz
        * state["speed"]
        * dt
    )
    # -------------------------------------------------------------
    # Couple dolphin vertical position to animated ocean.
    # -------------------------------------------------------------

    # -------------------------------------------------------------
    # Vertical behaviour: ocean-relative diving and surfacing
    # -------------------------------------------------------------

    if state["follow_ocean_surface"]:

        surface_y = (
            _sample_ocean_surface_height(
                state["x"],
                state["z"],
            )
        )

        if surface_y is not None:

            surface_y = float(surface_y)

            state["ocean_surface_y"] = (
                surface_y
            )

            target_depth = state.get(
                "target_depth_below_surface"
            )

            # ---------------------------------------------------------
            # New physical depth mode
            # ---------------------------------------------------------

            if target_depth is not None:

                current_depth = float(
                    state.get(
                        "current_depth_below_surface",
                        0.0,
                    )
                )

                target_depth = float(
                    target_depth
                )

                if target_depth > current_depth:

                    # Diving
                    max_depth_change = (
                        state["dive_rate"]
                        * dt
                    )

                else:

                    # Surfacing
                    max_depth_change = (
                        state["ascent_rate"]
                        * dt
                    )

                current_depth = (
                    move_toward(
                        current_depth,
                        target_depth,
                        max_depth_change,
                    )
                )

                state[
                    "current_depth_below_surface"
                ] = current_depth

                desired_y = (
                    surface_y
                    - current_depth
                )

            # ---------------------------------------------------------
            # Legacy surface-offset mode
            # ---------------------------------------------------------

            else:

                desired_y = (
                    surface_y
                    + state["surface_offset"]
                )

            # Smooth the actual vertical movement.
            state["current_y"] = (
                move_toward(
                    state["current_y"],
                    desired_y,
                    state["vertical_follow_rate"]
                    * dt,
                )
            )

            state[
                "actual_depth_below_surface"
            ] = (
                surface_y
                - state["current_y"]
            )

    else:

        # Legacy absolute-Y mode.
        state["current_y"] = (
            state["depth"]
        )

        state[
            "actual_depth_below_surface"
        ] = None

    # -------------------------------------------------------------
    # Natural whole-body attitude.
    #
    # The referenced skeleton owns the tail/spine swim motion. The motion
    # root only adds gentle pitch for vertical travel and bank for turns.
    # -------------------------------------------------------------

    vertical_velocity = (
        state["current_y"] - previous_y
    ) / dt

    heading_change = (
        (state["heading"] - previous_heading + 180.0)
        % 360.0
    ) - 180.0
    turning_rate = heading_change / dt

    target_pitch, target_bank = natural_swim_attitude(
        vertical_velocity=vertical_velocity,
        horizontal_speed=state["speed"],
        turning_rate=turning_rate,
        max_pitch=state["max_pitch"],
        max_bank=state["max_bank"],
    )

    state["pitch"] = move_toward(
        state["pitch"],
        target_pitch,
        state["pose_follow_rate"] * dt,
    )
    state["bank"] = move_toward(
        state["bank"],
        target_bank,
        state["pose_follow_rate"] * dt,
    )
    state["vertical_velocity"] = vertical_velocity
    state["turning_rate"] = turning_rate

    # Drive the composed USD animation by advancing Kit's stage time. This
    # keeps the authored spine/flipper/fluke cycle intact and synchronizes
    # its rate to MARLIN's requested world speed.
    animation = state["authored_animation"]

    if (
        state["body_animation"]
        and animation["available"]
        and animation["duration_seconds"] > 0.0
    ):
        if state["speed"] <= 0.0:
            playback_rate = 0.0
        else:
            playback_rate = (
                state["speed"]
                / state["animation_reference_speed"]
            )
            playback_rate = max(
                state["animation_min_rate"],
                min(state["animation_max_rate"], playback_rate),
            )

        state["animation_playback_rate"] = playback_rate
        state["animation_phase_seconds"] = (
            state["animation_phase_seconds"]
            + dt * playback_rate
        ) % animation["duration_seconds"]

        current_animation_time = (
            animation["start_time_seconds"]
            + state["animation_phase_seconds"]
        )
        state["animation_time_seconds"] = current_animation_time

        omni.timeline.get_timeline_interface().set_current_time(
            current_animation_time
        )
    else:
        state["animation_playback_rate"] = 0.0

    xform = UsdGeom.XformCommonAPI(
        prim
    )

    xform.SetTranslate(
        Gf.Vec3d(
            state["x"],
            state["current_y"],
            state["z"],
        )
    )

    # The referenced model's child transform owns the fixed 90-degree
    # asset correction. The root receives only natural motion attitude.
    xform.SetRotate(
        Gf.Vec3f(
            state["pitch"],
            state["heading"],
            state["bank"],
        ),
        UsdGeom.XformCommonAPI.RotationOrderXYZ,
    )


@router.post(
    "/scene/cetacean/swim/start",
    summary="Start bounded cetacean swimming",
)
async def start_cetacean_swimming(
    data: CetaceanSwimDataModel,
):

    from pxr import Usd

    global _cetacean_swim_subscription
    global _cetacean_swim_state

    stage = omni.usd.get_context().get_stage()

    if stage is None:
        return {
            "ok": False,
            "error": "No live USD stage is open.",
        }

    prim_path = (
        f"/World/Cetaceans/{data.name}"
    )

    prim = stage.GetPrimAtPath(
        prim_path
    )

    if not prim or not prim.IsValid():
        return {
            "ok": False,
            "error": f"Cetacean not found: {prim_path}",
        }

    # Stop an existing controller.
    _cetacean_swim_subscription = None

    transform = (
        UsdGeom.Xformable(prim)
        .ComputeLocalToWorldTransform(
            Usd.TimeCode.Default()
        )
    )

    current_position = (
        transform.ExtractTranslation()
    )

    initial_surface_y = None
    initial_depth_below_surface = 0.0

    if data.follow_ocean_surface:

        initial_surface_y = (
            _sample_ocean_surface_height(
                float(current_position[0]),
                float(current_position[2]),
            )
        )

        if initial_surface_y is not None:

            initial_depth_below_surface = max(
                0.0,
                float(initial_surface_y)
                - float(current_position[1]),
            )

    initial_heading = (
        normalize_heading(data.heading)
    )

    animation_binding = None

    if data.body_animation:
        animation_binding = bind_baked_skeletal_animation(
            stage=stage,
            cetacean_path=prim_path,
            animation_file=DEFAULT_DOLPHIN_SWIM_ANIMATION,
        )

        if not animation_binding.get("ok", False):
            return {
                "ok": False,
                "error": animation_binding.get(
                    "error",
                    "Could not bind dolphin swim animation.",
                ),
                "animation_binding": animation_binding,
            }

    authored_animation = _discover_authored_animation(
        stage,
        prim,
    )

    _cetacean_swim_state = {
        "name": data.name,

        "prim_path": prim_path,

        "x": float(
            current_position[0]
        ),

        "z": float(
            current_position[2]
        ),

        "depth": float(
            data.depth
        ),

        "speed": float(
            data.speed
        ),

        "heading": initial_heading,

        "requested_heading": initial_heading,

        "world_half_extent": float(
            data.world_half_extent
        ),

        "turn_margin": float(
            data.turn_margin
        ),

        "turn_rate": float(
            data.turn_rate
        ),

        "boundary_avoidance": False,
        "follow_ocean_surface": bool(
            data.follow_ocean_surface
        ),

        "surface_offset": float(
            data.surface_offset
        ),

        "vertical_follow_rate": float(
            data.vertical_follow_rate
        ),

        "current_y": float(
            current_position[1]
        ),

        "ocean_surface_y": (
            None
            if initial_surface_y is None
            else float(initial_surface_y)
        ),

        "target_depth_below_surface": (
            None
            if data.depth_below_surface is None
            else float(data.depth_below_surface)
        ),

        "current_depth_below_surface": float(
            initial_depth_below_surface
        ),

        "actual_depth_below_surface": None,

        "dive_rate": float(
            data.dive_rate
        ),

        "ascent_rate": float(
            data.ascent_rate
        ),

        "body_animation": bool(
            data.body_animation
        ),

        "authored_animation": authored_animation,

        "animation_binding": animation_binding,

        "animation_reference_speed": float(
            data.animation_reference_speed
        ),

        "animation_min_rate": float(
            data.animation_min_rate
        ),

        "animation_max_rate": float(
            data.animation_max_rate
        ),

        "animation_phase_seconds": 0.0,

        "animation_time_seconds": (
            authored_animation["start_time_seconds"]
        ),

        "animation_playback_rate": 0.0,

        "max_pitch": float(data.max_pitch),

        "max_bank": float(data.max_bank),

        "pose_follow_rate": float(
            data.pose_follow_rate
        ),

        "pitch": 0.0,

        "bank": 0.0,

        "vertical_velocity": 0.0,

        "turning_rate": 0.0,
    }

    if authored_animation["available"]:
        omni.timeline.get_timeline_interface().set_current_time(
            authored_animation["start_time_seconds"]
        )

    _cetacean_swim_subscription = (
        omni.kit.app
        .get_app()
        .get_update_event_stream()
        .create_subscription_to_pop(
            _update_cetacean_swimming,
            name="CRIS Cetacean Swimming",
        )
    )

    return {
        "ok": True,
        **_cetacean_swim_state,
    }


@router.post(
    "/scene/cetacean/swim/update",
    summary="Update swimming speed, heading or depth",
)
async def update_cetacean_swimming(
    data: CetaceanSwimUpdateDataModel,
):

    global _cetacean_swim_state

    if _cetacean_swim_state is None:
        return {
            "ok": False,
            "error": "No cetacean swimmer is running.",
        }

    if (
        _cetacean_swim_state["name"]
        != data.name
    ):
        return {
            "ok": False,
            "error": (
                f"{data.name} is not the "
                "currently controlled cetacean."
            ),
        }

    changed = {}

    if data.depth_below_surface is not None:

        _cetacean_swim_state[
            "target_depth_below_surface"
        ] = float(
            data.depth_below_surface
        )

        # A depth command automatically enables
        # ocean-relative positioning.
        _cetacean_swim_state[
            "follow_ocean_surface"
        ] = True

        changed[
            "depth_below_surface"
        ] = data.depth_below_surface


    if data.dive_rate is not None:

        _cetacean_swim_state[
            "dive_rate"
        ] = float(data.dive_rate)

        changed[
            "dive_rate"
        ] = data.dive_rate


    if data.ascent_rate is not None:

        _cetacean_swim_state[
            "ascent_rate"
        ] = float(data.ascent_rate)

        changed[
            "ascent_rate"
        ] = data.ascent_rate

    if data.speed is not None:

        _cetacean_swim_state[
            "speed"
        ] = float(data.speed)

        changed["speed"] = data.speed

    if data.body_animation is not None:

        _cetacean_swim_state[
            "body_animation"
        ] = bool(data.body_animation)

        changed["body_animation"] = data.body_animation

    if data.heading is not None:

        heading = normalize_heading(
            data.heading
        )

        _cetacean_swim_state[
            "requested_heading"
        ] = heading

        changed["heading"] = heading

    if data.depth is not None:

        _cetacean_swim_state[
            "depth"
        ] = float(data.depth)

        _cetacean_swim_state[
            "follow_ocean_surface"
        ] = False

        _cetacean_swim_state[
            "target_depth_below_surface"
        ] = None

        changed["depth"] = data.depth
    return {
        "ok": True,
        "changed": changed,
        "state": _cetacean_swim_state,
    }

    


@router.post(
    "/scene/cetacean/swim/stop",
    summary="Stop cetacean swimming",
)
async def stop_cetacean_swimming():

    was_running = _cetacean_swim_subscription is not None
    shutdown_cetacean_swimming()

    return {
        "ok": True,
        "was_running": was_running,
    }


def shutdown_cetacean_swimming():
    """Release the live swimming controller during extension shutdown."""

    global _cetacean_swim_subscription
    global _cetacean_swim_state

    _cetacean_swim_subscription = None
    _cetacean_swim_state = None


@router.get(
    "/scene/cetacean/swim/status",
    summary="Get cetacean swimming status",
)
async def cetacean_swimming_status():

    if _cetacean_swim_state is None:
        return {
            "running": False,
        }

    return {
        "running": True,
        **_cetacean_swim_state,
    }
