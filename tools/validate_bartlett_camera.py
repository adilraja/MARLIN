"""Compute full-resolution GSD maps without changing Kit or fitting parameters."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT/'source/extensions/cris.madil.render_service/config'
sys.path.insert(0,str(CONFIG.parent/'cris/madil/render_service'))
from bartlett_geometry import validate, nominal, maps_chunk, footprint, footprint_gaps


def heatmaps(out,roll,c,maps,stats):
    canvas=Image.new('RGB',(1160,1080),'white');draw=ImageDraw.Draw(canvas)
    draw.text((24,12),f'Flat-plane reconstruction | pitch {c["pitch_from_nadir_deg"]} deg | inferred roll {roll} deg',fill='black')
    for i,(name,values) in enumerate(maps.items()):
        y=45+i*255
        low,high=stats[name]['simulated_min'],stats[name]['simulated_max']
        normalized=np.nan_to_num((values[::8,::8]-low)/max(high-low,1e-12))
        def colors(t):
            return (np.stack([np.clip(2*t,0,1),np.clip(2-2*np.abs(t-.5),0,1),np.clip(2-2*t,0,1)],axis=-1)*255).astype('uint8')
        img=Image.fromarray(colors(normalized)).resize((985,180))
        canvas.paste(img,(65,y+25))
        bar=Image.fromarray(colors(np.linspace(1,0,180)[:,None])).resize((20,180))
        canvas.paste(bar,(1070,y+25))
        draw.text((65,y),name.replace('_',' '),fill='black')
        draw.text((1095,y+25),f'{high:.4f}',fill='black');draw.text((1095,y+190),f'{low:.4f}',fill='black')
        draw.text((22,y+25),'0',fill='black');draw.text((15,y+190),str(c['image_height_px']),fill='black')
        draw.text((65,y+212),'0',fill='black');draw.text((500,y+212),'image column (row increases downward)',fill='black')
        draw.text((1010,y+212),str(c['image_width_px']),fill='black')
    canvas.save(out/f'roll_{roll}_maps.png')


def footprint_plot(out,footprints):
    allp=np.vstack([f['corners_xz_m'] for f in footprints])
    low,high=allp.min(axis=0),allp.max(axis=0)
    scale=min(1000/(high[0]-low[0]),320/(high[1]-low[1]))
    canvas=Image.new('RGB',(1160,470),'white');draw=ImageDraw.Draw(canvas)
    draw.text((25,10),'Four-camera footprints | common optical centre | no fitted gaps | X/Z in metres',fill='black')
    palette=['#6622aa','#0066cc','#008844','#cc5500']
    for index,(f,color) in enumerate(zip(footprints,palette)):
        p=np.asarray(f['corners_xz_m'])
        q=[(60+(x-low[0])*scale,380-(z-low[1])*scale) for x,z in p]
        draw.line(q+[q[0]],fill=color,width=3)
        draw.text((40+index*270,420),f"roll {f['roll_deg']} deg",fill=color)
    for t in np.linspace(0,1,5):
        x=low[0]+t*(high[0]-low[0]);z=low[1]+t*(high[1]-low[1])
        draw.text((60+(x-low[0])*scale,390),f'{x:.1f}',fill='black')
        draw.text((5,380-(z-low[1])*scale),f'{z:.1f}',fill='black')
    canvas.save(out/'footprints.png')


def run(geometry_path,targets_path):
    c = json.loads(geometry_path.read_text())
    validate(c)
    base = ROOT/'artifacts/camera_validation'
    base.mkdir(parents=True,exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='bartlett_',dir=base))
    (out/'geometry_inputs.json').write_text(json.dumps(c,indent=2)+'\n')
    cases=[]
    for roll in c['rolls_deg']:
        maps={}
        stats={}
        for start in range(0,c['image_height_px'],64):
            stop=min(start+64,c['image_height_px'])
            chunk=maps_chunk(c,roll,start,stop)
            for name,values in chunk.items():
                if name not in maps:
                    maps[name]=np.lib.format.open_memmap(out/f'roll_{roll}_{name}.npy',mode='w+',dtype='float32',shape=(c['image_height_px'],c['image_width_px']))
                    stats[name]={'simulated_min':float('inf'),'simulated_max':float('-inf')}
                maps[name][start:stop]=values
                stats[name]['simulated_min']=min(stats[name]['simulated_min'],float(np.nanmin(values)))
                stats[name]['simulated_max']=max(stats[name]['simulated_max'],float(np.nanmax(values)))
        for values in maps.values(): values.flush()
        heatmaps(out,roll,c,maps,stats)
        cases.append({'roll_deg':roll,**stats,'footprint':footprint(c,roll)})
        del maps
    # Geometry is complete BEFORE loading published numerical targets.
    targets=json.loads(targets_path.read_text())
    (out/'comparison_targets.json').write_text(json.dumps(targets,indent=2)+'\n')
    for case in cases:
        target=next(t for t in targets['cases'] if t['roll_deg']==case['roll_deg'])
        for name in ('gsd_width_cm_px','gsd_height_cm_px'):
            for end,published in zip(('min','max'),target[name]):
                value=case[name]['simulated_'+end]
                case[name]['published_'+end]=published
                case[name]['absolute_error_'+end]=abs(value-published)
                case[name]['relative_error_'+end]=abs(value-published)/published
    footprints=[footprint(c,r) for r in sorted([-r for r in c['rolls_deg']]+c['rolls_deg'])]
    footprint_plot(out,footprints)
    report={'schema_version':'1.0.0','inputs':c,'input_sha256':hashlib.sha256(geometry_path.read_bytes()).hexdigest(),
            'parameter_fitting':False,'nominal_nadir_gsd_width_height_cm_px':nominal(c),
            'map_sampling':'Full resolution. Forward pixel-centre neighbour spacing; width last column and height last row are NaN. Area uses pixel-edge quadrilaterals.',
            'storage':'float32 .npy maps; extrema/comparisons calculated in float64; plots subsampled every 8 pixels',
            'anisotropy_definition':'height / width, not averaged GSD; not necessarily >=1',
            'cases':cases,'array_footprints':footprints,'footprint_gaps':footprint_gaps(footprints),
            'published_gap_description':targets['published_gap_description'],
            'conclusion':'Independent reconstruction, not a deployment calibration. Differences are reported, not fitted away.',
            'unresolved':['deployed camera identity','ROI versus binning','ROI origin','exact rotation composition and yaw','physical camera baselines and measured mount angles','historical barometric altitude to sea reference','lens intrinsics and distortion']}
    (out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'directory':str(out),'cases':cases,'gaps':report['footprint_gaps']},indent=2))
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--geometry',type=Path,default=CONFIG/'bartlett_geometry_v1.json')
    p.add_argument('--targets',type=Path,default=CONFIG/'bartlett_validation_targets_v1.json')
    a=p.parse_args();run(a.geometry,a.targets)
