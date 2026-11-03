"""Standalone comparison figures for MAR's material review, from retained data."""
import json
import os
from pathlib import Path
import tempfile

os.environ.setdefault('MPLCONFIGDIR',tempfile.mkdtemp(prefix='marlin_m6_plot_'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'figures'


def contact(analysis,filename,overlay=False):
    fig,axes=plt.subplots(3,2,figsize=(10.5,11.5),constrained_layout=True)
    for row,pose in enumerate(('above','intersecting','below')):
        for col,selection in enumerate(('original','engineering')):
            label=selection+'_'+pose
            path=ROOT/analysis['capture_directories'][label]
            image=np.asarray(Image.open(path/('review_geometric_box.png' if overlay else 'review_log.png')))
            axes[row,col].imshow(image)
            axes[row,col].set_xticks([])
            axes[row,col].set_yticks([])
            if row==0:
                axes[row,col].set_title('Original water' if col==0 else 'Engineering v1 + closed boundary',fontsize=12)
            if col==0:
                axes[row,col].set_ylabel(pose.capitalize(),fontsize=12)
    fig.suptitle('MARLIN — same frozen dolphin, paired water configurations',fontsize=15)
    footer='Fixed log HDR display, log1p(RGB) / log1p(12000); no per-image normalization.'
    footer+=' Yellow: direct projected 3D bounds; no visible-mask claim.' if overlay else ' Camera, lights, animal and top ocean match within each pair.'
    footer+='\nDolphin asset: DigitalLife3D, Model 61A - Bottlenose Dolphin (CC-BY-NC-4.0); original licence retained.'
    fig.supxlabel(footer,fontsize=8)
    fig.savefig(OUT/filename,dpi=150)
    plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True)
    analysis=json.loads((ROOT/'analysis.json').read_text())
    contact(analysis,'material_comparison.png')
    contact(analysis,'geometric_annotation_comparison.png',True)
    figure,axes=plt.subplots(1,3,figsize=(12,4),constrained_layout=True)
    paths=analysis['capture_directories']
    a=np.asarray(Image.open(ROOT/paths['engineering_intersecting']/'hdr_display.png'))
    b=np.asarray(Image.open(ROOT/paths['reload_intersecting']/'hdr_display.png'))
    axes[0].imshow(a);axes[0].set_title('Saved engineering scene')
    axes[1].imshow(b);axes[1].set_title('Fresh-process reload')
    diff=np.abs(a.astype(float)-b.astype(float)).mean(axis=2)
    heat=axes[2].imshow(diff,cmap='magma',vmin=0,vmax=8);axes[2].set_title('Mean absolute RGB difference')
    for axis in axes:
        axis.set_axis_off()
    figure.colorbar(heat,ax=axes[2],label='8-bit primary display values',shrink=.7)
    figure.suptitle('Unchanged M5 fixed-gamma display; native HDR retained',fontsize=11)
    figure.savefig(OUT/'fresh_reload.png',dpi=150)
    plt.close(figure)
    retest=json.loads((ROOT.parent/'m4_driver_5959902/analysis.json').read_text())
    figure,axes=plt.subplots(1,2,figsize=(9,3.6),constrained_layout=True)
    for axis,test in zip(axes,retest['tests']):
        x=np.arange(3)
        axis.bar(x-.18,test['absorption_relative_to_clear_rgb'],.36,label='Measured')
        axis.bar(x+.18,test['beer_prediction_rgb'],.36,label='Expected')
        axis.set(xticks=x,xticklabels=['R','G','B'],ylim=(0,1.1),ylabel='Absorption / clear HDR',
                 title=('Above-water control, 1 m' if test['view']=='above' else 'Inside-water camera, 0.5 m'))
        axis.legend(fontsize=8)
    figure.suptitle('Driver 595.99.02 — inside-camera attenuation defect persisted',fontsize=12)
    figure.savefig(OUT/'driver_retest.png',dpi=160)
    plt.close(figure)


if __name__=='__main__':
    main()
