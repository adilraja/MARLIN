"""Review capture/replay pixels and maps, without biological detectability claims.

Requires NumPy and Pillow. Does not alter capture images or metadata.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def review(original, replay):
    a=json.loads((original/'metadata.json').read_text())
    b=json.loads((replay/'metadata.json').read_text())
    rgb_a=np.array(Image.open(original/'rgb.png').convert('RGB'))
    rgb_b=np.array(Image.open(replay/'rgb.png').convert('RGB'))
    shape=(a['config']['image_height_px'],a['config']['image_width_px'])
    checks=dict(original_restored=a['main_viewport_preserved'],replay_restored=b['main_viewport_preserved'],
                replay_link=b['replay_of']==a['capture_id'],
                image_dimensions=rgb_a.shape==rgb_b.shape==(*shape,3),
                camera_identical=a['camera_position_m']==b['camera_position_m'] and a['actual_projection_matrix']==b['actual_projection_matrix'],
                scene_file_identical=a['scene_sha256']==b['scene_sha256'])
    for directory,meta in ((original,a),(replay,b)):
        for filename,expected in meta['output_sha256'].items():
            actual=hashlib.sha256((directory/filename).read_bytes()).hexdigest()
            checks[directory.name+'/'+filename+'_hash']=actual==expected
    with np.load(original/'directional_gsd.npz') as ma,np.load(replay/'directional_gsd.npz') as mb:
        for key in ma.files:
            checks[key+'_repeatable']=np.array_equal(ma[key],mb[key],equal_nan=True)
            checks[key+'_shape']=ma[key].shape==shape
        checks['image_not_blank']=float(rgb_a.std())>2 and float(rgb_a.max()-rgb_a.min())>20
        delta=np.abs(rgb_a.astype(float)-rgb_b.astype(float))
        metrics=dict(mean_absolute_rgb_error_0_255=float(delta.mean()),
                     max_absolute_rgb_error_0_255=float(delta.max()),
                     fraction_channels_identical=float((delta==0).mean()))
        # Engineering replay tolerance, not a wildlife detection criterion.
        checks['replay_mean_pixel_error_le_2']=metrics['mean_absolute_rgb_error_0_255']<=2
        image_height=round(1200*shape[0]/shape[1])
        row_height=image_height+80
        panel=Image.new('RGB',(1280,70+3*row_height),'white')
        draw=ImageDraw.Draw(panel)
        try:
            font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',21)
        except OSError:
            font=ImageFont.load_default()
        label='Sony provisional' if a.get('camera_model')=='Sony ILX-LR1' else 'HiDef'
        draw.text((30,15),'%s: pitch %.2f° from nadir; roll %.2f°; %d × %d preview'%(
            label,a['config']['pitch_deg'],a['config']['roll_deg'],shape[1],shape[0]),fill='black',font=font)
        for i,(filename,title,key) in enumerate((('rgb.png','Captured RGB (uncalibrated animals)',None),
            ('gsd_width_cm_px.png','Image-width direction — flat reference sea plane','gsd_width_cm_px'),
            ('gsd_height_cm_px.png','Image-height direction — flat reference sea plane','gsd_height_cm_px'))):
            top=60+i*row_height
            draw.text((30,top),title,fill='black',font=font)
            with Image.open(original/filename) as im:
                panel.paste(im.convert('RGB').resize((1200,image_height)),(30,top+35))
            if key:
                lo,hi=float(np.nanmin(ma[key])),float(np.nanmax(ma[key]))
                draw.text((30,top+image_height+40),'Blue %.4f  →  yellow %.4f cm/preview pixel; black = invalid edge'%(lo,hi),fill='black',font=font)
        panel.save(original/'review.png')
    report=dict(status='passed' if all(checks.values()) else 'failed',checks=checks,
                original=a['capture_id'],replay=b['capture_id'],pixel_comparison=metrics,
                biological_detectability_tested=False,
                caveats=['Some animals intersect frame edges; this is not a claim that every specimen fits wholly inside the image.',
                         'Water appearance is the saved demonstration material and lighting, not a validated controlled-survey environment.',
                         'External runtime MDL dependencies are not bundled. Same runtime and unchanged local texture files are required.',
                         'Not a native-resolution image; directional preview GSD is recorded separately.',
                         'Image non-blank and replay similarity checks do not prove biological realism or visibility through water.'])
    (original/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original',type=Path)
    parser.add_argument('replay',type=Path)
    args=parser.parse_args()
    raise SystemExit(0 if review(args.original,args.replay)['status']=='passed' else 1)
