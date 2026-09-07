"""One-command construction of the complete MARLIN demonstration scene."""

import omni.usd
from pydantic import BaseModel, Field

from .api import router
from .camera import (
    ChaseCameraDataModel,
    start_chase_camera,
    stop_chase_camera,
)
from .cetacean import (
    CetaceanSpawnDataModel,
    CetaceanSwimDataModel,
    spawn_cetacean,
    start_cetacean_swimming,
    stop_cetacean_swimming,
)
from .config import DEFAULT_DOLPHIN_ASSET
from .environment import EnvironmentDataModel, create_environment
from .ocean import (
    OceanAnimationDataModel,
    OceanMaterialDataModel,
    apply_ocean_material,
    start_ocean_animation,
    stop_ocean_animation,
)
from .underwater_api import UnderwaterCueDataModel, apply_underwater_cue

# =========================================================================
# CRIS Complete Marine Scene Setup
# =========================================================================


class MarineSceneSetupDataModel(BaseModel):

    underwater_cue: bool = Field(
        default=True,
        description="Enable subtle height fog below the ocean surface",
    )

    start_swimming: bool = Field(
        default=True,
        description="Start dolphin swimming after constructing the scene",
    )

    start_chase_camera: bool = Field(
        default=True,
        description="Follow the dolphin with a smooth active viewport camera",
    )

    camera_distance: float = Field(default=1200.0, gt=0.0)
    camera_height: float = Field(default=180.0)
    camera_side_offset: float = Field(
        default=650.0,
        description=(
            "Three-quarter documentary framing that keeps the dolphin's "
            "upright body orientation visible"
        ),
    )
    camera_look_ahead: float = Field(default=150.0, ge=0.0)
    camera_responsiveness: float = Field(default=3.0, gt=0.0)
    camera_focal_length: float = Field(default=35.0, gt=0.0)

    dolphin_name: str = Field(
        default="Dolphin_001",
    )

    dolphin_asset: str = Field(default=DEFAULT_DOLPHIN_ASSET)

    dolphin_position: tuple[float, float, float] = Field(
        default=(0.0, -20.0, 0.0),
    )

    dolphin_rotation: tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0),
        description="World-space rotation; asset correction is applied separately",
    )

    dolphin_scale: float = Field(
        default=100.0,
        gt=0.0,
    )

    dolphin_speed: float = Field(
        default=5.0,
        ge=0.0,
    )

    dolphin_heading: float = Field(
        default=0.0,
    )

    dolphin_depth: float = Field(
        default=-20.0,
    )
    dolphin_depth_below_surface: float = Field(
        default=20.0,
        ge=0.0,
    )


