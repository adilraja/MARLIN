"""Validate retained native PNGs, label normal-speed clips, build review sheets."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
os.environ.setdefault('MPLCONFIGDIR','/tmp/marlin_m4_matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[3]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def srt_time(seconds):
    ms=round(seconds*1000);return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}'


def main():
    summaries=[];figures=ROOT/'figures';figures.mkdir(exist_ok=True)
    for name in ('dry02','review01'):
        result=json.loads((ROOT/'native_runs'/name/'result.json').read_text());assert result['status']=='passed' and all(result['restoration'].values())
        directory=Path(result['media_directory']);records=[];stats=[]
        for frame in result['frames']:
            p=directory/frame['file'];assert sha(p)==frame['sha256']
            image=Image.open(p).convert('RGB');assert image.size==(512,384)
            values=np.asarray(image);assert values.max()!=values.min(),'Flat frame cannot support visual review: '+str(p)
            metadata=json.loads(p.with_suffix('.json').read_text())
            assert metadata['sha256']==sha(p)
            assert metadata['projection']['render_product']['resolution']==[512,384]
            assert len(metadata['joint_rotations'])==len(metadata['joint_translations'])==len(metadata['joint_scales'])==20
            if name=='review01':assert metadata['camera_above_surface_bounds']
            records.append((frame,metadata));stats.append(dict(file=p.name,min=int(values.min()),max=int(values.max()),std=float(values.std())))
        clip=[(f,m) for f,m in records if f['file'].startswith('clip_')];assert len(clip)==300
        subtitles=directory/'review_subtitles.srt';assert not subtitles.exists()
        lines=[];label='DRY GEOMETRY DIAGNOSTIC' if name=='dry02' else 'ENGINEERING WATER / ABOVE-WATER CAMERA'
        for i,(f,m) in enumerate(clip):
            controls=m['pose_controls'];caption=f'{label}\nt={f["simulation_time_s"]:.2f} s | {f["state"]} | phase={controls["phase"]:.3f} | weight={controls["weight"]:.3f}\n1x simulation speed; labelled edited windows'
            lines.append(f'{i+1}\n{srt_time(i/10)} --> {srt_time((i+1)/10)}\n{caption}\n')
        subtitles.write_text('\n'.join(lines))
        movie=directory/'review_30s.mp4';assert not movie.exists()
        filter_text="subtitles="+str(subtitles)+":force_style='FontName=DejaVu Sans,Fontsize=11,Outline=1,Shadow=0,Alignment=2,MarginV=5'"
        command=['ffmpeg','-hide_banner','-loglevel','warning','-n','-framerate','10','-i',str(directory/'clip_%05d.png'),'-frames:v','300','-vf',filter_text,'-c:v','libx264','-threads','2','-preset','fast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(movie)]
        p=subprocess.run(command,capture_output=True,text=True,timeout=180)
        (ROOT/(name+'_ffmpeg.json')).write_text(json.dumps(dict(command=command,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr),indent=2)+'\n');assert p.returncode==0,p.stderr
        probe=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate,nb_frames,duration','-of','json',str(movie)],capture_output=True,text=True,check=True)
        stream=json.loads(probe.stdout)['streams'][0];assert (stream['width'],stream['height'],stream['avg_frame_rate'],stream['nb_frames'])==(512,384,'10/1','300') and abs(float(stream['duration'])-30)<1e-6
        times=[6,16,30,42 if name=='dry02' else 38,56,6.625 if name=='dry02' else 70]
        fig,axes=plt.subplots(6,3,figsize=(14,19),constrained_layout=True)
        for row,t in enumerate(times):
            for column,view in enumerate(('top','oblique','close')):
                f,m=next((f,m) for f,m in records if f['file'].startswith('shot_') and f['simulation_time_s']==t and f['view']==view)
                axes[row,column].imshow(Image.open(directory/f['file']));axes[row,column].axis('off')
                axes[row,column].set_title(f'{view} | t={t:g} s | {f["state"]}\nphase={m["pose_controls"]["phase"]:.3f}, weight={m["pose_controls"]["weight"]:.3f}',fontsize=10)
        fig.suptitle('M4 · '+label+' · native 512×384 frames\nExisting asset/material; cyclic body mapping; manoeuvre-specific poses limited',fontsize=15,weight='bold')
        contact=figures/(name+'_native_contact_sheet.png');fig.savefig(contact,dpi=140);plt.close(fig)
        summaries.append(dict(job=name,passed=True,native_frames=len(records),all_frames_nonflat=True,all_pose_joint_arrays_complete=True,clip_frames=300,clip_duration_s=30,clip_fps=10,
            movie=str(movie.relative_to(REPO)),movie_sha256=sha(movie),movie_bytes=movie.stat().st_size,ffprobe=stream,
            contact_sheet=str(contact.relative_to(REPO)),contact_sheet_sha256=sha(contact),min_sampled_free_gpu_mib=min(x['free_mib'] for x in result['gpu']),pixel_statistics=stats))
    output=ROOT/'native_media_analysis.json';assert not output.exists();output.write_text(json.dumps(dict(passed=True,candidates=summaries,manual_review='Pending named Gate C review; pixel nonflatness is not animal/biological or deformation acceptance.'),indent=2)+'\n')
    print(json.dumps(dict(passed=True,candidates=[{k:v for k,v in s.items() if k in ('job','native_frames','movie','movie_bytes','clip_duration_s')} for s in summaries])))


if __name__=='__main__':main()
