"""Visual locomotion profiles and deformation math for the gallery.

These values tune an inspection preview.  They are deliberately not exposed
as biological performance data; MARLIN's future biological profiles require
separate literature-backed calibration in physical world units.
"""

import math


GALLERY_MOTION_PROFILES = {
    "bottlenose_dolphin": {
        "family": "delphinid",
        "backend": "procedural_mesh",
        "cadence_hz": 1.15,
        "tail_amplitude_ratio": 0.075,
        "wave_cycles": 0.85,
        "flex_start": 0.34,
    },
    "cuvier_whale": {
        "family": "beaked_whale",
        "backend": "procedural_mesh",
        "cadence_hz": 0.70,
        "tail_amplitude_ratio": 0.070,
        "wave_cycles": 0.78,
        "flex_start": 0.38,
    },
    "frasers_dolphin": {
        "family": "delphinid",
        "backend": "procedural_mesh",
        "cadence_hz": 1.30,
        "tail_amplitude_ratio": 0.080,
        "wave_cycles": 0.90,
        "flex_start": 0.32,
    },
    "humpback_whale": {
        "family": "baleen_whale",
        "backend": "procedural_mesh",
        "cadence_hz": 0.42,
        "tail_amplitude_ratio": 0.090,
        "wave_cycles": 0.68,
        "flex_start": 0.40,
    },
    "manatee": {
        "family": "sirenian",
        "backend": "procedural_mesh",
        "cadence_hz": 0.55,
        "tail_amplitude_ratio": 0.115,
        "wave_cycles": 1.05,
        "flex_start": 0.28,
    },
    "model_61a_-_bottlenose_dolphin": {
        "family": "delphinid",
        "backend": "skeletal",
        "cadence_hz": 24.0 / 30.0,
        "tail_amplitude_ratio": None,
        "wave_cycles": None,
        "flex_start": None,
    },
    "pantropical_spotted_dolphin": {
        "family": "delphinid",
        "backend": "procedural_mesh",
        "cadence_hz": 1.40,
        "tail_amplitude_ratio": 0.078,
        "wave_cycles": 0.92,
        "flex_start": 0.32,
    },
    "pilot_whale": {
        "family": "delphinid",
        "backend": "procedural_mesh",
        "cadence_hz": 0.62,
        "tail_amplitude_ratio": 0.072,
        "wave_cycles": 0.76,
        "flex_start": 0.38,
    },
    "pygmy_sperm_whale": {
        "family": "sperm_whale",
        "backend": "procedural_mesh",
        "cadence_hz": 0.82,
        "tail_amplitude_ratio": 0.070,
        "wave_cycles": 0.80,
        "flex_start": 0.37,
    },
    "sperm_whale": {
        "family": "sperm_whale",
        "backend": "procedural_mesh",
        "cadence_hz": 0.34,
        "tail_amplitude_ratio": 0.082,
        "wave_cycles": 0.66,
        "flex_start": 0.43,
    },
    "steno_dolphin": {
        "family": "delphinid",
        "backend": "procedural_mesh",
        "cadence_hz": 1.22,
        "tail_amplitude_ratio": 0.078,
        "wave_cycles": 0.88,
        "flex_start": 0.33,
    },
}


def tail_flex_envelope(
    tail_fraction: float,
    flex_start: float,
) -> float:
    """Return a smooth 0..1 envelope from rigid torso to flexible fluke."""

    if tail_fraction <= flex_start:
        return 0.0

    span = max(1e-9, 1.0 - flex_start)
    normalized = min(1.0, (tail_fraction - flex_start) / span)
    smooth = normalized * normalized * (3.0 - 2.0 * normalized)
    return smooth * smooth


def vertical_wave_offset(
    tail_fraction: float,
    phase_radians: float,
    *,
    body_length: float,
    amplitude_ratio: float,
    wave_cycles: float,
    flex_start: float,
) -> float:
    """Compute a dorsoventral travelling-wave displacement for one section."""

    envelope = tail_flex_envelope(tail_fraction, flex_start)
    wave_phase = phase_radians - math.tau * wave_cycles * tail_fraction
    return body_length * amplitude_ratio * envelope * math.sin(wave_phase)


def inferred_model_forward_heading(
    longitudinal_axis: int,
    tail_is_high: bool,
) -> float:
    """Infer native nose heading after the gallery's -90 degree X correction."""

    nose_sign = -1.0 if tail_is_high else 1.0
    local = [0.0, 0.0, 0.0]
    local[longitudinal_axis] = nose_sign

    # Rotation of -90 degrees around X: (x, y, z) -> (x, z, -y).
    world_x = local[0]
    world_z = -local[1]

    if abs(world_x) + abs(world_z) <= 1e-9:
        return 0.0

    return math.degrees(math.atan2(world_x, world_z)) % 360.0
