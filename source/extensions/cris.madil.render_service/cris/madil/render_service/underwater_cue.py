"""Pure configuration helpers for MARLIN's underwater depth cue."""

from dataclasses import dataclass


UNDERWATER_FOG_SETTING_PATHS = (
    "/rtx/fog/enabled",
    "/rtx/fog/fogColor",
    "/rtx/fog/fogColorIntensity",
    "/rtx/fog/fogZup/enabled",
    "/rtx/fog/fogStartHeight",
    "/rtx/fog/fogHeightDensity",
    "/rtx/fog/fogHeightFalloff",
    "/rtx/fog/fogStartDist",
    "/rtx/fog/fogEndDist",
    "/rtx/fog/fogDistanceDensity",
)

# Extension-scoped state reported by the API. MARLIN startup sets it true;
# an explicit disable request sets it false for the remainder of that run.
UNDERWATER_CUE_REQUESTED_SETTING = (
    "/exts/cris.madil.render_service/underwaterCue/enabled"
)


@dataclass(frozen=True)
class UnderwaterCueParameters:
    """Subtle height fog concentrated beneath the ocean surface."""

    enabled: bool = True
    color: tuple[float, float, float] = (0.03, 0.16, 0.20)
    color_intensity: float = 0.5
    surface_height: float = 0.0
    height_density: float = 0.08
    height_falloff: float = 0.025
    start_distance: float = 0.0
    end_distance: float = 1800.0
    distance_density: float = 0.04


def underwater_fog_settings(data: UnderwaterCueParameters):
    """Translate cue parameters to NVIDIA RTX Simple Fog settings."""

    return {
        "/rtx/fog/enabled": data.enabled,
        "/rtx/fog/fogColor": data.color,
        "/rtx/fog/fogColorIntensity": data.color_intensity,
        # MARLIN uses Y as its vertical axis. RTX Simple Fog uses Y when
        # fogZup is false.
        "/rtx/fog/fogZup/enabled": False,
        "/rtx/fog/fogStartHeight": data.surface_height,
        "/rtx/fog/fogHeightDensity": data.height_density,
        "/rtx/fog/fogHeightFalloff": data.height_falloff,
        "/rtx/fog/fogStartDist": data.start_distance,
        "/rtx/fog/fogEndDist": data.end_distance,
        "/rtx/fog/fogDistanceDensity": data.distance_density,
    }


# MARLIN's built-in underwater look. Extension startup authors these exact
# values so a fresh launch does not depend on a previous API request.
DEFAULT_UNDERWATER_FOG_SETTINGS = underwater_fog_settings(
    UnderwaterCueParameters()
)
