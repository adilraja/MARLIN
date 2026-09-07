"""Renderer-facing parameter model for MARLIN's OmniSurface seawater."""

from dataclasses import dataclass


RTX_WATER_SETTINGS = {
    "/rtx/translucency/enabled": True,
    "/rtx/translucency/maxRefractionBounces": 8,
    "/rtx/pathtracing/maxBounces": 16,
    "/rtx/pathtracing/maxSpecularAndTransmissionBounces": 16,
    "/rtx/rtpt/maxBounces": 8,
    "/rtx/rtpt/maxSpecularAndTransmissionBounces": 8,
}


@dataclass(frozen=True)
class OmniSurfaceWaterParameters:
    ocean_name: str = "Ocean"
    material_name: str = "OceanWater"
    ior: float = 1.333
    roughness: float = 0.045
    transmission: float = 1.0
    base_weight: float = 0.02
    base_color: tuple[float, float, float] = (0.02, 0.10, 0.13)
    transmission_color: tuple[float, float, float] = (0.78, 0.92, 0.95)
    transmission_depth: float = 100.0
    scattering_color: tuple[float, float, float] = (0.005, 0.02, 0.03)
    scattering_anisotropy: float = 0.0
    thin_walled: bool = True


def omnisurface_inputs(data: OmniSurfaceWaterParameters):
    """Return OmniSurface input names, USD value kinds, and authored values."""

    return {
        "diffuse_reflection_weight": ("float", data.base_weight),
        "diffuse_reflection_color": ("color3f", data.base_color),
        "metalness": ("float", 0.0),
        "specular_reflection_weight": ("float", 1.0),
        "specular_reflection_color": ("color3f", (1.0, 1.0, 1.0)),
        "specular_reflection_roughness": ("float", data.roughness),
        "specular_reflection_ior": ("float", data.ior),
        "enable_specular_transmission": ("bool", True),
        "specular_transmission_weight": ("float", data.transmission),
        "specular_transmission_color": ("color3f", data.transmission_color),
        "specular_transmission_scattering_depth": (
            "float",
            data.transmission_depth,
        ),
        "specular_transmission_scattering_color": (
            "color3f",
            data.scattering_color,
        ),
        "specular_transmission_scatter_anisotropy": (
            "float",
            data.scattering_anisotropy,
        ),
        "thin_walled": ("bool", data.thin_walled),
    }
