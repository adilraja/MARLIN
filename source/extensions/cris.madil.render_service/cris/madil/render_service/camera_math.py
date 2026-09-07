"""Renderer-independent chase-camera calculations for MARLIN."""

import math


def damping_alpha(responsiveness: float, dt: float) -> float:
    """Return a frame-rate-independent exponential smoothing weight."""

    if responsiveness <= 0.0 or dt <= 0.0:
        return 0.0

    return 1.0 - math.exp(-responsiveness * dt)


def damp_point(
    current: tuple[float, float, float],
    target: tuple[float, float, float],
    responsiveness: float,
    dt: float,
) -> tuple[float, float, float]:
    """Smooth a 3D point toward a target without frame-rate dependence."""

    alpha = damping_alpha(responsiveness, dt)

    return tuple(
        current[index]
        + (target[index] - current[index]) * alpha
        for index in range(3)
    )


def horizontal_distance(
    first: tuple[float, float, float],
    second: tuple[float, float, float],
) -> float:
    """Measure XZ distance so wave height does not trigger camera pursuit."""

    return math.hypot(
        float(second[0]) - float(first[0]),
        float(second[2]) - float(first[2]),
    )


def documentary_camera_transition(
    mode: str,
    mode_elapsed: float,
    horizontal_error: float,
    hold_duration: float,
    dead_zone: float,
    reaction_delay: float,
    settle_distance: float,
    settle_duration: float,
) -> str:
    """Advance the documentary camera's finite-state motion controller."""

    if mode == "HOLD":
        if (
            mode_elapsed >= hold_duration
            and horizontal_error >= dead_zone
        ):
            return "DELAY"
        return mode

    if mode == "DELAY":
        if horizontal_error <= settle_distance:
            return "HOLD"
        if mode_elapsed >= reaction_delay:
            return "CATCH_UP"
        return mode

    if mode == "CATCH_UP":
        if horizontal_error <= settle_distance:
            return "SETTLE"
        return mode

    if mode == "SETTLE":
        if mode_elapsed >= settle_duration:
            return "HOLD"
        return mode

    return "HOLD"


def move_point_with_acceleration(
    current: tuple[float, float, float],
    target: tuple[float, float, float],
    velocity: tuple[float, float, float],
    max_speed: float,
    acceleration: float,
    dt: float,
) -> tuple[
    tuple[float, float, float],
    tuple[float, float, float],
]:
    """Accelerate toward a moving target with braking and no overshoot."""

    if dt <= 0.0:
        return current, velocity

    offset = tuple(
        float(target[index]) - float(current[index])
        for index in range(3)
    )
    distance = math.sqrt(sum(component * component for component in offset))

    if distance <= 1e-8:
        return target, (0.0, 0.0, 0.0)

    direction = tuple(component / distance for component in offset)
    braking_speed = math.sqrt(max(0.0, 2.0 * acceleration * distance))
    desired_speed = min(max_speed, braking_speed)
    desired_velocity = tuple(
        component * desired_speed
        for component in direction
    )

    velocity_change = tuple(
        desired_velocity[index] - float(velocity[index])
        for index in range(3)
    )
    change_length = math.sqrt(
        sum(component * component for component in velocity_change)
    )
    maximum_change = max(0.0, acceleration) * dt

    if change_length > maximum_change and change_length > 1e-8:
        scale = maximum_change / change_length
        velocity_change = tuple(
            component * scale
            for component in velocity_change
        )

    new_velocity = tuple(
        float(velocity[index]) + velocity_change[index]
        for index in range(3)
    )
    step = tuple(component * dt for component in new_velocity)
    step_length = math.sqrt(sum(component * component for component in step))

    if step_length >= distance:
        return target, (0.0, 0.0, 0.0)

    new_position = tuple(
        float(current[index]) + step[index]
        for index in range(3)
    )

    return new_position, new_velocity


def chase_camera_targets(
    target_position: tuple[float, float, float],
    forward: tuple[float, float, float],
    distance: float,
    height: float,
    side_offset: float,
    look_ahead: float,
    look_height: float,
) -> tuple[
    tuple[float, float, float],
    tuple[float, float, float],
]:
    """Compute desired camera and look-at positions around a moving target."""

    forward_x = float(forward[0])
    forward_z = float(forward[2])
    horizontal_length = math.hypot(forward_x, forward_z)

    if horizontal_length <= 1e-8:
        forward_x = 0.0
        forward_z = 1.0
    else:
        forward_x /= horizontal_length
        forward_z /= horizontal_length

    # Right is the horizontal vector perpendicular to forward.
    right_x = forward_z
    right_z = -forward_x

    target_x, target_y, target_z = (
        float(component)
        for component in target_position
    )

    camera_position = (
        target_x - forward_x * distance + right_x * side_offset,
        target_y + height,
        target_z - forward_z * distance + right_z * side_offset,
    )

    look_target = (
        target_x + forward_x * look_ahead,
        target_y + look_height,
        target_z + forward_z * look_ahead,
    )

    return camera_position, look_target
