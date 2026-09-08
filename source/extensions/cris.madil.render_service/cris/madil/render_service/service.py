# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from pathlib import Path
from pydantic import BaseModel, Field

import omni.kit.commands
import omni.usd

from .api import router
from . import scene_setup as _scene_setup
from . import cetacean_gallery as _cetacean_gallery
from . import survey_gallery as _survey_gallery
from . import survey_environment as _survey_environment
from . import scene_diagnostics as _scene_diagnostics
from .cetacean import shutdown_cetacean_swimming
from .ocean import shutdown_ocean_animation
from .water_material import RTX_WATER_SETTINGS
from .underwater_cue import UNDERWATER_FOG_SETTING_PATHS


@router.get(
    "/debug/render-settings",
    summary="Inspect RTX water and underwater-cue settings used by MARLIN",
)
async def render_settings_status():
    import carb.settings

    settings = carb.settings.get_settings()
    paths = tuple(RTX_WATER_SETTINGS) + UNDERWATER_FOG_SETTING_PATHS

    return {
        "ok": True,
        "settings": {
            path: settings.get(path)
            for path in paths
        },
    }


class CubeDataModel(BaseModel):
    """Model of a request for generating a cube."""

    asset_write_location: str = Field(
        default="/asset_write_path",
        title="Asset Path",
        description="Location on device to write generated asset",
    )

    asset_name: str = Field(
        default="cube",
        title="Asset Name",
        description="Name of the asset to be generated, .usda will be appended to the name",
    )

    cube_scale: float = Field(
        default=100,
        title="Cube Scale",
        description="Scale of the cube",
    )


@router.post(
    "/generate_cube",
    summary="Generate a cube",
    description="An endpoint to generate a usda file containing a cube of given scale",
)
async def generate_cube(cube_data: CubeDataModel):
    print("[CRIS Render Service] generate_cube was called")

    # Create a new stage
    usd_context = omni.usd.get_context()
    usd_context.new_stage()
    stage = omni.usd.get_context().get_stage()

    # Set the default prim
    default_prim_path = "/World"
    stage.DefinePrim(default_prim_path, "Xform")
    prim = stage.GetPrimAtPath(default_prim_path)
    stage.SetDefaultPrim(prim)

    # Create cube
    prim_type = "Cube"
    prim_path = f"/World/{prim_type}"

    omni.kit.commands.execute(
        "CreatePrim",
        prim_path=prim_path,
        prim_type=prim_type,
        attributes={"size": cube_data.cube_scale},
        select_new_prim=False,
    )

    # save stage
    asset_file_path = str(Path(
        cube_data.asset_write_location).joinpath(f"{cube_data.asset_name}.usda")
    )
    stage.GetRootLayer().Export(asset_file_path)
    msg = f"[CRIS Render Service] Wrote a cube to this path: {asset_file_path}"
    print(msg)
    return msg


# -------------------------------------------------------------------------
# CRIS live-stage API
# -------------------------------------------------------------------------

from pxr import Gf, Sdf, UsdGeom


class LiveCubeDataModel(BaseModel):
    """Request model for creating/updating a cube on the live Kit stage."""

    name: str = Field(
        default="LiveCube",
        title="Cube Name",
        description="USD prim name under /World",
    )

    size: float = Field(
        default=100.0,
        gt=0.0,
        title="Cube Size",
        description="Edge length of the cube",
    )

    position: tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0),
        title="Position",
        description="XYZ translation",
    )

    rotation: tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0),
        title="Rotation",
        description="XYZ rotation in degrees",
    )

    scale: tuple[float, float, float] = Field(
        default=(1.0, 1.0, 1.0),
        title="Scale",
        description="XYZ scale",
    )


@router.post(
    "/scene/cube",
    summary="Create or update a cube on the live stage",
)
async def create_live_cube(data: LiveCubeDataModel):
    """Create or update a cube directly on the currently displayed USD stage."""

    # Ensure the supplied name is a legal USD path component.
    if not Sdf.Path.IsValidIdentifier(data.name):
        return {
            "ok": False,
            "error": f"Invalid USD prim name: {data.name}",
        }

    # Get the stage currently owned/displayed by Kit.
    stage = omni.usd.get_context().get_stage()

    if stage is None:
        return {
            "ok": False,
            "error": "No USD stage is currently open in Kit.",
        }

    # Ensure /World exists.
    UsdGeom.Xform.Define(stage, "/World")

    prim_path = f"/World/{data.name}"

    # Define() creates the cube if necessary and gives us access
    # to it if the prim already exists.
    cube = UsdGeom.Cube.Define(stage, prim_path)
    cube.GetSizeAttr().Set(data.size)

    # Author normal USD transform operations.
    xform = UsdGeom.XformCommonAPI(cube)

    xform.SetTranslate(
        Gf.Vec3d(
            data.position[0],
            data.position[1],
            data.position[2],
        )
    )

    xform.SetRotate(
        Gf.Vec3f(
            data.rotation[0],
            data.rotation[1],
            data.rotation[2],
        ),
        UsdGeom.XformCommonAPI.RotationOrderXYZ,
    )

    xform.SetScale(
        Gf.Vec3f(
            data.scale[0],
            data.scale[1],
            data.scale[2],
        )
    )

    print(
        f"[CRIS Render Service] Live cube updated: "
        f"{prim_path} position={data.position}"
    )

    return {
        "ok": True,
        "prim_path": prim_path,
        "size": data.size,
        "position": data.position,
        "rotation": data.rotation,
        "scale": data.scale,
    }
