"""Verify native files, retain fixed HDR displays, and encode review media."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def main(run_id):
    result = json.loads((ROOT/run_id/'result.json').read_text())
    assert result['status']=='passed' and all(result['restoration'].values())
    directory = Path(result['media_directory'])
    plan = json.loads((ROOT/'locked_plan_v3.json').read_text())
    records = []
    for capture in result['captures']:
        folder = directory/capture['label']
        state = json.loads((folder/'state.json').read_text())
        assert sha(folder/'state.json') == capture['state_sha256']
        assert sha(folder/'hdr.npz') == state['hdr_npz_sha256']
        assert sha(folder/'hdr.exr') == state['hdr_exr_sha256']
        assert state['held_exactly_during_capture']
        assert json.loads((folder/'capture_hold_check.json').read_text())['exact']
        settle = json.loads((folder/'settle_check.json').read_text())
        assert settle['exact_commanded_state_held']
        with np.load(folder/'hdr.npz') as archive:
            rgb = archive['rgba'][..., :3].astype(np.float64)
        assert rgb.shape==(384,512,3) and np.isfinite(rgb).all()
        primary = np.rint(255*np.clip(rgb/12000,0,1)**(1/2.2)).astype(np.uint8)
        review_log = np.rint(255*np.clip(np.log1p(np.maximum(rgb,0))/np.log1p(12000),0,1)).astype(np.uint8)
        positive = np.maximum(rgb,0)
        reinhard = np.rint(255*(positive/(1+positive))**(1/2.2)).astype(np.uint8)
        for name, pixels in [('hdr_display.png',primary),('review_log.png',review_log),('review_reinhard.png',reinhard)]:
            path = folder/name
            assert not path.exists(), path
            Image.fromarray(pixels).save(path)
        exr = subprocess.check_output(['file', '-b', str(folder/'hdr.exr')], text=True)
        assert 'OpenEXR' in exr and 'dataWindow: (0 0)-(511 383)' in exr, exr
        records.append(dict(label=capture['label'],simulation_time_s=state['simulation_time_s'],
            state=state['frame']['agent']['behavioural_state'],phase=state['pose_controls']['phase'],
            primary_min=int(primary.min()),primary_max=int(primary.max()),
            review_std=float(reinhard.std()),hdr_max=float(rgb.max()),
            exr=exr.strip(), snapshot=capture['snapshot'],
            ui_metadata_changed_during_settle=settle['commanded']['projection']!=settle['settled']['projection']))
        write(folder/'display_conversion.json',dict(native_source='hdr.npz',source_sha256=sha(folder/'hdr.npz'),
            primary_formula=plan['capture']['primary_display'],log_formula=plan['capture']['review_display'],
            review_formula=plan['capture']['additional_review_display'],
            domain='Derived displays of native HdrColor; no native LDR qualification, radiometric calibration or per-image normalization',
            outputs={name:sha(folder/name) for name in ['hdr_display.png','review_log.png','review_reinhard.png']}))
    analysis=dict(passed=True,run_id=run_id,captures=len(records),frames=records,
        no_per_image_normalization=True,rgb_identity_claimed=False,
        ui_cache_settle_changes=sum(r['ui_metadata_changed_during_settle'] for r in records))
    if run_id==plan['primary_run']:
        fps=plan['video']['fps']
        review_frames=directory/'review_frames'
        review_frames.mkdir(exist_ok=False)
        font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',13)
        for index in range(plan['video']['frames']):
            folder=directory/f'frame_{index:05d}'
            state=json.loads((folder/'state.json').read_text())
            image=Image.open(folder/'review_reinhard.png').convert('RGB')
            draw=ImageDraw.Draw(image)
            draw.rectangle((0,0,511,42),fill=(5,12,20))
            draw.text((8,3),f'M5 full sequence | t={state["simulation_time_s"]:05.2f} s | {state["frame"]["agent"]["behavioural_state"]}',font=font,fill=(240,245,250))
            draw.text((8,23),f'phase={state["pose_controls"]["phase"]:.3f} | weight={state["pose_controls"]["weight"]:.3f} | existing cycle',font=font,fill=(255,206,90))
            draw.rectangle((0,364,511,383),fill=(5,12,20))
            draw.text((8,366),'Fixed HDR display | 5 fps, normal speed | engineering demo',font=font,fill=(240,245,250))
            image.save(review_frames/f'video_{index:05d}.png')
        movie=directory/'full_sequence_74s.mp4'
        assert not movie.exists()
        command=['ffmpeg','-hide_banner','-loglevel','error','-framerate',str(fps),'-i',str(review_frames/'video_%05d.png'),
                 '-frames:v',str(plan['video']['frames']),'-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-r',str(fps),'-movflags','+faststart',str(movie)]
        encoded=subprocess.run(command,capture_output=True,text=True)
        write(ROOT/(run_id+'_ffmpeg.json'),dict(command=command,returncode=encoded.returncode,stdout=encoded.stdout,stderr=encoded.stderr))
        assert encoded.returncode==0
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate,duration,nb_frames','-of','json',str(movie)],text=True))['streams'][0]
        assert int(probe['nb_frames'])==370 and abs(float(probe['duration'])-74)<1e-6
        assert probe['avg_frame_rate']=='5/1'
        analysis.update(movie=str(movie.relative_to(REPO)),movie_sha256=sha(movie),ffprobe=probe)
        snapshots=[r for r in records if r['snapshot'] and not r['label'].startswith('reorder_')]
        assert len(snapshots)==23
        sheet=Image.new('RGB',(1280,6*265+60),(248,250,252))
        d=ImageDraw.Draw(sheet)
        d.text((12,6),'M5 | 23 predeclared frozen states | fixed Reinhard HDR display',font=font,fill=(10,25,40))
        for i,record in enumerate(snapshots):
            tile=Image.open(directory/record['label']/'review_reinhard.png').convert('RGB').resize((320,240))
            x,y=(i%4)*320,35+(i//4)*265
            sheet.paste(tile,(x,y))
            d.text((x+5,y+241),f't={record["simulation_time_s"]:05.2f} s | {record["state"]}',font=font,fill=(10,25,40))
        figures=ROOT/'figures';figures.mkdir(exist_ok=True)
        path=figures/'frozen_state_contact_sheet.png'
        assert not path.exists();sheet.save(path)
        analysis['contact_sheet']=str(path.relative_to(REPO))
    write(ROOT/(run_id+'_media_analysis.json'),analysis)
    print(json.dumps({k:v for k,v in analysis.items() if k!='frames'},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('run_id',choices=['smoke03','primary02','fresh01'])
    main(parser.parse_args().run_id)
