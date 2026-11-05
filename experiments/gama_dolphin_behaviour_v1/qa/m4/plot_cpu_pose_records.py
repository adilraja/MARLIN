"""Draw scientific geometry views; these are CPU skinning, not RTX renders."""
import json
from pathlib import Path
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/marlin_m4_matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
import numpy as np

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[3]


def main():
    output=ROOT/'figures';output.mkdir(exist_ok=True)
    record=json.loads((ROOT/'cpu_pose_records.json').read_text());data=np.load(REPO/record['geometry_file'])
    points,triangles,times=data['points'],data['triangles'],data['times']
    indices=[int(np.flatnonzero(times==t)[0]) for t in (4,6,16,30,56,70)]
    fig,axes=plt.subplots(2,len(indices),figsize=(18,7),constrained_layout=True)
    for column,index in enumerate(indices):
        vertices=points[index];faces=vertices[triangles];normals=np.cross(faces[:,1]-faces[:,0],faces[:,2]-faces[:,0]);normals/=np.linalg.norm(normals,axis=1)[:,None]
        for row,(horizontal,vertical,depth) in enumerate(((2,1,0),(0,2,1))):
            order=np.argsort(faces[:,:,depth].mean(axis=1))
            shade=.38+.48*np.maximum(0,np.sum(normals*np.array([.3,.8,.5]),axis=1))
            colors=np.column_stack((shade*.7,shade*.85,shade,np.ones(len(shade))))
            collection=PolyCollection(faces[order][:,:,[horizontal,vertical]],facecolors=colors[order],edgecolors='none',rasterized=True)
            ax=axes[row,column];ax.add_collection(collection);ax.autoscale_view();ax.set_aspect('equal');ax.grid(alpha=.2)
            if row==0:
                controls=record['records'][index]['pose_controls'];state=record['records'][index]['frame']['agent']['behavioural_state']
                ax.set_title(f't={times[index]:g} s · {state}\nphase={controls["phase"]:.3f}, weight={controls["weight"]:.3f}',fontsize=10)
            ax.set_xlabel('Root-local '+('Z' if row==0 else 'X')+' (m)');ax.set_ylabel('Root-local '+('Y' if row==0 else 'Z')+' (m)')
    fig.suptitle('M4 · Actual CPU-evaluated skinned poses · existing mesh/rig · source geometry unchanged',fontsize=15,weight='bold')
    fig.savefig(output/'cpu_pose_contact_sheet.png',dpi=150);plt.close(fig)
    print('Created CPU pose contact sheet')


if __name__=='__main__':main()
