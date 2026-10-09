"""Measure the pinned engineering porpoise model, without biological approval.

``metrics(states, config)`` accepts a complete retained v2 trajectory and the
existing model configuration. Structurally invalid exchange states raise
ValueError; valid states that violate the declared model return ``passed=False``.

``compare_seed_variation(runs, config)`` accepts a list of dictionaries with
``states`` and ``validation.initial_phase_deg``. Extra execution metadata is
allowed. Supply the ten distinct primary seed runs, not their repeat executions.
This checks actual geometric variation and that phase is its only effect.
No HTTP, GAMA execution, USD access, plots or scene mutation occurs here.
"""
import math

import gama_porpoise as runner

TURN_RATE_TOLERANCE_DEG_PER_S = 1e-7


def circular_delta(left, right):
    """Signed angular displacement from left to right, in [-180, 180)."""
    return (right - left + 180.0) % 360.0 - 180.0


def _summary(values):
    return {"min": min(values), "max": max(values),
            "mean": math.fsum(values) / len(values)}


def _validated(states):
    if not isinstance(states, list) or len(states) < 2:
        raise ValueError("A trajectory must contain at least two v2 states")
    buffer = runner.exchange.StepBuffer()
    detached = []
    for state in states:
        result = buffer.accept(state)
        if result["duplicate"]:
            raise ValueError("A recorded trajectory must not contain duplicate states")
        detached.append(buffer.latest)
    return detached


