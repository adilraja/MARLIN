"""Validate integration evidence and describe HDR target observations."""
from collections import deque
import json
from pathlib import Path
import sys
import hashlib
import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent/'m3/qa'))
from validate_final import exr_dimensions


def component(array):
    # Descriptive measurement chosen after inspection, not a retroactive
    # replacement for the declared geometry/controller acceptance tolerances.
    mask=array[...,:3].min(axis=2)>2000
    keep=np.zeros(mask.shape,dtype=bool);keep[50:320,128:384]=True;mask &= keep
    seen=np.zeros(mask.shape,dtype=bool);components=[]
    for y,x in zip(*np.where(mask)):
        if seen[y,x]:continue
        todo=deque([(int(y),int(x))]);seen[y,x]=True;pixels=[]
        while todo:
            y,x=todo.popleft();pixels.append((y,x))
            for ny,nx in ((y-1,x),(y+1,x),(y,x-1),(y,x+1)):
                if 0<=ny<384 and 0<=nx<512 and mask[ny,nx] and not seen[ny,nx]:
                    seen[ny,nx]=True;todo.append((ny,nx))
        if len(pixels)>=50:components.append(pixels)
    if not components:return {'observable':False}
    pixels=max(components,key=len);yy,xx=zip(*pixels);a=array[np.array(yy),np.array(xx),:3]
    return {'observable':True,'area_px':len(pixels),
            'centroid_px':[float(np.mean(xx)+.5),float(np.mean(yy)+.5)],
            'mean_rgb':a.mean(axis=0).astype(float).tolist()}


def main():
    rows=json.loads((ROOT/'qa/capture_execution.json').read_text())
    assert len(rows)==12 and all(r['response']['ok'] for r in rows)
    measurements=[]
    for row in rows:
        d=Path(row['response']['directory']);m=json.loads((d/'metadata.json').read_text())
        assert m['scene_sha256']==hashlib.sha256((d/'scene.usdc').read_bytes()).hexdigest()
        assert m['viewport_resolution']==[512,384] and m['actual_viewport_resolution']==[512,384]
        assert m['gpu_before']['free_mib']>=768
        assert exr_dimensions(d/'hdr.exr')==(512,384)
        for f in ('rgb.png','warmup.png'):
            with Image.open(d/f) as im:assert im.size==(512,384);im.verify()
        a=np.load(d/'hdr.npz',allow_pickle=False)['rgba'];assert a.shape==(384,512,4) and np.isfinite(a).all()
        e=json.loads((d/'effective_settings.json').read_text())
        assert e['render_product']['omni:rtx:rendermode']=='PathTracing'
        assert e['render_product']['omni:rtx:fog:enabled']=='False'
        assert e['render_product']['omni:rtx:pt:fireflyFilter:enabled']=='False'
        assert e['camera']['omni:rtx:autoExposure:enabled']=='False'
        expected='/World/Looks/OceanWaterEngineeringV1' if row['request']['selection']=='engineering_v1' else '/World/Looks/OceanWater'
        assert m['material']==expected
        g=m['integrated_geometry']
        if row['request']['selection']=='engineering_v1':
            assert g['points']==17154 and g['faces']==17408
            assert g['boundary_edges']==g['nonmanifold_edges']==g['same_direction_shared_edges']==0
            assert g['minimum_top_normal_y']>0 and g['minimum_outward_side_dot']>0 and g['maximum_bottom_normal_y']<0
        restoration=json.loads((d/'restoration.json').read_text())
        assert all(restoration['ocean_root_attributes_restored'].values())
        assert all(v for k,v in restoration.items() if k!='ocean_root_attributes_restored')
        primary=row['request']['view'] in ('nadir','oblique')
        observation=component(a) if primary else {'not_a_primary_target_view':True}
        if primary:assert observation['observable']
        measurements.append({'request':row['request'],'directory':str(d.relative_to(ROOT)),
            'effective_phase_seconds':m['effective_phase_seconds'],'material':m['material'],
            'target_observation':observation,'geometry_and_transaction_checks_passed':True})
    for view in ('nadir','oblique'):
        pair=[r for r in rows if r['request']['view']==view and r['request']['phase_seconds']==0 and not r['request'].get('advance_live')]
        assert len(pair)==2
        a,b=[r['response']['metadata'] for r in pair]
        assert a['config']==b['config']
        np.testing.assert_allclose(a['capture_view_matrix'],b['capture_view_matrix'],atol=1e-8)
        np.testing.assert_allclose(a['capture_projection_matrix'],b['capture_projection_matrix'],atol=1e-8)
    live=rows[-1]['response']['metadata']['live_frames']
    assert len(live)==10 and len({x['elapsed'] for x in live})>1
    assert all(x['binding']=='/World/Looks/OceanWaterEngineeringV1' and x['points']==17154 for x in live)
    inside=rows[8];d=Path(inside['response']['directory']);a=np.load(d/'hdr.npz')['rgba']
    inside_rgb=a[184:200,248:264,:3].mean(axis=(0,1)).astype(float).tolist()
    result={'data_and_geometry_checks_passed':True,'successful_capture_requests':12,
        'primary_above_water_captures':9,'above_water_target_observations_passed':True,
        'measurement_protocol':'Descriptive post-run HDR minimum-channel>2000, fixed ROI, four-connected components; no new optical acceptance threshold',
        'measurements':measurements,'live_update_samples':live,
        'camera_inside_probe':{'target_roi_mean_rgb':inside_rgb,'chromatic_attenuation_demonstrated':False,
            'qualification':'Camera-inside rendering remained unqualified; no supported initial-medium control established'},
        'full_milestone_complete':False,'status':'above_water_integration_passed_with_unresolved_camera_inside_attenuation'}
    (ROOT/'qa/integration_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('measurements','live_update_samples')},indent=2))
    comparisons=ROOT/'comparisons';comparisons.mkdir(exist_ok=True)
    def picture(index):
        a=np.load(Path(rows[index]['response']['directory'])/'hdr.npz')['rgba'][...,:3]
        return Image.fromarray(np.uint8(np.clip(np.log1p(np.maximum(a,0))/np.log1p(12000),0,1)*255))
    def montage(indices,columns,name):
        height=(len(indices)+columns-1)//columns
        canvas=Image.new('RGB',(columns*512,height*420+36),'#10202a');draw=ImageDraw.Draw(canvas)
        draw.text((12,10),'HDR previews: identical log1p(RGB)/log1p(12000) display scale; no per-image exposure',fill='white')
        for k,index in enumerate(indices):
            x=k%columns*512;y=k//columns*420+36;q=rows[index]['request']
            label=f"{q['selection']}; {q['view']}; phase {q['phase_seconds']} s"
            if q.get('advance_live'):label+='; live advance'
            draw.text((x+8,y+8),label,fill='white');canvas.paste(picture(index),(x,y+36))
        canvas.save(comparisons/name)
    montage([0,2,1,3],2,'frozen_original_candidate.png')
    montage([3,4,5,6,7,11],2,'animated_phase_sequence.png')
    montage([8,9,10],1,'inside_exit_edge_probes.png')


if __name__=='__main__':main()
