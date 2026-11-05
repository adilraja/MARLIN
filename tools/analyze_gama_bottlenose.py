"""Independent SI trajectory acceptance oracle; does not generate run outputs."""
import math


def smooth(u):return 6*u**5-15*u**4+10*u**3
def derivative(u):return 30*u*u*(1-u)*(1-u)
def delta(a,b):return (b-a+180)%360-180


def controls(t,p,choice):
    durations=[p[k] for k in ('steady_s','turn_s','descent_s','submerged_s','ascent_s','final_steady_s')]
    names=['initial_steady','turn','descent','submerged_swim','ascent','final_steady']
    ends=[];elapsed=0.
    for d in durations:elapsed+=d;ends.append(elapsed)
    index=next((i for i,end in enumerate(ends) if t<end),5)
    entry=0. if index==0 else ends[index-1];duration=durations[index];u=(t-entry)/duration
    h=p['initial_heading_deg']+(0 if index==0 else choice['realised_turn_deg']*smooth(u) if index==1 else choice['realised_turn_deg'])
    depth=p['initial_depth_m'];vy=0.
    if index in (2,4):
        first,last=(p['initial_depth_m'],choice['realised_depth_m']) if index==2 else (choice['realised_depth_m'],p['initial_depth_m'])
        depth=first+(last-first)*smooth(u);vy=-(last-first)*derivative(u)/duration
    elif index==3:depth=choice['realised_depth_m']
    hold,ramp=p['stationary_hold_s'],p['speed_ramp_s'];end=ends[-1]
    speed=choice['realised_speed_mps']
    if t<=hold or t>=end-hold:speed=0.
    elif t<hold+ramp:speed*=smooth((t-hold)/ramp)
    elif t>end-hold-ramp:speed*=1-smooth((t-end+hold+ramp)/ramp)
    pitch=math.degrees(math.atan2(vy,speed)) if speed else 0.
    return dict(episode=names[index],state='steady_swim' if index in (0,5) else names[index],entry=entry,duration=duration,
                heading=h%360,depth=depth,vy=vy,speed=speed,pitch=pitch,
                vx=speed*math.sin(math.radians(h)),vz=speed*math.cos(math.radians(h)))


def analytic_envelopes(p):
    """Conservative continuous bounds for every declared random choice."""
    vmax=p['cruise_speed_mps']+p['speed_spread_mps'];vmin=p['cruise_speed_mps']-p['speed_spread_mps']
    change=p['target_depth_m']+p['depth_spread_m']-p['initial_depth_m']
    d=min(p['descent_s'],p['ascent_s']);angle=abs(p['turn_angle_deg'])+p['turn_spread_deg']
    vy=1.875*change/d;ay=(10/math.sqrt(3))*change/d**2
    heading_rate=1.875*angle/p['turn_s'];heading_acc=(10/math.sqrt(3))*angle/p['turn_s']**2
    speed_acc=1.875*vmax/p['speed_ramp_s']
    lateral=vmax*math.radians(heading_rate)
    duration=sum(p[k] for k in ('steady_s','turn_s','descent_s','submerged_s','ascent_s','final_steady_s'))
    return dict(horizontal_speed_mps=vmax,speed_3d_mps=math.hypot(vmax,vy),horizontal_acceleration_mps2=max(speed_acc,lateral),
        vector_acceleration_mps2=max(speed_acc,lateral,ay),heading_rate_deg_s=heading_rate,heading_acceleration_deg_s2=heading_acc,
        vertical_speed_mps=vy,vertical_acceleration_mps2=ay,pitch_abs_deg=math.degrees(math.atan2(vy,vmin)),
        pitch_rate_deg_s=math.degrees(ay/vmin),roll_abs_deg=0.,max_distance_from_start_m=vmax*(duration-2*p['stationary_hold_s']-p['speed_ramp_s']),
        note='Quintic derivative max 1.875, second derivative max 10/sqrt(3); ramp, turn and depth phases do not overlap. Distance bound integrates both half-area speed ramps and stationary endpoint holds.')


