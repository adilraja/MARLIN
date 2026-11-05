"""Summarize retained GAMA outputs and draw standard scientific figures."""
from copy import deepcopy
import csv
import json
import math
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parents[1]
REPO=ROOT.parents[3]
sys.path.insert(0,str(REPO/'tools'))
import gama_bottlenose as recorder
import analyze_gama_bottlenose as analyzer


def main():
    out=ROOT/'figures';out.mkdir(exist_ok=False)
    campaign=json.loads((ROOT/'campaign_execution.json').read_text());assert campaign['status']=='passed'
    config=json.loads(recorder.CONFIG.read_text());tol=json.loads(recorder.ACCEPTANCE.read_text())
    names=['m3_ref_a01','m3_seed1_a01','m3_seed42_a01','m3_seed184729_a01']
    colors=['#173f5f','#ed553b','#3caea3','#a45bba'];labels=['Reference','Seed 1','Seed 42','Seed 184729']
    all_runs={};summaries=[];boundary_records=[]
    for execution in campaign['runs']:
        name=execution['run_id'];directory=BASE/'trajectories'/name
        states=json.loads((directory/'trajectory.json').read_text());diagnostics=json.loads((directory/'diagnostics.json').read_text())
        fresh=analyzer.analyze(states,diagnostics,config,tol,execution['variation']);assert fresh['passed']
        original=json.loads((directory/'analysis.json').read_text());assert fresh==original
        all_runs[name]=(states,diagnostics,fresh)
        agents=[s['agents'][0] for s in states]
        summaries.append(dict(run_id=name,seed=execution['actual_seed'],variation=execution['variation'],samples=len(states),
            choices=execution['realised_choices'],sampled_peaks=fresh['measured_sampled_peaks'],errors=fresh['errors'],
            final_position_m=[*agents[-1]['horizontal_position_m']],min_depth_m=min(a['depth_m'] for a in agents),
            max_depth_m=max(a['depth_m'] for a in agents),passed=True))
        for transition in fresh['transitions'][1:]:
            i=transition['step_index'];before,current,after=agents[i-1:i+2]
            boundary_records.append(dict(run_id=name,**transition,previous_state=before['behavioural_state'],
                previous_position_xz_m=before['horizontal_position_m'],position_xz_m=current['horizontal_position_m'],
                next_position_xz_m=after['horizontal_position_m'],heading_before_at_after_deg=[a['heading_deg'] for a in (before,current,after)],
                depth_before_at_after_m=[a['depth_m'] for a in (before,current,after)],pitch_before_at_after_deg=[a['pitch_deg'] for a in (before,current,after)],
                speed_before_at_after_mps=[a['speed_mps'] for a in (before,current,after)],
                vertical_velocity_at_boundary_mps=current['vertical_velocity_mps'],
                reset_or_teleport=False,integrator_and_control_oracles_passed=True))
    repeats=[]
    for pair in campaign['repeat_comparisons']:
        a=all_runs[pair['first']][0];b=all_runs[pair['repeat']][0]
        errors={k:0. for k in ('position_m','heading_deg','depth_m','pitch_deg','speed_mps','phase_cycles','time_s')}
        for left,right in zip(a,b):
            x,y=left['agents'][0],right['agents'][0]
            errors['position_m']=max(errors['position_m'],*(abs(i-j) for i,j in zip(x['horizontal_position_m'],y['horizontal_position_m'])))
            for k,field in [('depth_m','depth_m'),('pitch_deg','pitch_deg'),('speed_mps','speed_mps')]:errors[k]=max(errors[k],abs(x[field]-y[field]))
            errors['heading_deg']=max(errors['heading_deg'],abs(analyzer.delta(x['heading_deg'],y['heading_deg'])))
            errors['time_s']=max(errors['time_s'],abs(left['simulation_time_s']-right['simulation_time_s']))
            errors['phase_cycles']=max(errors['phase_cycles'],recorder.exchange.phase_distance(recorder.exchange.phase_at(x['animation_clock'],left['simulation_time_s']),recorder.exchange.phase_at(y['animation_clock'],right['simulation_time_s'])))
        repeats.append(dict(**pair,max_discrepancies=errors));assert all(v==0 for v in errors.values())
    for name in names:
        states,diagnostics,_=all_runs[name]
        with (out/(name+'.csv')).open('x',newline='') as f:
            writer=csv.writer(f);writer.writerow(['time_s','state','episode','x_m','z_m','depth_m','speed_mps','vertical_velocity_mps','heading_deg','pitch_deg','phase_cycles'])
            for s,d in zip(states,diagnostics):
                a=s['agents'][0];writer.writerow([s['simulation_time_s'],a['behavioural_state'],d['episode'],*a['horizontal_position_m'],a['depth_m'],a['speed_mps'],a['vertical_velocity_mps'],a['heading_deg'],a['pitch_deg'],recorder.exchange.phase_at(a['animation_clock'],s['simulation_time_s'])])
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white','savefig.facecolor':'white'})
    fig,axes=plt.subplots(2,2,figsize=(13,9),constrained_layout=True)
    detail,axs=plt.subplots(2,2,figsize=(13,8),constrained_layout=True)
    position,posaxes=plt.subplots(3,1,figsize=(13,8),sharex=True,constrained_layout=True)
    for name,color,label in zip(names,colors,labels):
        states,diagnostics,_=all_runs[name];a=[s['agents'][0] for s in states];t=np.array([s['simulation_time_s'] for s in states]);dt=states[0]['simulation_step_s']
        x,z=np.array([v['horizontal_position_m'] for v in a]).T;depth=np.array([v['depth_m'] for v in a]);speed=np.array([v['speed_mps'] for v in a]);heading=np.degrees(np.unwrap(np.radians([v['heading_deg'] for v in a])))
        axes[0,0].plot(x,z,color=color,label=label);axes[0,0].scatter([x[0]],[z[0]],color=color,marker='o',s=20);axes[0,0].scatter([x[-1]],[z[-1]],color=color,marker='s',s=20)
        for ax,values in ((axes[0,1],depth),(axes[1,0],speed),(axes[1,1],heading)):ax.plot(t,values,color=color,label=label)
        phase=[recorder.exchange.phase_at(v['animation_clock'],s['simulation_time_s']) for s,v in zip(states,a)]
        vx=np.array([d['vx_mps'] for d in diagnostics]);vz=np.array([d['vz_mps'] for d in diagnostics]);vy=np.array([v['vertical_velocity_mps'] for v in a])
        accel=np.sqrt(np.diff(vx)**2+np.diff(vz)**2+np.diff(vy)**2)/dt
        for ax,values,time in ((axs[0,0],[v['pitch_deg'] for v in a],t),(axs[0,1],vy,t),(axs[1,0],phase,t),(axs[1,1],accel,t[1:])):ax.plot(time,values,color=color,label=label,lw=1.2)
        posaxes[0].plot(t,x,color=color,label=label);posaxes[1].plot(t,z,color=color,label=label)
    axes[0,0].set(xlabel='World X (m)',ylabel='World Z (m)',title='Recorded horizontal paths · circle=start, square=end');axes[0,0].axis('equal');axes[0,0].legend(fontsize=9)
    axes[0,1].set(ylabel='Depth below mean sea level (m)',xlabel='Simulation time (s)',title='Analytic descent and ascent');axes[0,1].invert_yaxis()
    axes[1,0].set(ylabel='Horizontal speed (m/s)',xlabel='Simulation time (s)',title='Smooth start and stop')
    axes[1,1].set(ylabel='Unwrapped heading (degrees)',xlabel='Simulation time (s)',title='Gradual turn across 360°');axes[1,1].axhline(360,color='gray',ls=':',lw=1)
    axs[0,0].set(ylabel='Pitch (degrees)',xlabel='Simulation time (s)',title='Trajectory tangent · positive nose up');axs[0,0].axhline(35,color='gray',ls='--');axs[0,0].axhline(-35,color='gray',ls='--')
    axs[0,1].set(ylabel='Upward velocity (m/s)',xlabel='Simulation time (s)',title='Vertical speed');axs[0,1].axhline(.45,color='gray',ls='--');axs[0,1].axhline(-.45,color='gray',ls='--')
    axs[1,0].set(ylabel='Recorded phase (cycles)',xlabel='Simulation time (s)',title='Phase wraps normally; endpoint holds freeze it')
    axs[1,1].set(ylabel='Vector acceleration (m/s²)',xlabel='Simulation time (s)',title='Sampled velocity differences');axs[1,1].axhline(.6,color='gray',ls='--',label='Locked limit');axs[1,1].legend(fontsize=9)
    bands=[(0,10,'Initial steady'),(10,22,'Turn'),(22,38,'Descent'),(38,48,'Submerged'),(48,64,'Ascent'),(64,74,'Final steady')]
    for ax in [axes[0,1],axes[1,0],axes[1,1],*axs.flat,*posaxes[:2]]:
        for index,(start,end,label) in enumerate(bands):
            if index%2:ax.axvspan(start,end,color='#e7eef4',alpha=.45,zorder=-2)
            if start:ax.axvline(start,color='gray',lw=.5,alpha=.5)
        ax.grid(alpha=.2)
    for index,(start,end,label) in enumerate(bands):
        posaxes[2].axvspan(start,end,color=plt.cm.Set3(index/6));posaxes[2].text((start+end)/2,.5,label,ha='center',va='center',fontsize=10)
    posaxes[0].set(ylabel='World X (m)',title='Recorded position and executed state intervals');posaxes[0].legend(ncol=4,fontsize=9)
    posaxes[1].set(ylabel='World Z (m)');posaxes[2].set(yticks=[],ylim=(0,1),xlabel='Simulation time (s)',ylabel='Executed state')
    for figure,title,name in [(fig,'M3 · Actual GAMA movement · reference and three seeded choices','movement_overview'),(detail,'M3 · Recorded attitude, phase controls and acceleration · no body animation','attitude_and_constraints'),(position,'M3 · SI position and state timing · engineering demonstration','position_and_states')]:
        figure.suptitle(title,fontsize=14,weight='bold');figure.savefig(out/(name+'.png'),dpi=150);figure.savefig(out/(name+'.svg'));plt.close(figure)
    result=dict(passed=True,runs=summaries,repeatability=repeats,total_actual_executions=8,total_samples=sum(v['samples'] for v in summaries),samples_per_execution=297,
                actual_stochastic_variation=campaign['actual_seed_variation'],human_gate_b='pending',biological_approval=False)
    recorder.write(ROOT/'campaign_analysis.json',result);recorder.write(ROOT/'boundary_audit.json',dict(passed=True,boundaries=boundary_records))
    print(json.dumps(dict(passed=True,actual_executions=8,total_samples=result['total_samples'],figures=str(out))))


if __name__=='__main__':main()
