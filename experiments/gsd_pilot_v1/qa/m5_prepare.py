"""Prepare the 300-image M5 dataset without duplicating generated USD in Git.

The M3 manifests and environment are canonical. Materialized Kit checkpoints
are reproducible local artifacts, indexed with hashes. M4 scene-0000 captures
are reused byte-for-byte.
"""
import hashlib
import json
from pathlib import Path
import shutil
import sys
sys.dont_write_bytecode=True
import numpy as np
from pxr import UsdGeom

ROOT=Path(__file__).resolve().parents[3]
EXP=ROOT/'experiments/gsd_pilot_v1'
OUT=EXP/'renders/milestone_5'
BASE=ROOT/'artifacts/gsd_pilot_v1_m5/base_scenes'
CHECKPOINTS=ROOT/'artifacts/scene_checkpoints'
sys.path.insert(0,str(EXP/'scenes'))
import build_scenes as builder
import sampling
from build_scenes import CAMERA,TARGET,make_scene,open_private,set_camera,sha,save,points,biological_record

NEGATIVE_PARENT_IDS=(0,6,12,18,24)
SPECIES=('european_storm_petrel','harbour_porpoise')


def frozen_sampler_root():
    """Validate M3 manifests against their original 1.2 protocol bytes."""
    folder=ROOT/'artifacts/gsd_pilot_v1_m5/frozen_sampler_input'
    (folder/'wildlife').mkdir(parents=True,exist_ok=True)
    shutil.copy2(EXP/'history/milestone_3/specification.json',folder/'specification.json')
    for species in SPECIES:
        shutil.copy2(EXP/'wildlife'/(species+'.json'),folder/'wildlife'/(species+'.json'))
    return folder


def base_scene(manifest,environment,m3_snapshots):
    scene_id=manifest['scene_id']
    if scene_id in m3_snapshots:
        item=m3_snapshots[scene_id]
        path=EXP/item['snapshot']
        if sha(path)!=item['sha256']:raise ValueError('M3 snapshot changed')
        return path,item['sha256']
    folder=BASE/scene_id;folder.mkdir(parents=True,exist_ok=True)
    path=folder/'scene.usdc'
    if not path.exists():
        stage=make_scene(manifest,environment)
        stage.GetRootLayer().Export(str(path))
    return path,sha(path)