def metrics(states, config):
    """Return interval-weighted measurements and declared-model acceptance checks.

    Labels describe intervals beginning at each sample. The final sample adds
    no exposure. The final episode is right-censored by the observation window;
    the FSM has no exit from its final surface state. Finite differences are
    sampled secants, and are not presented as continuous derivative peaks.
    """
    expected_count = runner.validate_config(config)
    states = _validated(states)
    p, configured_tolerance = config["parameters"], config["tolerances"]
    dt = p["step"]
    tolerance = {**configured_tolerance,
                 "turn_rate_deg_per_s": TURN_RATE_TOLERANCE_DEG_PER_S,
                 "horizontal_chord_speed_mps": 2 * configured_tolerance["position_m"] / dt,
                 "depth_secant_mps": 2 * configured_tolerance["depth_m"] / dt,
                 "three_dimensional_chord_speed_mps": 2 * (configured_tolerance["position_m"] + configured_tolerance["depth_m"]) / dt}
    agents = [s["agents"][0] for s in states]
    times = [s["simulation_time_s"] for s in states]
    depths = [a["depth_m"] for a in agents]
    positions = [a["horizontal_position_m"] for a in agents]
    phase = math.atan2(positions[0][0], positions[0][1])
    angular_speed = p["horizontal_speed_mps"] / p["path_radius_m"]
    expected_turn = math.degrees(angular_speed)
    expected_chord_speed = 2 * p["path_radius_m"] * math.sin(angular_speed * dt / 2) / dt
    expected_depths, expected_labels = [], []
    errors = {name: 0.0 for name in ("clock_s", "step_s", "position_m", "radius_m", "heading_deg", "depth_m", "exported_speed_mps",
                                            "horizontal_chord_speed_mps", "turn_rate_deg_per_s", "depth_secant_mps", "three_dimensional_chord_speed_mps", "episode_duration_s")}
    for i, (state, agent) in enumerate(zip(states, agents)):
        expected_time = i * dt
        label, depth = runner.expected_vertical(expected_time, p)
        expected_depths.append(depth)
        expected_labels.append(label)
        x, z = positions[i]
        angle = phase + angular_speed * expected_time
        expected_x, expected_z = p["path_radius_m"] * math.sin(angle), p["path_radius_m"] * math.cos(angle)
        errors["clock_s"] = max(errors["clock_s"], abs(times[i] - expected_time))
        errors["step_s"] = max(errors["step_s"], abs(state["simulation_step_s"] - dt))
        errors["position_m"] = max(errors["position_m"], math.hypot(x - expected_x, z - expected_z))
        errors["radius_m"] = max(errors["radius_m"], abs(math.hypot(x, z) - p["path_radius_m"]))
        errors["heading_deg"] = max(errors["heading_deg"], abs(circular_delta(math.degrees(angle) + 90, agent["heading_deg"])))
        errors["depth_m"] = max(errors["depth_m"], abs(depths[i] - depth))
        errors["exported_speed_mps"] = max(errors["exported_speed_mps"], abs(agent["speed_mps"] - p["horizontal_speed_mps"]))

    episodes, coverage, intervals, transitions = [], {}, [], []
    for i, agent in enumerate(agents):
        label = agent["behavioural_state"]
        if not transitions or transitions[-1]["state"] != label:
            transitions.append({"state": label, "step_index": states[i]["step_index"], "simulation_time_s": times[i]})
        if not episodes or episodes[-1]["state"] != label:
            if episodes:
                episodes[-1]["end_s"] = times[i]
                episodes[-1]["duration_s"] = times[i] - episodes[-1]["start_s"]
            episodes.append({"state": label, "start_s": times[i], "end_s": times[i], "duration_s": 0.0, "right_censored": False})
        if i == len(states) - 1:
            continue
        span = times[i + 1] - times[i]
        chord = math.hypot(positions[i + 1][0] - positions[i][0], positions[i + 1][1] - positions[i][1])
        depth_delta = depths[i + 1] - depths[i]
        chord_speed = chord / span
        turn = circular_delta(agent["heading_deg"], agents[i + 1]["heading_deg"]) / span
        depth_rate = depth_delta / span
        speed_3d = math.hypot(chord, depth_delta) / span
        expected_depth_rate = (expected_depths[i + 1] - expected_depths[i]) / dt
        errors["horizontal_chord_speed_mps"] = max(errors["horizontal_chord_speed_mps"], abs(chord_speed - expected_chord_speed))
        errors["turn_rate_deg_per_s"] = max(errors["turn_rate_deg_per_s"], abs(turn - expected_turn))
        errors["depth_secant_mps"] = max(errors["depth_secant_mps"], abs(depth_rate - expected_depth_rate))
        errors["three_dimensional_chord_speed_mps"] = max(errors["three_dimensional_chord_speed_mps"], abs(speed_3d - math.hypot(expected_chord_speed, expected_depth_rate)))
        coverage[label] = coverage.get(label, 0.0) + span
        intervals.append({"start_s": times[i], "end_s": times[i + 1], "state": label,
                          "horizontal_chord_speed_mps": chord_speed, "turn_rate_deg_per_s": turn,
                          "depth_secant_mps": depth_rate, "three_dimensional_chord_speed_mps": speed_3d})
    episodes[-1].update(end_s=times[-1], duration_s=times[-1] - episodes[-1]["start_s"], right_censored=True)
    expected_episodes = list(zip(("surface", "shallow_swim", "descent", "submerged_swim", "ascent", "surface"), (p[name] for name in runner.DURATIONS)))
    schedule_matches = len(episodes) == len(expected_episodes)
    if schedule_matches:
        start = 0.0
        for episode, (label, duration) in zip(episodes, expected_episodes):
            schedule_matches = schedule_matches and episode["state"] == label
            errors["episode_duration_s"] = max(errors["episode_duration_s"], abs(episode["duration_s"] - duration), abs(episode["start_s"] - start))
            start += duration
    else:
        # A finite explicit error accompanies the separate failed count check.
        errors["episode_duration_s"] = abs(len(episodes) - len(expected_episodes)) * dt
    checks = {"complete_sample_count": len(states) == expected_count,
              "contiguous_indices_from_zero": all(s["step_index"] == i for i, s in enumerate(states)),
              "clock_and_step": errors["clock_s"] <= tolerance["clock_s"] and errors["step_s"] <= tolerance["clock_s"],
              "unaliased_turn_sampling": angular_speed * dt < math.pi,
              "declared_state_labels": [a["behavioural_state"] for a in agents] == expected_labels,
              "declared_episodes_and_durations": schedule_matches and errors["episode_duration_s"] <= tolerance["clock_s"],
              "circle_and_phase": max(errors["position_m"], errors["radius_m"]) <= tolerance["position_m"],
              "tangent_heading": errors["heading_deg"] <= tolerance["heading_deg"],
              "declared_depth_evolution": errors["depth_m"] <= tolerance["depth_m"],
              "exported_horizontal_speed": errors["exported_speed_mps"] <= tolerance["speed_mps"]}
    for name in ("horizontal_chord_speed_mps", "turn_rate_deg_per_s", "depth_secant_mps", "three_dimensional_chord_speed_mps"):
        checks[name] = errors[name] <= tolerance[name]
    expected_exposure = sum(p[name] for name in runner.DURATIONS)
    checks["observation_window"] = abs(times[0]) <= tolerance["clock_s"] and abs(times[-1] - expected_exposure) <= tolerance["clock_s"]
    return {"passed": all(checks.values()), "biological_approval": False, "samples": len(states),
            "checks": checks, "maximum_errors": errors, "tolerances": tolerance,
            "observation_window": {"start_s": times[0], "end_s": times[-1], "duration_s": times[-1] - times[0],
                                   "interval_convention": "[start,end); final sample has zero exposure"},
            "episodes": episodes, "coverage_s": coverage, "transitions": transitions,
            "depth_range_m": [min(depths), max(depths)],
            "exported_speed_mps": _summary([a["speed_mps"] for a in agents]),
            **{name: _summary([row[name] for row in intervals]) for name in ("horizontal_chord_speed_mps", "turn_rate_deg_per_s", "depth_secant_mps", "three_dimensional_chord_speed_mps")},
            "horizontal_polyline_length_m": math.fsum(row["horizontal_chord_speed_mps"] * (row["end_s"] - row["start_s"]) for row in intervals),
            "declared_continuous_horizontal_length_m": p["horizontal_speed_mps"] * expected_exposure,
            "expected_horizontal_chord_speed_mps": expected_chord_speed,
            "expected_turn_rate_deg_per_s": expected_turn,
            "continuous_vertical_peak_mps": {"shallow_swim": 1.5 * (p["shallow_depth_m"] - p["surface_depth_m"]) / p["shallow_swim_s"],
                                             "descent": 1.5 * (p["submerged_depth_m"] - p["shallow_depth_m"]) / p["descent_s"],
                                             "ascent": -1.5 * (p["submerged_depth_m"] - p["surface_depth_m"]) / p["ascent_s"]},
            "interval_series": intervals}


