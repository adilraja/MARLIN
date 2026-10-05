"""Register immutable five-GSD MARLIN checkpoint pairs from each M3 snapshot.

Executed with the installed Blender USD runtime. Only camera Y changes within
positive pairs. Target-off counterparts are explicit visibility interventions.
"""
import hashlib
import json
from pathlib import Path
import shutil
import sys
sys.dont_write_bytecode=True
from pxr import UsdGeom
ROOT=Path(__file__).resolve().parents[3]
EXP=ROOT/'experiments/gsd_pilot_v1'
sys.path.insert(0,str(EXP/'scenes'))
from build_scenes import CAMERA,TARGET,open_private,set_camera,sha,save,points
from sampling import validate_manifest
OUT=EXP/'renders/milestone_4'
CHECKPOINTS=ROOT/'artifacts/scene_checkpoints'


def build():
    index_file=OUT/'variant_index.json'
    if index_file.exists():raise RuntimeError('Preserve existing M4 variant index')
    original={x['scene_id']:x for x in json.loads((EXP/'scenes/snapshot_index.json').read_text())}
    env=json.loads((EXP/'environment.json').read_text())
    results=[]
    for species in ('european_storm_petrel','harbour_porpoise'):
        scene_id=species+'_0000'
        manifest=json.loads((EXP/'scenes/manifests'/(scene_id+'.json')).read_text())
        validate_manifest(manifest)
        source=EXP/original[scene_id]['snapshot']
        if sha(source)!=original[scene_id]['sha256']:raise ValueError('M3 snapshot changed')
        expected=open_private(source)
        baseline=points(expected)
        biological=original[scene_id]['biological_manifest_sha256']
        for i,variant in enumerate(manifest['camera']['variants']):
            gsd=variant['requested_gsd_cm_px'];label=('%.1f'%gsd).replace('.','p')
            for intervention in ('target_present','target_absent'):
                stage=open_private(source)
                set_camera(stage,variant)
                if intervention=='target_absent':
                    UsdGeom.Imageable(stage.GetPrimAtPath(TARGET)).MakeInvisible()
                if not (abs(points(stage)-baseline)<1e-5).all():
                    raise ValueError('Animal geometry changed during camera pairing')
                directory=OUT/scene_id/('gsd_'+label)/intervention
                directory.mkdir(parents=True,exist_ok=False)
                scene_file=directory/'scene.usdc'
                stage.GetRootLayer().Export(str(scene_file))
                metadata={'schema_version':1,'scene_sha256':sha(scene_file),'camera':CAMERA,
                    'resolution':[1024,768],'fill_frame':False,'renderer_settings':env['renderer_settings'],
                    'display_options':0,'timeline_seconds':1/24,'frozen_sampled_attributes':0,
                    'limitations':'Static M4 pilot; external material/runtime dependencies; target-absent is a separate visibility intervention.'}
                save(directory/'metadata.json',metadata)
                checkpoint_id='checkpoint_m4_'+scene_id+'_'+str(i)+'_'+('on' if intervention=='target_present' else 'off')+'_'+metadata['scene_sha256'][:10]
                checkpoint=CHECKPOINTS/checkpoint_id
                if checkpoint.exists():raise RuntimeError('Checkpoint already registered')
                shutil.copytree(directory,checkpoint)
                results.append({'scene_id':scene_id,'species':species,'requested_gsd_cm_px':gsd,
                    'variant_index':i,'intervention':intervention,'checkpoint_id':checkpoint_id,
                    'snapshot':str(scene_file.relative_to(EXP)),'snapshot_sha256':metadata['scene_sha256'],
                    'biological_manifest_sha256':biological,
                    'camera_world_position_m':variant['position_m'],
                    'reference_plane_y_m':variant['reference_plane_y_m']})
    save(index_file,results)
    print(json.dumps({'pairs':10,'registered_snapshots':len(results),'target_states':['present','absent']}))


if __name__=='__main__':build()