def register(stage,scene_id,gsd,index,intervention,environment):
    key='checkpoint_m5_'+scene_id+'_'+str(index)+'_'+('on' if intervention=='target_present' else 'off')
    folder=CHECKPOINTS/key
    folder.mkdir(parents=True,exist_ok=True)
    path=folder/'scene.usdc'
    if not path.exists():stage.GetRootLayer().Export(str(path))
    digest=sha(path)
    meta={'schema_version':1,'scene_sha256':digest,'camera':CAMERA,
          'resolution':[1024,768],'fill_frame':False,
          'renderer_settings':environment['renderer_settings'],
          'display_options':0,'timeline_seconds':1/24,
          'frozen_sampled_attributes':0,
          'limitations':'M5 static frozen scene; material/runtime dependencies recorded in M3; scene reconstructible from manifest and base snapshot.'}
    metadata=folder/'metadata.json'
    if metadata.exists():
        if json.loads(metadata.read_text())!=meta:
            raise ValueError('Checkpoint metadata changed: '+key)
    else:save(metadata,meta)
    return key,digest


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    sampler_root=frozen_sampler_root()
    def validate_manifest(manifest):return sampling.validate_manifest(manifest,sampler_root)
    builder.validate_manifest=validate_manifest
    index_path=OUT/'variant_index.json'
    rows=json.loads(index_path.read_text()) if index_path.exists() else []
    retained=[]
    for row in rows:
        if row['capture_source']=='milestone_4_reused':
            retained.append(row)
            continue
        checkpoint=CHECKPOINTS/row['checkpoint_id']
        stage=checkpoint/'scene.usdc'
        if not stage.exists() or not (checkpoint/'metadata.json').exists():
            continue  # Re-materialize a missing ignored checkpoint from M3 inputs.
        if sha(stage)!=row['snapshot_sha256']:
            raise ValueError('Existing checkpoint bytes changed: '+row['checkpoint_id'])
        retained.append(row)
    rows=retained
    completed={(x['scene_id'],x['requested_gsd_cm_px'],x['intervention']) for x in rows}
    environment=json.loads((EXP/'environment.json').read_text())
    m3={x['scene_id']:x for x in json.loads((EXP/'scenes/snapshot_index.json').read_text())}
    m4={ (x['scene_id'],x['requested_gsd_cm_px'],x['intervention']):x
         for x in json.loads((EXP/'renders/milestone_4/capture_progress.json').read_text()) }
    manifest_hashes={}
    for species in SPECIES:
        for scene_index in range(25):
            scene_id=species+'_%04d'%scene_index
            manifest_path=EXP/'scenes/manifests'/(scene_id+'.json')
            manifest=json.loads(manifest_path.read_text())
            validate_manifest(manifest)
            manifest_hashes[scene_id]=sha(manifest_path)
            if scene_index==0:
                for item in sorted((v for k,v in m4.items() if k[0]==scene_id),
                                   key=lambda x:(x['requested_gsd_cm_px'],x['intervention']!='target_present')):
                    key=(scene_id,item['requested_gsd_cm_px'],item['intervention'])
                    if key not in completed:
                        rows.append({'scene_id':scene_id,'species':species,'scene_index':scene_index,
                                     'requested_gsd_cm_px':item['requested_gsd_cm_px'],
                                     'intervention':item['intervention'],
                                     'capture_source':'milestone_4_reused',
                                     'checkpoint_id':item['checkpoint_id'],
                                     'snapshot_sha256':item['snapshot_sha256'],
                                     'rgb_path':item['rgb_path'],'rgb_sha256':item['rgb_sha256'],
                                     'biological_manifest_sha256':item['biological_manifest_sha256'],
                                     'manifest_sha256':manifest_hashes[scene_id]})
                        completed.add(key)
                save(index_path,rows)
                print(scene_id,'reused M4',flush=True)
                continue
            source,source_hash=base_scene(manifest,environment,m3)
            original=open_private(source)
            frozen_vertices=points(original)
            biological_sha=biological_record(manifest,sha(EXP/'environment.json'),original)['biological_manifest_sha256']
            if scene_id in m3 and biological_sha!=m3[scene_id]['biological_manifest_sha256']:
                raise ValueError('M3 biological identity changed')
            for variant_index,variant in enumerate(manifest['camera']['variants']):
                gsd=variant['requested_gsd_cm_px']
                states=('target_present','target_absent') if scene_index in NEGATIVE_PARENT_IDS else ('target_present',)
                for intervention in states:
                    key=(scene_id,gsd,intervention)
                    if key in completed:continue
                    stage=open_private(source)
                    set_camera(stage,variant)
                    if intervention=='target_absent':UsdGeom.Imageable(stage.GetPrimAtPath(TARGET)).MakeInvisible()
                    if not np.allclose(points(stage),frozen_vertices,rtol=0,atol=1e-5):
                        raise ValueError('Animal world geometry changed across camera variants')
                    checkpoint_id,scene_hash=register(stage,scene_id,gsd,variant_index,intervention,environment)
                    rows.append({'scene_id':scene_id,'species':species,'scene_index':scene_index,
                                 'requested_gsd_cm_px':gsd,'intervention':intervention,
                                 'capture_source':'milestone_5_new',
                                 'checkpoint_id':checkpoint_id,'snapshot_sha256':scene_hash,
                                 'base_scene_sha256':source_hash,
                                 'base_scene_source':'M3 snapshot' if scene_id in m3 else 'M5 deterministic rebuild from M3 manifest',
                                 'biological_manifest_sha256':biological_sha,
                                 'manifest_sha256':manifest_hashes[scene_id],
                                 'camera_world_position_m':variant['position_m'],
                                 'reference_plane_y_m':variant['reference_plane_y_m']})
                    completed.add(key)
            save(index_path,rows)
            print(scene_id,'prepared',flush=True)
    if len(rows)!=300 or len(completed)!=300:raise ValueError('Expected exactly 300 indexed views')
    save(OUT/'preparation.json',{'positive_images':250,'negative_images':50,
         'negative_parent_scene_indices':list(NEGATIVE_PARENT_IDS),
         'negative_parent_selection_policy':'fixed before rendering; evenly spread scene IDs, reserved for M6 3/1/1 split allocation',
         'scene_manifests_sha256':manifest_hashes,
         'checkpoint_policy':'Generated USD checkpoint files were stored under ignored artifacts/scene_checkpoints; source manifests and scene hashes were recorded here.',
         'milestone_4_reused_images':10})
    print(json.dumps({'prepared_views':len(rows),'reused_m4':10,'new_to_capture':280}),flush=True)


if __name__=='__main__':main()
