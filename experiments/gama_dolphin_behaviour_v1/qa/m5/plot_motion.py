"""Plot retained composed playback records; never regenerate GAMA states."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parent
result=json.loads((ROOT/'primary02/result.json').read_text())
assert result['status']=='passed'
records=json.loads((Path(result['media_directory'])/'schedule_a.json').read_text())
times=np.array([r['simulation_time_s'] for r in records])
agents=[r['frame']['agent'] for r in records]
position=np.array([a['horizontal_position_m'] for a in agents])
depth=np.array([a['depth_m'] for a in agents])
speed=np.array([a['speed_mps'] for a in agents])
heading=np.array([a['heading_deg'] for a in agents])
heading_change=np.rad2deg(np.unwrap(np.deg2rad(heading)))-heading[0]
pitch=np.array([a['pitch_deg'] for a in agents])
phase=np.array([r['pose_controls']['phase'] for r in records])
weight=np.array([r['pose_controls']['weight'] for r in records])
fig,axes=plt.subplots(3,2,figsize=(13,10))
fig.subplots_adjust(left=.075,right=.98,bottom=.09,top=.90,hspace=.50,wspace=.24)
fig.suptitle('M5 · Full accepted 74 s reference · measured composed playback controls',fontsize=15,y=.98)
axes[0,0].plot(position[:,0],position[:,1],color='#116e89')
axes[0,0].scatter(position[0,0],position[0,1],label='Start',color='#cc7a12')
axes[0,0].set(xlabel='GAMA horizontal X (m)',ylabel='GAMA horizontal Z (m)',title='Recorded path; world position owned by GAMA')
axes[0,0].axis('equal');axes[0,0].legend()
axes[0,1].plot(times,depth);axes[0,1].invert_yaxis();axes[0,1].set(xlabel='Simulation time (s)',ylabel='Depth below mean sea level (m)')
axes[1,0].plot(times,speed);axes[1,0].set(xlabel='Simulation time (s)',ylabel='Horizontal speed (m/s)')
axes[1,1].plot(times,heading_change,label='Heading change (unwrapped)');axes[1,1].plot(times,pitch,label='Pitch');axes[1,1].set(xlabel='Simulation time (s)',ylabel='Degrees');axes[1,1].legend()
axes[2,0].plot(times,phase,'.-',markersize=2);axes[2,0].set(xlabel='Simulation time (s)',ylabel='Recorded normalized phase (cycles)',title='Modulo-one loop wraps are intentional')
axes[2,1].plot(times,weight);axes[2,1].set(xlabel='Simulation time (s)',ylabel='Visual cycle amplitude weight',ylim=(-.05,1.05),title='Bounded engineering display mapping')
for ax in axes.flat:
 ax.grid(alpha=.22)
 if ax is not axes[0,0]:
  for t in [10,22,38,48,64]:ax.axvline(t,color='#718096',alpha=.3,linestyle='--')
fig.text(.01,.02,'Existing-cycle manoeuvre limits retained. Ocean phase fixed at zero; no biological, optical or survey validation.',fontsize=9)
out=ROOT/'figures';out.mkdir(exist_ok=True)
for suffix in ['png','svg']:
 p=out/('motion_and_phase.'+suffix)
 assert not p.exists();fig.savefig(p,dpi=150)
print(json.dumps(dict(passed=True,records=len(records),figure=str(out/'motion_and_phase.png'))))