def compare_seed_variation(runs, config):
    """Verify distinct initial phases/poses and phase-only stochastic variation.

    De-rotate x/z and heading by each engine-exported phase. Scientific fields
    other than run identity, seed, x/z and heading must remain identical. The
    seed is deliberately excluded only from this cross-seed invariant check;
    same-seed reproducibility must retain it in its separate canonical comparison.
    """
    runner.validate_config(config)
    if not isinstance(runs, list) or len(runs) < 2:
        raise ValueError("Variation comparison requires at least two primary seed runs")
    tolerance = {**config["tolerances"], "turn_rate_deg_per_s": TURN_RATE_TOLERANCE_DEG_PER_S}
    checked, phases, first_poses, seeds, per_run_passed = [], [], [], [], []
    for run in runs:
        if not isinstance(run, dict) or "states" not in run or not isinstance(run.get("validation"), dict):
            raise ValueError("Each run needs states and validation.initial_phase_deg")
        phase = run["validation"].get("initial_phase_deg")
        if type(phase) not in (int, float) or not math.isfinite(phase) or not 0 <= phase < 360:
            raise ValueError("Exported initial phase must be finite in [0,360)")
        states = _validated(run["states"])
        checked.append(states)
        phases.append(phase)
        seeds.append(states[0]["seed"])
        first_poses.append(states[0]["agents"][0]["horizontal_position_m"])
        per_run_passed.append(metrics(states, config)["passed"])
    phases_distinct = all(abs(circular_delta(phases[i], phases[j])) > tolerance["heading_deg"] for i in range(len(phases)) for j in range(i))
    first_poses_distinct = all(math.dist(first_poses[i], first_poses[j]) > tolerance["position_m"] for i in range(len(phases)) for j in range(i))
    errors = {"derotated_position_m": 0.0, "derotated_heading_deg": 0.0,
              "initial_phase_heading_deg": 0.0, "clock_s": 0.0, "depth_m": 0.0, "speed_mps": 0.0}
    equal_invariants = True
    equal_lengths = all(len(s) == len(checked[0]) for s in checked)

    def normalized(state, phase):
        x, z = state["agents"][0]["horizontal_position_m"]
        angle = math.radians(phase)
        return (x * math.cos(angle) - z * math.sin(angle), x * math.sin(angle) + z * math.cos(angle)), (state["agents"][0]["heading_deg"] - phase) % 360

    for states, phase in zip(checked, phases):
        x, z = states[0]["agents"][0]["horizontal_position_m"]
        errors["initial_phase_heading_deg"] = max(errors["initial_phase_heading_deg"], abs(circular_delta(phase, math.degrees(math.atan2(x, z)))))
        for reference, state in zip(checked[0], states):
            a, b = reference["agents"][0], state["agents"][0]
            expected_pos, expected_heading = normalized(reference, phases[0])
            pos, heading = normalized(state, phase)
            errors["derotated_position_m"] = max(errors["derotated_position_m"], math.dist(expected_pos, pos))
            errors["derotated_heading_deg"] = max(errors["derotated_heading_deg"], abs(circular_delta(expected_heading, heading)))
            errors["clock_s"] = max(errors["clock_s"], abs(reference["simulation_time_s"] - state["simulation_time_s"]), abs(reference["simulation_step_s"] - state["simulation_step_s"]))
            errors["depth_m"] = max(errors["depth_m"], abs(a["depth_m"] - b["depth_m"]))
            errors["speed_mps"] = max(errors["speed_mps"], abs(a["speed_mps"] - b["speed_mps"]))
            equal_invariants = equal_invariants and all(reference[name] == state[name] for name in ("schema_version", "step_index"))
            equal_invariants = equal_invariants and all(a[name] == b[name] for name in ("agent_id", "species", "behavioural_state", "vertical_reference"))
    checks = {"distinct_primary_seeds": len(set(seeds)) == len(seeds),
              "all_runs_meet_model_constraints": all(per_run_passed),
              "distinct_initial_phases": phases_distinct, "distinct_initial_positions": first_poses_distinct,
              "equal_sample_counts": equal_lengths, "equal_discrete_invariants": equal_invariants,
              "phase_matches_first_position": errors["initial_phase_heading_deg"] <= tolerance["heading_deg"],
              "phase_only_position_variation": errors["derotated_position_m"] <= tolerance["position_m"],
              "phase_only_heading_variation": errors["derotated_heading_deg"] <= tolerance["heading_deg"],
              "equal_clocks": errors["clock_s"] <= tolerance["clock_s"],
              "equal_depth_evolution": errors["depth_m"] <= tolerance["depth_m"],
              "equal_exported_speeds": errors["speed_mps"] <= tolerance["speed_mps"]}
    return {"passed": all(checks.values()), "biological_approval": False, "checks": checks,
            "seeds": seeds, "initial_phases_deg": phases, "first_horizontal_positions_m": first_poses,
            "maximum_errors": errors, "tolerances": tolerance,
            "variation_scope": "Seed changes initial circular phase only; schedule, depth, horizontal speed and turning stay fixed"}
