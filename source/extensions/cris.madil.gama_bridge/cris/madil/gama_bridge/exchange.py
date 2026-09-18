"""Pure-Python v1 exchange contract. No Kit, USD or renderer dependencies.

These checks establish syntactic/transport validity, NOT biological validity.
Positions are metres in MARLIN's local Y-up frame, not geographic coordinates.
"""
from copy import deepcopy
import math
import re

STATES = frozenset((
    "surface", "shallow_swim", "dive", "submerged", "ascent",
    "flying", "gliding", "banking", "descending", "on_water", "takeoff", "landing",
))
MAX_AGENTS = 1000  # Transport guard, not an ecological population limit.
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}\Z")


def _number(value, label, minimum=None):
    if type(value) not in (float, int):
        raise ValueError(f"{label} must be a finite number (not a boolean/string)")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite or (minimum is not None and value < minimum):
        raise ValueError(f"{label} must be finite and >= {minimum}" if minimum is not None
                         else f"{label} must be finite")
    return value


def _object(value, required, optional, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    missing = set(required) - value.keys()
    extra = value.keys() - set(required) - set(optional)
    if missing or extra:
        raise ValueError(f"{label}: missing fields {sorted(missing)}; unknown fields {sorted(extra)}")


def validate_step(payload):
    """Return a detached snapshot, accepting the manual's unversioned example as v1."""
    _object(payload, ("time_s", "seed", "agents"), ("schema_version",), "step")
    if payload.get("schema_version", "1.0") != "1.0":
        raise ValueError("schema_version must be '1.0'")
    _number(payload["time_s"], "time_s", 0)
    if type(payload["seed"]) is not int or not 0 <= payload["seed"] <= 2**53 - 1:
        raise ValueError("seed must be an integer in [0, 2^53-1]")
    agents = payload["agents"]
    if not isinstance(agents, list) or len(agents) > MAX_AGENTS:
        raise ValueError(f"agents must be an array with at most {MAX_AGENTS} entries")
    seen = set()
    for index, agent in enumerate(agents):
        label = f"agents[{index}]"
        _object(agent, ("id", "species", "state", "position_m", "heading_deg", "speed_mps"),
                ("depth_m", "altitude_m", "group_id"), label)
        for field in ("id", "species", "group_id"):
            if field in agent and (not isinstance(agent[field], str) or
                                   not IDENTIFIER.fullmatch(agent[field])):
                raise ValueError(f"{label}.{field} must be a safe identifier, at most 128 characters")
        if agent["id"] in seen:
            raise ValueError(f"Duplicate agent id: {agent['id']}")
        seen.add(agent["id"])
        if not isinstance(agent["state"], str) or agent["state"] not in STATES:
            raise ValueError(f"{label}.state is not a v1 state")
        position = agent["position_m"]
        if not isinstance(position, list) or len(position) != 3:
            raise ValueError(f"{label}.position_m must be [x, y, z]")
        for axis, value in zip("xyz", position):
            _number(value, f"{label}.position_m.{axis}")
        heading = _number(agent["heading_deg"], f"{label}.heading_deg", 0)
        if heading >= 360:
            raise ValueError(f"{label}.heading_deg must be less than 360")
        _number(agent["speed_mps"], f"{label}.speed_mps", 0)
        for field in ("depth_m", "altitude_m"):
            if field in agent:
                _number(agent[field], f"{label}.{field}", 0)
        # v1 uses the fixed mean sea plane y=0, not the moving wave surface.
        if "depth_m" in agent and abs(agent["depth_m"] - max(0, -position[1])) > 1e-6:
            raise ValueError(f"{label}.depth_m disagrees with position_m relative to y=0")
        if "altitude_m" in agent and abs(agent["altitude_m"] - max(0, position[1])) > 1e-6:
            raise ValueError(f"{label}.altitude_m disagrees with position_m relative to y=0")
    snapshot = deepcopy(payload)
    snapshot["schema_version"] = "1.0"
    return snapshot


def preview_transforms(payload, meters_per_scene_unit):
    """Pure conversion only; caller must eventually read actual USD stage units.

    Asset scale/orientation corrections are separate from these motion roots.
    No species binding, pixel projection, swimming integration or wave following.
    """
    snapshot = validate_step(payload)
    _number(meters_per_scene_unit, "meters_per_scene_unit")
    if meters_per_scene_unit <= 0:
        raise ValueError("meters_per_scene_unit must be positive")
    transforms = []
    for agent in snapshot["agents"]:
        position = [v / meters_per_scene_unit for v in agent["position_m"]]
        speed = agent["speed_mps"] / meters_per_scene_unit
        for value in (*position, speed):
            _number(value, "converted scene value")
        heading = math.radians(agent["heading_deg"])
        transforms.append({
            "id": agent["id"], "position_scene_units": position,
            "heading_deg": agent["heading_deg"],
            "forward_y_up": [math.sin(heading), 0.0, math.cos(heading)],
            "speed_scene_units_per_s": speed,
        })
    return transforms


class StepBuffer:
    """One in-memory run; full snapshots, no interpolation or autonomous advance."""

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
        if self._latest is not None:
            if step == self._latest:
                return {"accepted": True, "duplicate": True, "rendered": False}
            if step["seed"] != self._latest["seed"]:
                raise ValueError("seed changed within a run; reset the exchange buffer first")
            if step["time_s"] <= self._latest["time_s"]:
                raise ValueError("time_s must increase; only an identical latest-step retry is allowed")
            previous = {a["id"]: a["species"] for a in self._latest["agents"]}
            for agent in step["agents"]:
                if agent["id"] in previous and previous[agent["id"]] != agent["species"]:
                    raise ValueError("an agent present in consecutive steps cannot change species")
        self._latest = step
        self.accepted_steps += 1
        return {"accepted": True, "duplicate": False, "rendered": False}
