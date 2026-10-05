"""Audit actual five-GSD RGB pairs, direct mesh labels and target visibility."""
import hashlib
import json
import math
from pathlib import Path
import sys
sys.dont_write_bytecode=True
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[3]
EXP=ROOT/'experiments/gsd_pilot_v1'
OUT=EXP/'renders/milestone_4'


def load(path):return json.loads(path.read_text())
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def validate():
    index=load(OUT/'variant_index.json')
    progress=load(OUT/'capture_progress.json')
    geometry=load(EXP/'annotations/milestone_4_geometry.json')['records']
    environment=load(EXP/'environment.json')
    if len(index)!=20 or len(progress)!=20 or len(geometry)!=10:
        raise ValueError('Pilot must contain 10 complete positive/negative pairs')
    captures={x['checkpoint_id']:x for x in progress}
    if len(captures)!=20 or set(captures)!={x['checkpoint_id'] for x in index}:
        raise ValueError('Missing or duplicate capture')
    labels={(x['scene_id'],x['gsd_cm_px_requested']):x for x in geometry}
    if len(labels)!=10:raise ValueError('Duplicate mesh label')
    images=[];annotations=[];checks=[];image_id=0
    for target in ('european_storm_petrel','harbour_porpoise'):
        scene_id=target+'_0000'
        for gsd in (.5,1.,2.,3.,4.):
            pair=[x for x in index if x['scene_id']==scene_id and x['requested_gsd_cm_px']==gsd]
            if {x['intervention'] for x in pair}!={'target_present','target_absent'}:
                raise ValueError('Incomplete intervention pair')
            a,b=sorted(pair,key=lambda x:x['intervention']!='target_present')
            on,off=captures[a['checkpoint_id']],captures[b['checkpoint_id']]
            label=labels[(scene_id,gsd)]
            rgb=[]
            for item,record in ((a,on),(b,off)):
                image=EXP/record['rgb_path']
                if sha(image)!=record['rgb_sha256']:raise ValueError('RGB hash changed')
                if sha(EXP/item['snapshot'])!=item['snapshot_sha256']:
                    raise ValueError('USD snapshot hash changed')
                actual=record['actual_checkpoint']
                if (actual['camera']!='/World/Cameras/PilotCamera' or actual['resolution']!=[1024,768]
                    or actual['fill_frame'] or actual['renderer_settings']!=environment['renderer_settings']):
                    raise ValueError('Actual viewport/renderer differs from declared capture')
                probes=record['settling_probes']
                if len(probes)<3 or probes[-1]['mean_absolute_rgb_difference_from_previous']>=1:
                    raise ValueError('Renderer had not settled')
                with Image.open(image) as im:
                    if im.size!=(1024,768):raise ValueError('Captured dimensions changed')
                    rgb.append(np.asarray(im.convert('RGB'),dtype=np.int16))
            difference=np.max(np.abs(rgb[0]-rgb[1]),axis=2)
            x0,y0,x1,y1=label['amodal_bbox_xyxy_px']
            left,top,right,bottom=max(0,math.floor(x0)),max(0,math.floor(y0)),min(1024,math.ceil(x1)),min(768,math.ceil(y1))
            region=difference[top:bottom,left:right]
            outside=np.ones((768,1024),dtype=bool)
            outside[max(0,top-10):min(768,bottom+10),max(0,left-10):min(1024,right+10)]=False
            background=difference[outside]
            # A fixed 5/255 floor exceeds the observed 1-2/255 background
            # drift; retain the empirical background maximum for review.
            threshold=max(5,int(np.quantile(background,.999))+3)
            changed=region>threshold
            ys,xs=np.nonzero(changed)
            changed_count=int(changed.sum())
            detected=changed_count>=5 and int(region.max())>=20
            if not detected:raise ValueError('Target not detectable: '+scene_id+' '+str(gsd))
            observed=[int(left+xs.min()),int(top+ys.min()),int(left+xs.max()+1),int(top+ys.max()+1)]
            check={'scene_id':scene_id,'species':target,'requested_gsd_cm_px':gsd,
                   'positive_image_sha256':on['rgb_sha256'],'negative_image_sha256':off['rgb_sha256'],
                   'background_max_channel_difference_outside_10px_label_margin':int(background.max()),
                   'difference_threshold_0_255':threshold,
                   'significantly_changed_pixels_inside_amodal_bbox':changed_count,
                   'max_channel_difference_inside_amodal_bbox':int(region.max()),
                   'change_bbox_within_amodal_label_xyxy_px':observed,
                   'target_detected_in_paired_rgb':detected,
                   'visible_target_area_px':None,
                   'visible_target_area_reason':'Paired RGB change is evidence of visibility, not an exact occlusion/refraction segmentation.',
                   'direct_projection_underwater_limitation':target=='harbour_porpoise'}
            checks.append(check)
            for item,record in ((a,on),(b,off)):
                image_id+=1
                images.append({'id':image_id,'file_name':record['rgb_path'],'width':1024,'height':768,
                               'scene_id':scene_id,'species':target,'requested_gsd_cm_px':gsd,
                               'intervention':item['intervention'],'sha256':record['rgb_sha256']})
                if item['intervention']=='target_present':
                    x,y,w,h=label['amodal_bbox_coco_xywh_px']
                    annotations.append({'id':len(annotations)+1,'image_id':image_id,'category_id':1,
                                        'bbox':[x,y,w,h],
                                        'area':w*h,'area_semantics':'bbox_area_for_detection_only; not silhouette or visible area',
                                        'iscrowd':0,'species':target,
                                        'bbox_semantics':'amodal_direct_evaluated_mesh_projection',
                                        'visibility_evidence':check['target_detected_in_paired_rgb']})
            print(scene_id,gsd,'detected pixels',changed_count,flush=True)
    save(EXP/'annotations/milestone_4_coco.json',
         {'info':{'description':'MARLIN M4 bounded pilot: direct amodal mesh boxes; bbox area only',
                  'bbox_convention':'COCO xywh at pixel edges; top-left image origin',
                  'underwater_limitation':'Refraction can displace apparent visible bounds; direct amodal labels require downstream evaluation.'},
          'licenses':[],'categories':[{'id':1,'name':'wildlife'}],
          'images':images,'annotations':annotations})
    save(EXP/'qa/m4_capture_validation.json',
         {'passed':True,'positive_images':10,'negative_images':10,'species_count':2,
          'gsd_levels_cm_px':[.5,1.,2.,3.,4.],
          'visibility_method':'Paired target-present/absent RGB difference; threshold above background drift inside exact direct mesh box.',
          'bbox_semantics':'direct amodal evaluated mesh projection',
          'silhouette_and_exact_visible_area_status':'unknown; not replaced with bbox area',
          'checks':checks})


if __name__=='__main__':validate()
