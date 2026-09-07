"""Pure movement helpers used by MARLIN's live scene controllers."""

import math


def normalize_heading(angle: float) -> float:
    """Normalize a heading to the half-open range [0, 360)."""

    return float(angle) % 360.0


def move_toward(current: float, target: float, max_delta: float) -> float:
    """Move a scalar toward a target without overshooting it."""

    current = float(current)
    target = float(target)
    max_delta = max(0.0, float(max_delta))
    difference = target - current

    if abs(difference) <= max_delta:
        return target
    if difference > 0.0:
        return current + max_delta
    return current - max_delta


def turn_toward(current: float, target: float, max_change: float) -> float:
    """Turn toward a heading using the shortest angular path."""

    current = normalize_heading(current)
    target = normalize_heading(target)
    max_change = max(0.0, float(max_change))
    delta = ((target - current + 180.0) % 360.0) - 180.0

    if abs(delta) <= max_change:
        return target
    if delta > 0.0:
        return normalize_heading(current + max_change)
    return normalize_heading(current - max_change)


def natural_swim_attitude(
    vertical_velocity: float,
    horizontal_speed: float,
    turning_rate: float,
    max_pitch: float,
    max_bank: float,
) -> tuple[float, float]:
    """Return biologically subtle pitch and bank targets in degrees."""

    safe_horizontal_speed = max(float(horizontal_speed), 1.0)
    pitch = -math.degrees(
        math.atan2(float(vertical_velocity), safe_horizontal_speed)
    )
    pitch = max(-max_pitch, min(max_pitch, pitch))

    bank = -float(turning_rate) * 0.35
    bank = max(-max_bank, min(max_bank, bank))

    return pitch, bank
