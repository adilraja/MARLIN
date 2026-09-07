"""Sky and sunlight HTTP endpoints for MARLIN."""

import os

import omni.usd
from pydantic import BaseModel, Field
from pxr import Gf, Sdf, UsdGeom, UsdLux

from .api import router

# =========================================================================
# CRIS Natural Environment: Sky + Sun
# =========================================================================



class TexturedEnvironmentDataModel(BaseModel):
    """Create a sky/environment and directional sun on the live stage."""

    sky_texture: str | None = Field(
        default=None,
        description=(
            "Optional absolute path to an HDR/EXR environment image. "
            "If omitted, the DomeLight uses a constant sky colour."
        ),
    )

    sky_intensity: float = Field(
        default=500.0,
        ge=0.0,
        description="Intensity of the sky DomeLight",
    )

    sky_exposure: float = Field(
        default=0.0,
        description="Exposure adjustment for the sky DomeLight",
    )

    sky_color: tuple[float, float, float] = Field(
        default=(0.45, 0.65, 1.0),
        description="Sky colour when no HDRI texture is supplied",
    )

    sky_rotation: float = Field(
        default=0.0,
        description="Rotation of the environment around the vertical axis",
    )

    sun_intensity: float = Field(
        default=3000.0,
        ge=0.0,
        description="Intensity of the directional sunlight",
    )

    sun_angle: float = Field(
        default=0.53,
        ge=0.0,
        description="Angular diameter of the sun in degrees",
    )

    sun_rotation: tuple[float, float, float] = Field(
        default=(-35.0, 25.0, 0.0),
        description="XYZ rotation of the sun in degrees",
    )

    sun_color: tuple[float, float, float] = Field(
        default=(1.0, 0.92, 0.78),
        description="RGB colour of the sunlight",
    )


@router.post(
    "/scene/environment/texture",
    summary="Create a textured natural sky and sun environment",
)
async def create_textured_environment(data: TexturedEnvironmentDataModel):

    stage = omni.usd.get_context().get_stage()

    if stage is None:
        return {
            "ok": False,
            "error": "No USD stage is currently open in Kit.",
        }

    UsdGeom.Xform.Define(stage, "/World")

    environment_path = "/World/Environment"

    # Replacing the environment makes repeated HTTP requests predictable.
    if stage.GetPrimAtPath(environment_path):
        stage.RemovePrim(environment_path)

    UsdGeom.Xform.Define(stage, environment_path)

    # ------------------------------------------------------------------
    # SKY / ENVIRONMENT
    # ------------------------------------------------------------------

    sky_path = f"{environment_path}/Sky"

    sky = UsdLux.DomeLight.Define(
        stage,
        sky_path,
    )

    sky.CreateIntensityAttr().Set(
        data.sky_intensity
    )

    sky.CreateExposureAttr().Set(
        data.sky_exposure
    )

    sky.CreateColorAttr().Set(
        Gf.Vec3f(*data.sky_color)
    )

    # Make the dome orientation conform to the stage up axis.
    sky.OrientToStageUpAxis()

    sky_texture_used = None

    if data.sky_texture:

        sky_texture = os.path.abspath(
            os.path.expanduser(data.sky_texture)
        )

        if not os.path.isfile(sky_texture):
            return {
                "ok": False,
                "error": f"Sky texture does not exist: {sky_texture}",
            }

        sky.CreateTextureFileAttr().Set(
            Sdf.AssetPath(sky_texture)
        )

        # Most HDRI skies use latitude/longitude mapping.
        sky.CreateTextureFormatAttr().Set(
            UsdLux.Tokens.latlong
        )

        sky_texture_used = sky_texture

    # Rotate the environment around Y.
    sky_xform = UsdGeom.XformCommonAPI(
        sky.GetPrim()
    )

    sky_xform.SetRotate(
        Gf.Vec3f(
            0.0,
            data.sky_rotation,
            0.0,
        ),
        UsdGeom.XformCommonAPI.RotationOrderXYZ,
    )

    # ------------------------------------------------------------------
    # SUN
    # ------------------------------------------------------------------

    sun_path = f"{environment_path}/Sun"

    sun = UsdLux.DistantLight.Define(
        stage,
        sun_path,
    )

    sun.CreateIntensityAttr().Set(
        data.sun_intensity
    )

    sun.CreateAngleAttr().Set(
        data.sun_angle
    )

    sun.CreateColorAttr().Set(
        Gf.Vec3f(*data.sun_color)
    )

    sun_xform = UsdGeom.XformCommonAPI(
        sun.GetPrim()
    )

    sun_xform.SetRotate(
        Gf.Vec3f(
            data.sun_rotation[0],
            data.sun_rotation[1],
            data.sun_rotation[2],
        ),
        UsdGeom.XformCommonAPI.RotationOrderXYZ,
    )

    print(
        "[CRIS Render Service] Natural environment created: "
        f"Sky={sky_path}, Sun={sun_path}"
    )

    return {
        "ok": True,
        "environment_path": environment_path,
        "sky_path": sky_path,
        "sun_path": sun_path,
        "sky_texture": sky_texture_used,
        "sky_intensity": data.sky_intensity,
        "sky_exposure": data.sky_exposure,
        "sun_intensity": data.sun_intensity,
        "sun_angle": data.sun_angle,
        "sun_rotation": data.sun_rotation,
    }