def analyze(states,diagnostics,config,tolerance,variation):
    # Imported lazily to keep the scalar oracle independently importable.
    import gama_bottlenose as recorder
    p=config['parameters'];bounds=tolerance['bounds'];dt=p['step'];checks={};errors={};measurements={};transitions=[]
    expected_count=round(sum(p[k] for k in ('steady_s','turn_s','descent_s','submerged_s','ascent_s','final_steady_s'))/dt)+1
    if len(states)!=expected_count or len(diagnostics)!=len(states):raise ValueError('Incomplete trajectory/diagnostics')
    buffer=recorder.exchange.StepBuffer()
    for state in states:
        if buffer.accept(state)['duplicate']:raise ValueError('Duplicate recorded state')
    choice={k:diagnostics[0][k] for k in ('realised_turn_deg','realised_depth_m','realised_speed_mps','random_draw_count')}
    checks['choices_fixed']=all(all(d[k]==v for k,v in choice.items()) for d in diagnostics)
    checks['variation_draw_count']=choice['random_draw_count']==(3 if variation else 0)
    for realised,base,spread in [('realised_turn_deg','turn_angle_deg','turn_spread_deg'),('realised_depth_m','target_depth_m','depth_spread_m'),('realised_speed_mps','cruise_speed_mps','speed_spread_mps')]:
        checks[realised+'_in_range']=abs(choice[realised]-p[base]) <= (p[spread] if variation else 0)
    def error(name,value,limit):
        errors[name]=max(errors.get(name,0.),abs(value));checks[name]=errors[name]<=limit
    expected_x=p['start_x_m'];expected_z=p['start_z_m'];previous=None;phase=p['initial_phase_cycles']
    for i,(state,d) in enumerate(zip(states,diagnostics)):
        t=i*dt;a=state['agents'][0];e=controls(t,p,choice)
        if previous:
            expected_x+=dt*(previous['vx']+e['vx'])/2;expected_z+=dt*(previous['vz']+e['vz'])/2
            phase=(phase+(p['animation_rate_hz'] if previous['speed']>0 else 0)*dt)%1
        error('clock_s',state['simulation_time_s']-t,tolerance['time_error_s'])
        error('step_s',state['simulation_step_s']-dt,tolerance['time_error_s'])
        error('horizontal_position_m',max(abs(a['horizontal_position_m'][0]-expected_x),abs(a['horizontal_position_m'][1]-expected_z)),tolerance['position_error_m'])
        error('depth_m',a['depth_m']-e['depth'],tolerance['position_error_m'])
        error('heading_deg',delta(e['heading'],a['heading_deg']),tolerance['heading_error_deg'])
        error('pitch_deg',a['pitch_deg']-e['pitch'],tolerance['attitude_error_deg'])
        error('speed_mps',a['speed_mps']-e['speed'],tolerance['velocity_error_mps'])
        error('vertical_velocity_mps',a['vertical_velocity_mps']-e['vy'],tolerance['velocity_error_mps'])
        error('vx_mps',d['vx_mps']-e['vx'],tolerance['velocity_error_mps']);error('vz_mps',d['vz_mps']-e['vz'],tolerance['velocity_error_mps'])
        error('state_entry_s',a['state_entry_time_s']-e['entry'],tolerance['time_error_s'])
        error('state_duration_s',a['transition_duration_s']-e['duration'],tolerance['time_error_s'])
        checks['state_episode']=checks.get('state_episode',True) and a['behavioural_state']==e['state'] and d['episode']==e['episode']
        clock=a['animation_clock'];error('phase_cycles',recorder.exchange.phase_distance(recorder.exchange.phase_at(clock,t),phase),tolerance['phase_error_cycles'])
        error('phase_epoch_s',clock['epoch_time_s']-t,tolerance['time_error_s'])
        error('phase_rate_hz',clock['rate_hz']-(p['animation_rate_hz'] if e['speed']>0 else 0),tolerance['velocity_error_mps'])
        if not transitions or transitions[-1]['episode']!=d['episode']:
            transitions.append(dict(episode=d['episode'],state=a['behavioural_state'],step_index=i,time_s=t))
        x,z=a['horizontal_position_m'];b=bounds
        checks['inside_volume']=checks.get('inside_volume',True) and b['x_m'][0]<=x<=b['x_m'][1] and b['z_m'][0]<=z<=b['z_m'][1] and b['depth_m'][0]<=a['depth_m']<=b['depth_m'][1]
        checks['speed_domain']=checks.get('speed_domain',True) and b['horizontal_speed_mps'][0]<=a['speed_mps']<=b['horizontal_speed_mps'][1]+tolerance['numeric_bound_slack']
        def peak(name,value,limit):
            measurements[name]=max(measurements.get(name,0.),abs(value));checks[name+'_bounded']=measurements[name]<=limit+tolerance['numeric_bound_slack']
        peak('speed_3d_mps',math.hypot(a['speed_mps'],a['vertical_velocity_mps']),b['speed_3d_mps'][1])
        for name,field in [('vertical_speed_mps','vertical_velocity_mps'),('pitch_abs_deg','pitch_deg'),('roll_abs_deg','roll_deg')]:peak(name,a[field],b[name])
        if i:
            last=states[i-1]['agents'][0];ld=diagnostics[i-1]
            increment=[a['horizontal_position_m'][j]-last['horizontal_position_m'][j] for j in (0,1)]
            error('horizontal_integrator_residual_m',max(abs(increment[0]-dt*(ld['vx_mps']+d['vx_mps'])/2),abs(increment[1]-dt*(ld['vz_mps']+d['vz_mps'])/2)),tolerance['position_error_m'])
            peak('horizontal_acceleration_mps2',math.hypot(d['vx_mps']-ld['vx_mps'],d['vz_mps']-ld['vz_mps'])/dt,b['horizontal_acceleration_mps2'])
            peak('vector_acceleration_mps2',math.sqrt((d['vx_mps']-ld['vx_mps'])**2+(d['vz_mps']-ld['vz_mps'])**2+(a['vertical_velocity_mps']-last['vertical_velocity_mps'])**2)/dt,b['vector_acceleration_mps2'])
            peak('vertical_acceleration_mps2',(a['vertical_velocity_mps']-last['vertical_velocity_mps'])/dt,b['vertical_acceleration_mps2'])
            rate=delta(last['heading_deg'],a['heading_deg'])/dt;peak('heading_rate_deg_s',rate,b['heading_rate_deg_s'])
            peak('pitch_rate_deg_s',delta(last['pitch_deg'],a['pitch_deg'])/dt,b['pitch_rate_deg_s'])
            if i>1:peak('heading_acceleration_deg_s2',(rate-last_rate)/dt,b['heading_acceleration_deg_s2'])
            last_rate=rate
        previous=e
    checks['episode_order']=[v['episode'] for v in transitions]==['initial_steady','turn','descent','submerged_swim','ascent','final_steady']
    checks['stationary_endpoints']=states[0]['agents'][0]['speed_mps']==states[-1]['agents'][0]['speed_mps']==0
    envelope=analytic_envelopes(p)
    for name,value in envelope.items():
        if name in bounds and isinstance(bounds[name],(int,float)):checks['analytic_'+name]=value<=bounds[name]+tolerance['numeric_bound_slack']
        elif name in ('horizontal_speed_mps','speed_3d_mps'):checks['analytic_'+name]=value<=bounds[name][1]+tolerance['numeric_bound_slack']
    reach=envelope['max_distance_from_start_m']
    checks['analytic_domain_margin']=all(lo<origin-reach and origin+reach<hi for origin,(lo,hi) in ((p['start_x_m'],bounds['x_m']),(p['start_z_m'],bounds['z_m'])))
    return dict(passed=all(checks.values()),checks=checks,errors=errors,measured_sampled_peaks=measurements,continuous_parameter_box_envelopes=envelope,
        realised_choices=choice,transitions=transitions,samples=len(states),duration_s=states[-1]['simulation_time_s'],
        accepted_continuity='No reset/clamp; horizontal endpoint trapezoid residual and independent analytic vertical/attitude oracles checked. State thresholds/controls have continuous values and zero first/second quintic derivatives at joins.',
        interpretation='Engineering constrained trajectory; no rendered-body or biological acceptance')
