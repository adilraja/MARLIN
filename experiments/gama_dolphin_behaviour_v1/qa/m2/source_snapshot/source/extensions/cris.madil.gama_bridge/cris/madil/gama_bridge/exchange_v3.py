"""One Model 61A: explicit simulation clock, bounded presentation, no timers."""
from copy import deepcopy
import math

from .exchange import _number, _object
from .exchange_v2 import _identifier, _integer, CLOCK_ABS_TOLERANCE_S

STATES = frozenset(('steady_swim', 'turn', 'descent', 'submerged_swim', 'ascent'))
PHASE_TOLERANCE_CYCLES = 1e-9


def phase_at(clock, seconds):
    cycles = clock['epoch_phase_cycles'] + (seconds-clock['epoch_time_s'])*clock['rate_hz']
    _number(cycles, 'derived animation cycles')
    return cycles % 1.0


def phase_distance(a, b):
    return abs((a-b+.5) % 1.0-.5)


def validate_step(payload):
    _object(payload, ('schema_version', 'model_version', 'run_id', 'step_index',
                      'simulation_time_s', 'simulation_step_s', 'seed', 'agents'), (), 'step')
    if payload['schema_version'] != '3.0':
        raise ValueError("schema_version must be '3.0'")
    for name in ('model_version', 'run_id'):
        _identifier(payload[name], name)
    for name in ('step_index', 'seed'):
        _integer(payload[name], name)
    t = _number(payload['simulation_time_s'], 'simulation_time_s', 0)
    dt = _number(payload['simulation_step_s'], 'simulation_step_s', 0)
    if dt <= 0:
        raise ValueError('simulation_step_s must be positive')
    expected = _number(payload['step_index']*dt, 'derived simulation time', 0)
    if not math.isclose(t, expected, rel_tol=0, abs_tol=CLOCK_ABS_TOLERANCE_S):
        raise ValueError('simulation clock must equal step_index * simulation_step_s')
    agents = payload['agents']
    if not isinstance(agents, list) or len(agents) != 1:
        raise ValueError('Exactly one bottlenose agent is required')
    a = agents[0]
    _object(a, ('agent_id', 'species', 'behavioural_state', 'horizontal_position_m',
                'heading_deg', 'pitch_deg', 'roll_deg', 'speed_mps', 'vertical_velocity_mps',
                'vertical_reference', 'depth_m', 'state_entry_time_s', 'transition_duration_s',
                'animation_clock'), (), 'agent')
    _identifier(a['agent_id'], 'agent_id')
    if a['species'] != 'bottlenose_dolphin':
        raise ValueError("species must be 'bottlenose_dolphin'")
    if not isinstance(a['behavioural_state'], str) or a['behavioural_state'] not in STATES:
        raise ValueError('Unknown v3 behavioural_state')
    if a['vertical_reference'] != 'mean_sea_level':
        raise ValueError('Only fixed mean sea level Y=0 is supported')
    position = a['horizontal_position_m']
    if not isinstance(position, list) or len(position) != 2:
        raise ValueError('horizontal_position_m must be [x,z]')
    for value in position:
        _number(value, 'horizontal position')
    for name in ('depth_m', 'speed_mps', 'state_entry_time_s', 'transition_duration_s'):
        _number(a[name], name, 0)
    _number(a['vertical_velocity_mps'], 'vertical_velocity_mps')
    for name, lower, upper in [('heading_deg', 0, 360), ('pitch_deg', -90, 90), ('roll_deg', -180, 180)]:
        value = _number(a[name], name, lower)
        if value > upper or (name == 'heading_deg' and value == upper):
            raise ValueError(name+' is outside its mathematical angle domain')
    if a['state_entry_time_s'] > t:
        raise ValueError('state entry cannot be in the future')
    clock = a['animation_clock']
    _object(clock, ('version', 'epoch_time_s', 'epoch_phase_cycles', 'rate_hz'), (), 'animation_clock')
    if clock['version'] != 'constant_rate_v1':
        raise ValueError('Unknown animation clock version')
    epoch = _number(clock['epoch_time_s'], 'epoch_time_s', 0)
    phase = _number(clock['epoch_phase_cycles'], 'epoch_phase_cycles', 0)
    rate = _number(clock['rate_hz'], 'rate_hz', 0)
    if epoch > t or phase >= 1:
        raise ValueError('Animation epoch must be <= simulation time and phase must be < 1')
    if a['speed_mps'] == 0 and rate != 0:
        raise ValueError('The v3 zero-speed policy requires a frozen phase (rate_hz=0)')
    phase_at(clock, t)
    return deepcopy(payload)


