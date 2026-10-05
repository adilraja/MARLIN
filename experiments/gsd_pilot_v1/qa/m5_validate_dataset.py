"""Validate M5 counts, frozen pairing, captured RGB, visibility and labels."""
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
OUT=EXP/'renders/milestone_5'
NEGATIVE_PARENT_IDS={0,6,12,18,24}
SPECIES=('european_storm_petrel','harbour_porpoise')
GSD=(.5,1.,2.,3.,4.)


def load(path):return json.loads(path.read_text())
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def local_visibility(rgb,box):
    x0,y0,x1,y1=box
    l,t,r,b=max(0,math.floor(x0)),max(0,math.floor(y0)),min(1024,math.ceil(x1)),min(768,math.ceil(y1))
    e=12
    outer=rgb[max(0,t-e):min(768,b+e),max(0,l-e):min(1024,r+e)]
    mask=np.ones(outer.shape[:2],dtype=bool)
    mask[t-max(0,t-e):b-max(0,t-e),l-max(0,l-e):r-max(0,l-e)]=False
    surround=outer[mask]
    background=np.median(surround,axis=0)
    noise=np.max(np.abs(surround-background),axis=1)
    threshold=max(12,int(np.quantile(noise,.99))+5)
    target=np.max(np.abs(rgb[t:b,l:r]-background),axis=2)
    count=int(np.count_nonzero(target>threshold))
    return {'method':'local_12px_surround_median_color_contrast',
            'background_median_rgb':background.tolist(),
            'surround_99pct_max_channel_deviation':float(np.quantile(noise,.99)),
            'threshold_0_255':threshold,'significant_pixels_inside_box':count,
            'max_box_contrast':float(target.max()),
            'detected':bool(count>=5 and target.max()>=20)}