# =========================================================================
# CRIS Environment: procedural sky illumination + sun
# =========================================================================

from pxr import UsdLux


class EnvironmentDataModel(BaseModel):
    sky_intensity: float = Field(
        default=500.0,
        ge=0.0,
        description="Brightness of the ambient sky light",
    )

    sky_exposure: float = Field(
        default=1.0,
        description="Exposure adjustment for the sky light",
    )

    sky_color: tuple[float, float, float] = Field(
        default=(0.35, 0.55, 0.90),
        description="RGB colour of the sky illumination",
    )

    sun_intensity: float = Field(
        default=5000.0,
        ge=0.0,
        description="Brightness of the directional sun",
    )

    sun_angle: float = Field(
        default=0.53,
        ge=0.0,
        description="Angular diameter of the sun in degrees",
    )

    sun_rotation: tuple[float, float, float] = Field(
        default=(-35.0, 25.0, 0.0),
        description="XYZ rotation of the sun in degrees",
    )

    sun_color: tuple[float, float, float] = Field(
        default=(1.0, 0.92, 0.78),
        description="RGB colour of the sunlight",
    )


@router.post(
    "/scene/environment",
    summary="Create a procedural sky light and sun",
)
async def create_environment(data: EnvironmentDataModel):

    stage = omni.usd.get_context().get_stage()

    if stage is None:
        return {
            "ok": False,
            "error": "No live USD stage is currently open.",
        }

    UsdGeom.Xform.Define(stage, "/World")

    environment_path = "/World/Environment"

    if stage.GetPrimAtPath(environment_path):
        stage.RemovePrim(environment_path)

    UsdGeom.Xform.Define(stage, environment_path)

    # ---------------------------------------------------------------
    # Ambient sky illumination
    # ---------------------------------------------------------------

    sky_path = f"{environment_path}/Sky"

    sky = UsdLux.DomeLight.Define(
        stage,
        sky_path,
    )

    sky.CreateIntensityAttr().Set(
        data.sky_intensity
    )

    sky.CreateExposureAttr().Set(
        data.sky_exposure
    )

    sky.CreateColorAttr().Set(
        Gf.Vec3f(*data.sky_color)
    )

    sky.OrientToStageUpAxis()

    # ---------------------------------------------------------------
    # Directional sunlight
    # ---------------------------------------------------------------

    sun_path = f"{environment_path}/Sun"

    sun = UsdLux.DistantLight.Define(
        stage,
        sun_path,
    )

    sun.CreateIntensityAttr().Set(
        data.sun_intensity
    )

    sun.CreateAngleAttr().Set(
        data.sun_angle
    )

    sun.CreateColorAttr().Set(
        Gf.Vec3f(*data.sun_color)
    )

    sun_xform = UsdGeom.XformCommonAPI(
        sun.GetPrim()
    )

    sun_xform.SetRotate(
        Gf.Vec3f(*data.sun_rotation),
        UsdGeom.XformCommonAPI.RotationOrderXYZ,
    )

    print(
        "[CRIS Render Service] Environment created: "
        f"{sky_path}, {sun_path}"
    )

    return {
        "ok": True,
        "environment_path": environment_path,
        "sky_path": sky_path,
        "sun_path": sun_path,
        "sky_intensity": data.sky_intensity,
        "sun_intensity": data.sun_intensity,
        "sun_rotation": data.sun_rotation,
    }