def _angle(a, b, u):
    return a + ((b-a+180) % 360-180)*u


def sample_steps(left, right, seconds):
    """Piecewise linear position/attitude; shortest circular heading/roll arc.

    Discrete state and its clock are left-continuous until the right endpoint.
    No extrapolation and no independent integration of reported speed occurs.
    """
    _number(seconds, 'evaluation_time_s', 0)
    t0, t1 = left['simulation_time_s'], right['simulation_time_s']
    if not t0 <= seconds <= t1:
        raise ValueError('Requested time is outside the retained sample bracket; pose held')
    u = 0.0 if t0 == t1 else (seconds-t0)/(t1-t0)
    a, b = left['agents'][0], right['agents'][0]
    state = deepcopy(b if seconds == t1 else a)
    for name in ('depth_m', 'speed_mps', 'vertical_velocity_mps', 'pitch_deg'):
        state[name] = (1-u)*a[name] + u*b[name]
    state['horizontal_position_m'] = [(1-u)*x+u*y for x,y in zip(a['horizontal_position_m'],b['horizontal_position_m'])]
    state['heading_deg'] = _angle(a['heading_deg'],b['heading_deg'],u) % 360
    state['roll_deg'] = (_angle(a['roll_deg'],b['roll_deg'],u)+180) % 360-180
    duration = state['transition_duration_s']
    progress = 1.0 if duration == 0 else min(1.0, max(0.0,(seconds-state['state_entry_time_s'])/duration))
    return dict(schema_version='3.0',model_version=left['model_version'],run_id=left['run_id'],
                seed=left['seed'],evaluation_time_s=seconds,
                bracket_step_indices=[left['step_index'],right['step_index']],
                transition_progress=progress,animation_phase_cycles=phase_at(state['animation_clock'],seconds),
                agent=state,body_pose_mapping='static_rest_pose_m2',rendered=False)


class StepBuffer:
    """At most two contiguous producer snapshots; explicit queries only."""
    def __init__(self):
        self.reset()

    def reset(self):
        self.samples = []
        self.accepted_steps = 0

    @property
    def latest(self):
        return deepcopy(self.samples[-1]) if self.samples else None

    def accept(self, payload):
        step = validate_step(payload)
        if self.samples:
            previous = self.samples[-1]
            if step == previous:
                return dict(accepted=True,duplicate=True,rendered=False)
            for key in ('model_version','run_id','seed','simulation_step_s'):
                if step[key] != previous[key]:
                    raise ValueError(key+' changed within a run; explicit reset required')
            a,b = previous['agents'][0],step['agents'][0]
            if a['agent_id'] != b['agent_id']:
                raise ValueError('agent_id changed within the run')
            if step['step_index'] != previous['step_index']+1:
                raise ValueError('Stale/out-of-order/missing step: contiguous delivery required; pose held')
            if step['simulation_time_s'] <= previous['simulation_time_s']:
                raise ValueError('Simulation time must increase')
            if b['state_entry_time_s'] < a['state_entry_time_s']:
                raise ValueError('State-entry time cannot move backwards')
            if b['behavioural_state'] != a['behavioural_state'] and b['state_entry_time_s'] < previous['simulation_time_s']:
                raise ValueError('New state entry precedes the previous snapshot')
            if phase_distance(phase_at(a['animation_clock'],step['simulation_time_s']),
                              phase_at(b['animation_clock'],step['simulation_time_s'])) > PHASE_TOLERANCE_CYCLES:
                raise ValueError('Animation clock re-anchor is discontinuous')
        elif step['step_index'] != 0:
            raise ValueError('A run starts with step_index=0; no implicit skipped history')
        self.samples = (self.samples+[step])[-2:]
        self.accepted_steps += 1
        return dict(accepted=True,duplicate=False,rendered=False)

    def evaluate(self, seconds):
        if not self.samples:
            raise ValueError('No accepted state; initial pose held')
        return sample_steps(self.samples[0],self.samples[-1],seconds)