def main():
    entries=load(OUT/'variant_index.json')
    progress=load(OUT/'capture_progress.json')
    m4=load(EXP/'renders/milestone_4/capture_progress.json')
    geometry=load(EXP/'annotations/milestone_5_geometry.json')['records']
    environment=load(EXP/'environment.json')
    if len(entries)!=300 or len(progress)!=280 or len(geometry)!=250:
        raise ValueError('Dataset counts incomplete')
    new={x['checkpoint_id']:x for x in progress}
    old={x['checkpoint_id']:x for x in m4}
    if len(new)!=280:raise ValueError('Duplicate new capture')
    labels={(x['scene_id'],x['gsd_cm_px_requested']):x for x in geometry}
    if len(labels)!=250:raise ValueError('Duplicate geometry label')
    keys={(x['scene_id'],x['requested_gsd_cm_px'],x['intervention']) for x in entries}
    expected={(species+'_%04d'%i,gsd,'target_present')
              for species in SPECIES for i in range(25) for gsd in GSD}
    expected|={(species+'_%04d'%i,gsd,'target_absent')
               for species in SPECIES for i in NEGATIVE_PARENT_IDS for gsd in GSD}
    if keys!=expected or len(keys)!=300:raise ValueError('Wrong scene/GSD/intervention grid')
    checks=[];errors=[];images=[];annotations=[];frames=[]
    image_cache={}
    for image_id,item in enumerate(entries,1):
        try:
            key=(item['scene_id'],item['requested_gsd_cm_px'])
            source=old if item['capture_source']=='milestone_4_reused' else new
            capture=source[item['checkpoint_id']]
            image=EXP/capture['rgb_path']
            if sha(image)!=capture['rgb_sha256']:raise ValueError('Image hash changed')
            with Image.open(image) as im:
                if im.size!=(1024,768):raise ValueError('Image dimensions changed')
                rgb=np.asarray(im.convert('RGB'),dtype=np.float64)
            actual=capture['actual_checkpoint']
            if (actual['camera']!='/World/Cameras/PilotCamera'
                or actual['resolution']!=[1024,768] or actual['fill_frame']
                or actual['renderer_settings']!=environment['renderer_settings']
                or actual['frozen_sampled_attributes']!=0):
                raise ValueError('Actual camera/renderer/frozen state changed')
            if item['capture_source']=='milestone_5_new':
                stage=ROOT/'artifacts/scene_checkpoints'/item['checkpoint_id']/'scene.usdc'
                if sha(stage)!=item['snapshot_sha256']:raise ValueError('USD snapshot changed')
                if capture['settling_probes'][-1]['mean_absolute_rgb_difference_from_previous']>=1:
                    raise ValueError('Renderer did not settle')
            if sha(EXP/'scenes/manifests'/(item['scene_id']+'.json'))!=item['manifest_sha256']:
                raise ValueError('Frozen scene manifest changed')
            image_cache[(item['scene_id'],item['requested_gsd_cm_px'],item['intervention'])]=image
            images.append({'id':image_id,'file_name':capture['rgb_path'],'width':1024,'height':768,
                           'sha256':capture['rgb_sha256'],'scene_id':item['scene_id'],
                           'species':item['species'],'requested_gsd_cm_px':item['requested_gsd_cm_px'],
                           'intervention':item['intervention']})
            frame={'image_id':image_id,'scene_id':item['scene_id'],'species':item['species'],
                   'scene_index':item['scene_index'],'requested_gsd_cm_px':item['requested_gsd_cm_px'],
                   'intervention':item['intervention'],'image_path':capture['rgb_path'],
                   'image_sha256':capture['rgb_sha256'],'snapshot_sha256':item['snapshot_sha256'],
                   'manifest_sha256':item['manifest_sha256'],
                   'biological_manifest_sha256':item['biological_manifest_sha256'],
                   'camera':actual['camera'],'resolution_px':actual['resolution'],
                   'renderer_preset':'gsd_baseline_v1',
                   'actual_timeline_seconds':actual['timeline_seconds'],
                   'renderer_seed':None,'actual_sample_count':None,
                   'capture_source':item['capture_source']}
            if item['intervention']=='target_present':
                label=labels[key]
                if label['manifest_sha256']!=item['manifest_sha256'] or label['biological_manifest_sha256']!=item['biological_manifest_sha256']:
                    raise ValueError('Geometry provenance mismatch')
                if not math.isclose(label['reference_plane_gsd_cm_px'],item['requested_gsd_cm_px'],rel_tol=1e-6):
                    raise ValueError('Actual reference-plane GSD mismatch')
                visibility=local_visibility(rgb,label['amodal_bbox_xyxy_px'])
                frame.update(amodal_bbox_coco_xywh_px=label['amodal_bbox_coco_xywh_px'],
                             bbox_width_px=label['bbox_width_px'],bbox_height_px=label['bbox_height_px'],
                             projected_silhouette_area_px=None,visible_target_area_px=None,
                             target_mean_vertex_depth_gsd_cm_px=label['target_mean_vertex_depth_gsd_cm_px'],
                             camera_projection=label['projection'],visibility=visibility)
                checks.append({'scene_id':item['scene_id'],'gsd_cm_px':item['requested_gsd_cm_px'],
                               'visibility':visibility})
                if not visibility['detected']:
                    errors.append({'scene_id':item['scene_id'],'gsd_cm_px':item['requested_gsd_cm_px'],
                                   'reason':'Target failed local contrast validation; entire scene group rejected pending predefined next candidate'})
                x,y,w,h=label['amodal_bbox_coco_xywh_px']
                annotations.append({'id':len(annotations)+1,'image_id':image_id,
                                    'category_id':1,'bbox':[x,y,w,h],
                                    'area':w*h,'area_semantics':'bbox_area_for_detection_only',
                                    'iscrowd':0,'species':item['species'],
                                    'bbox_semantics':'amodal_direct_evaluated_mesh_projection',
                                    'visibility_validated':visibility['detected']})
            frames.append(frame)
        except Exception as exc:
            errors.append({'scene_id':item['scene_id'],'gsd_cm_px':item['requested_gsd_cm_px'],
                           'intervention':item['intervention'],'reason':str(exc)})
    for species in SPECIES:
        for i in NEGATIVE_PARENT_IDS:
            scene_id=species+'_%04d'%i
            for gsd in GSD:
                on_path=image_cache.get((scene_id,gsd,'target_present'))
                off_path=image_cache.get((scene_id,gsd,'target_absent'))
                if on_path is None or off_path is None:continue
                with Image.open(on_path) as image:on=np.asarray(image.convert('RGB'),dtype=np.int16)
                with Image.open(off_path) as image:off=np.asarray(image.convert('RGB'),dtype=np.int16)
                label=labels[(scene_id,gsd)]
                x0,y0,x1,y1=label['amodal_bbox_xyxy_px']
                l,t,r,b=math.floor(x0),math.floor(y0),math.ceil(x1),math.ceil(y1)
                diff=np.max(np.abs(on-off),axis=2)
                changed=int(np.count_nonzero(diff[t:b,l:r]>5))
                if changed<5:errors.append({'scene_id':scene_id,'gsd_cm_px':gsd,
                                             'reason':'Target-present/absent RGB pair showed under five changed pixels'})
    save(EXP/'qa/m5_dataset_validation.json',
         {'passed':not errors,'images':len(images),'positive_annotations':len(annotations),
          'scene_groups':50,'negative_parent_scene_indices':sorted(NEGATIVE_PARENT_IDS),
          'local_visibility_checks':len(checks),'all_positive_targets_detected':all(x['visibility']['detected'] for x in checks),
          'paired_negative_checks':50,'errors':errors,'checks':checks,
          'limitations':['Local contrast established target presence, not exact visible area.',
                         'Underwater porpoise boxes are direct amodal projections; refraction was not inverted.',
                         'Actual RTX sample counts and bitwise RGB repeatability were not measured.']})
    save(EXP/'annotations/milestone_5_frames.json',{'schema_version':1,'frames':frames})
    save(EXP/'annotations/milestone_5_coco.json',
         {'info':{'description':'MARLIN M5 provisional synthetic pilot; direct amodal boxes',
                  'area_semantics':'COCO area equals bbox area, not projected silhouette/visible area'},
          'licenses':[],'categories':[{'id':1,'name':'wildlife'}],
          'images':images,'annotations':annotations})
    print(json.dumps({'passed':not errors,'images':len(images),'annotations':len(annotations),
                      'errors':len(errors)},indent=2),flush=True)
    if errors:raise ValueError('Dataset validation rejected images; see qa/m5_dataset_validation.json')


if __name__=='__main__':main()