@router.post(
    "/scene/marine/setup",
    summary="Create the complete MARLIN marine demonstration scene",
)
async def setup_marine_scene(
    data: MarineSceneSetupDataModel,
):

    results = {}

    # ---------------------------------------------------------------
    # 1. Stop existing live controllers
    # ---------------------------------------------------------------

    try:
        await stop_cetacean_swimming()
    except Exception as exc:
        print(
            "[CRIS Marine Setup] "
            f"CETACEAN stop warning: {exc}"
        )

    try:
        await stop_chase_camera()
    except Exception as exc:
        print(
            "[CRIS Marine Setup] "
            f"CAMERA stop warning: {exc}"
        )

    try:
        await stop_ocean_animation()
    except Exception as exc:
        print(
            "[CRIS Marine Setup] "
            f"OCEAN stop warning: {exc}"
        )

    # ---------------------------------------------------------------
    # 2. Start animated ocean
    # ---------------------------------------------------------------

    ocean_data = OceanAnimationDataModel(
        name="Ocean",
        size=16000.0,
        resolution=128,
        wave_height=40.0,
        wave_length=650.0,
        choppiness=0.55,
        speed=0.7,
        target_fps=15.0,
        position=(0.0, 0.0, 0.0),
    )

    ocean_result = await start_ocean_animation(
        ocean_data
    )

    results["ocean"] = ocean_result

    if not ocean_result.get("ok", False):
        return {
            "ok": False,
            "step": "ocean",
            "results": results,
        }

    # ---------------------------------------------------------------
    # 3. Ocean material
    # ---------------------------------------------------------------

    material_data = OceanMaterialDataModel(
        ocean_name="Ocean",
        material_name="OceanWater",
        roughness=0.045,
        ior=1.333,
        transmission=1.0,
        base_weight=0.02,
        base_color=(0.02, 0.10, 0.13),
        transmission_color=(0.78, 0.92, 0.95),
        transmission_depth=100.0,
        scattering_color=(0.005, 0.02, 0.03),
        scattering_anisotropy=0.0,
        thin_walled=True,
    )

    material_result = await apply_ocean_material(
        material_data
    )

    results["material"] = material_result

    if not material_result.get("ok", False):
        return {
            "ok": False,
            "step": "material",
            "results": results,
        }

    # ---------------------------------------------------------------
    # 4. Sky + sun
    # ---------------------------------------------------------------

    environment_data = EnvironmentDataModel(
        sky_intensity=500.0,
        sky_exposure=1.0,
        sky_color=(0.45, 0.65, 1.0),

        sun_intensity=5000.0,
        sun_angle=0.53,
        sun_rotation=(-35.0, 25.0, 0.0),
        sun_color=(1.0, 0.92, 0.78),
    )

    environment_result = await create_environment(
        environment_data
    )

    results["environment"] = environment_result

    if not environment_result.get("ok", False):
        return {
            "ok": False,
            "step": "environment",
            "results": results,
        }

    # ---------------------------------------------------------------
    # 5. Subtle underwater depth cue
    # ---------------------------------------------------------------

    cue_data = UnderwaterCueDataModel(
        enabled=data.underwater_cue,
        surface_height=ocean_data.position[1],
    )

    cue_result = await apply_underwater_cue(cue_data)
    results["underwater_cue"] = cue_result

    if not cue_result.get("ok", False):
        return {
            "ok": False,
            "step": "underwater_cue",
            "results": results,
        }

    # ---------------------------------------------------------------
    # 6. Spawn real dolphin USD
    # ---------------------------------------------------------------

    dolphin_data = CetaceanSpawnDataModel(
        name=data.dolphin_name,
        asset_path=data.dolphin_asset,
        position=data.dolphin_position,
        rotation=data.dolphin_rotation,
        scale=data.dolphin_scale,
    )

    dolphin_result = await spawn_cetacean(
        dolphin_data
    )

    results["dolphin"] = dolphin_result

    if not dolphin_result.get("ok", False):
        return {
            "ok": False,
            "step": "dolphin",
            "results": results,
        }

    # ---------------------------------------------------------------
    # 7. Optional bounded swimming
    # ---------------------------------------------------------------

    if data.start_swimming:

        swim_data = CetaceanSwimDataModel(
        name=data.dolphin_name,

        speed=data.dolphin_speed,
        heading=data.dolphin_heading,

        depth=data.dolphin_depth,

        follow_ocean_surface=True,

        depth_below_surface=data.dolphin_depth_below_surface,

        vertical_follow_rate=40.0,

        world_half_extent=7500.0,
        turn_margin=1000.0,
        turn_rate=30.0,
    )

        swim_result = await start_cetacean_swimming(
            swim_data
        )

        results["swimming"] = swim_result

        if not swim_result.get("ok", False):
            return {
                "ok": False,
                "step": "swimming",
                "results": results,
            }

    else:
        results["swimming"] = {
            "ok": True,
            "started": False,
        }

    # ---------------------------------------------------------------
    # 8. Optional smooth chase camera
    # ---------------------------------------------------------------

    if data.start_chase_camera:
        camera_data = ChaseCameraDataModel(
            target_name=data.dolphin_name,
            distance=data.camera_distance,
            height=data.camera_height,
            side_offset=data.camera_side_offset,
            look_ahead=data.camera_look_ahead,
            responsiveness=data.camera_responsiveness,
            focal_length=data.camera_focal_length,
            activate_viewport=True,
        )

        camera_result = await start_chase_camera(camera_data)
        results["camera"] = camera_result

        if not camera_result.get("ok", False):
            return {
                "ok": False,
                "step": "camera",
                "results": results,
            }
    else:
        results["camera"] = {
            "ok": True,
            "started": False,
        }

    # Kit draws selected prims with a bright orange/yellow outline. The
    # procedurally generated ocean is often left selected while the scene is
    # being assembled, making its boundary look like part of the material.
    # Clear the authoring selection once setup is complete so the viewport is
    # a clean camera view.
    try:
        omni.usd.get_context().get_selection().set_selected_prim_paths(
            [],
            False,
        )
    except Exception as exc:
        print(
            "[CRIS Marine Setup] "
            f"SELECTION clear warning: {exc}"
        )

    print(
        "[CRIS Marine Setup] "
        "Complete MARLIN marine scene created."
    )

    return {
        "ok": True,
        "message": "MARLIN marine scene created.",
        "results": results,
    }
