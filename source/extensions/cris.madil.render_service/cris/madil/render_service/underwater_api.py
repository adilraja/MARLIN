"""HTTP controls for MARLIN's renderer-level underwater depth cue."""

import carb.settings
from pydantic import BaseModel, Field

from .api import router
from .underwater_cue import (
    UNDERWATER_CUE_REQUESTED_SETTING,
    UNDERWATER_FOG_SETTING_PATHS,
    UnderwaterCueParameters,
    underwater_fog_settings,
)


class UnderwaterCueDataModel(BaseModel):
    """Configurable RTX height fog used to make submersion readable."""

    enabled: bool = Field(default=True)
    color: tuple[float, float, float] = Field(
        default=(0.03, 0.16, 0.20),
        description="Fog colour below the waterline",
    )
    color_intensity: float = Field(default=0.5, ge=0.0)
    surface_height: float = Field(
        default=0.0,
        description="Ocean waterline on MARLIN's vertical Y axis",
    )
    height_density: float = Field(default=0.08, ge=0.0)
    height_falloff: float = Field(default=0.025, ge=0.0)
    start_distance: float = Field(default=0.0, ge=0.0)
    end_distance: float = Field(default=1800.0, gt=0.0)
    distance_density: float = Field(default=0.04, ge=0.0)


def _parameters_from_model(data: UnderwaterCueDataModel):
    return UnderwaterCueParameters(
        enabled=data.enabled,
        color=data.color,
        color_intensity=data.color_intensity,
        surface_height=data.surface_height,
        height_density=data.height_density,
        height_falloff=data.height_falloff,
        start_distance=data.start_distance,
        end_distance=data.end_distance,
        distance_density=data.distance_density,
    )


def _serializable_setting(value):
    """Convert renderer vector values to ordinary JSON-compatible values."""

    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    try:
        return [float(value[index]) for index in range(3)]
    except (IndexError, TypeError, ValueError):
        return str(value)


@router.post(
    "/scene/ocean/underwater-cue",
    summary="Configure the subtle underwater depth cue",
)
async def apply_underwater_cue(data: UnderwaterCueDataModel):
    parameters = _parameters_from_model(data)
    applied = underwater_fog_settings(parameters)
    settings = carb.settings.get_settings()

    for path, value in applied.items():
        settings.set(path, value)

    settings.set(UNDERWATER_CUE_REQUESTED_SETTING, data.enabled)

    return {
        "ok": True,
        "enabled": data.enabled,
        "surface_height": data.surface_height,
        "settings": applied,
    }


@router.get(
    "/scene/ocean/underwater-cue/status",
    summary="Inspect the current underwater depth cue",
)
async def underwater_cue_status():
    settings = carb.settings.get_settings()

    return {
        "ok": True,
        "enabled": bool(settings.get("/rtx/fog/enabled")),
        "requested_enabled": bool(
            settings.get(UNDERWATER_CUE_REQUESTED_SETTING)
        ),
        "settings": {
            path: _serializable_setting(settings.get(path))
            for path in UNDERWATER_FOG_SETTING_PATHS
        },
    }


@router.post(
    "/scene/ocean/underwater-cue/disable",
    summary="Disable the underwater depth cue",
)
async def disable_underwater_cue():
    carb.settings.get_settings().set(
        UNDERWATER_CUE_REQUESTED_SETTING,
        False,
    )
    shutdown_underwater_cue()
    return {"ok": True, "enabled": False}


def shutdown_underwater_cue():
    """Temporarily remove the global renderer cue during service shutdown."""

    carb.settings.get_settings().set("/rtx/fog/enabled", False)
