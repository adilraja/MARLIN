"""Single-porpoise exchange contract; validation and conversion never author USD.

Version 1 remains in exchange.py. This version makes run identity, the fixed
simulation clock and the one authoritative vertical coordinate explicit.
"""
from copy import deepcopy
import math

from .exchange import IDENTIFIER, _number, _object

STATES = frozenset(("surface", "shallow_swim", "descent", "submerged_swim", "ascent"))
MAX_INTEGER = 2**53 - 1
CLOCK_ABS_TOLERANCE_S = 1e-9


def _identifier(value, label):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} must be a safe identifier, at most 128 characters")


def _integer(value, label):
    if type(value) is not int or not 0 <= value <= MAX_INTEGER:
        raise ValueError(f"{label} must be an integer in [0, 2^53-1]")


def validate_step(payload):
    """Validate the complete boundary contract and return a detached snapshot.

    JSON Schema describes structure; this validator also rejects non-finite
    numbers and inconsistent clocks. It certifies no biological parameter.
    """
    _object(payload, ("schema_version", "run_id", "step_index", "simulation_time_s",
                      "simulation_step_s", "seed", "agents"), (), "step")
    if payload["schema_version"] != "2.0":
        raise ValueError("schema_version must be '2.0'")
    _identifier(payload["run_id"], "run_id")
    _integer(payload["step_index"], "step_index")
    _integer(payload["seed"], "seed")
    _number(payload["simulation_time_s"], "simulation_time_s", 0)
    dt = _number(payload["simulation_step_s"], "simulation_step_s", 0)
    if dt <= 0:
        raise ValueError("simulation_step_s must be positive")
    expected_time = payload["step_index"] * dt
    _number(expected_time, "step_index * simulation_step_s", 0)
    if not math.isclose(payload["simulation_time_s"], expected_time,
                        rel_tol=0, abs_tol=CLOCK_ABS_TOLERANCE_S):
        raise ValueError("simulation_time_s must equal step_index * simulation_step_s within 1e-9 s")
    agents = payload["agents"]
    if not isinstance(agents, list) or len(agents) != 1:
        raise ValueError("agents must contain exactly one harbour porpoise")
    agent = agents[0]
    _object(agent, ("agent_id", "species", "behavioural_state", "horizontal_position_m",
                    "heading_deg", "speed_mps", "vertical_reference", "depth_m"), (), "agent")
    _identifier(agent["agent_id"], "agent_id")
    if agent["species"] != "harbour_porpoise":
        raise ValueError("species must be 'harbour_porpoise'")
    if not isinstance(agent["behavioural_state"], str) or agent["behavioural_state"] not in STATES:
        raise ValueError("behavioural_state is not a v2 porpoise state")
    position = agent["horizontal_position_m"]
    if not isinstance(position, list) or len(position) != 2:
        raise ValueError("horizontal_position_m must be [x, z]")
    for axis, value in zip("xz", position):
        _number(value, f"horizontal_position_m.{axis}")
    heading = _number(agent["heading_deg"], "heading_deg", 0)
    if heading >= 360:
        raise ValueError("heading_deg must be less than 360")
    _number(agent["speed_mps"], "speed_mps", 0)
    if agent["vertical_reference"] != "mean_sea_level":
        raise ValueError("vertical_reference must be 'mean_sea_level'")
    _number(agent["depth_m"], "depth_m", 0)
    return deepcopy(payload)


def preview_transforms(payload, meters_per_scene_unit):
    """Resolve depth below the fixed mean plane Y=0, without wave following.

    The USD caller supplies actual inspected stage units. Horizontal speed is
    metadata, not an instruction for MARLIN to integrate autonomous motion.
    """
    step = validate_step(payload)
    units = _number(meters_per_scene_unit, "meters_per_scene_unit", 0)
    if units <= 0:
        raise ValueError("meters_per_scene_unit must be positive")
    agent = step["agents"][0]
    x, z = agent["horizontal_position_m"]
    position_m = [x, -agent["depth_m"], z]
    position = [value / units for value in position_m]
    speed = agent["speed_mps"] / units
    for value in (*position, speed):
        _number(value, "converted scene value")
    heading = math.radians(agent["heading_deg"])
    return [{"id": agent["agent_id"], "position_m": position_m,
             "position_scene_units": position, "heading_deg": agent["heading_deg"],
             "forward_y_up": [math.sin(heading), 0.0, math.cos(heading)],
             "speed_scene_units_per_s": speed,
             "vertical_reference": agent["vertical_reference"]}]


class StepBuffer:
    """One external run and actor identity, latest snapshot only, no USD writes.

    Index gaps allow replay of preselected snapshots. There is no interpolation,
    advancement, creation, deletion, timer, or controller handoff in this buffer.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self._latest = None
        self.accepted_steps = 0

    @property
    def latest(self):
        return deepcopy(self._latest)

    def accept(self, payload):
        step = validate_step(payload)
        previous = self._latest
        if previous is not None:
            if step == previous:
                return {"accepted": True, "duplicate": True, "rendered": False}
            for field in ("run_id", "seed", "simulation_step_s"):
                if step[field] != previous[field]:
                    raise ValueError(f"{field} changed within a run; reset the validation buffer first")
            if step["agents"][0]["agent_id"] != previous["agents"][0]["agent_id"]:
                raise ValueError("agent_id changed within a run; reset the validation buffer first")
            if step["step_index"] <= previous["step_index"]:
                raise ValueError("step_index must increase; only an identical latest-step retry is allowed")
            if step["simulation_time_s"] <= previous["simulation_time_s"]:
                raise ValueError("simulation_time_s must increase")
        self._latest = step
        self.accepted_steps += 1
        return {"accepted": True, "duplicate": False, "rendered": False}
