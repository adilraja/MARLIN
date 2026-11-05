"""Labelled orthographic geometry diagnostics; not RTX render captures."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

BASE = Path(__file__).resolve().parents[1]
record = json.loads((BASE/'baseline/live_before/evaluated_geometry.json').read_text())
points = np.concatenate([np.asarray(m['points_world_m']) for m in record['meshes']])
joints = record['joints_world_m']
fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
for ax, (a, b, title) in zip(axes, [(2, 1, 'Side: Z / Y'), (2, 0, 'Top: Z / X'), (0, 1, 'Front: X / Y')]):
    ax.scatter(points[:, a], points[:, b], s=.55, c='#6c8091', alpha=.45, linewidths=0, rasterized=True)
    for name, p in joints.items():
        parent = name.rsplit('/', 1)[0]
        if parent in joints:
            q = joints[parent]
            ax.plot([p[a], q[a]], [p[b], q[b]], color='#006f86', linewidth=.9)
    for name, p in joints.items():
        if name.rsplit('/', 1)[-1] in ('head_01_2', 'spine_007_12'):
            ax.annotate(name.rsplit('/', 1)[-1], (p[a], p[b]), fontsize=7, xytext=(3, 7), textcoords='offset points')
    root = [0, -.2, 0]
    ax.plot(root[a], root[b], '+', color='#b3442f', markersize=10, label='motion root')
    ax.set(title=title, xlabel='XYZ'[a]+' (m)', ylabel='XYZ'[b]+' (m)')
    ax.set_aspect('equal', adjustable='box')
    ax.grid(alpha=.2)
axes[0].legend(loc='lower left', fontsize=8)
fig.suptitle('Model 61A — saved rest-pose geometry and existing skeleton', fontsize=15)
fig.text(.5, .025, 'CPU evaluation of the frozen baseline; asset joint labels shown. Stage-unit dimensions do not establish biological calibration.', ha='center', fontsize=9)
fig.tight_layout(rect=(0, .07, 1, .93))
out = BASE/'baseline/figures'
out.mkdir(exist_ok=True)
fig.savefig(out/'geometry_views.png', dpi=160)
fig.savefig(out/'geometry_views.svg')
print(out/'geometry_views.png')
