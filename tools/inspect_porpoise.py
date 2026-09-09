"""Non-destructive harbour-porpoise inspection using official Blender."""
import hashlib
import json
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
ASSET=ROOT/'assets/cetaceans/model_75a_-_harbor_porpoise'
OUT=ASSET/'working/calibration_v1'


def bounds(points):
    return {'min':points.min(axis=0).tolist(),'max':points.max(axis=0).tolist(),
            'dimensions':np.ptp(points,axis=0).tolist()}


def inspect():
    OUT.mkdir(parents=True,exist_ok=True)
    blend=OUT/'harbour_porpoise_inspected.blend'
    if blend.exists(): raise RuntimeError('Inspection already exists; preserve working version')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(ASSET/'source/scene.gltf'))
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    deps=bpy.context.evaluated_depsgraph_get()
    records=[]; allpoints=[]
    for obj in list(bpy.context.scene.objects):
        rec={'name':obj.name,'type':obj.type,'parent':obj.parent.name if obj.parent else None,
             'matrix_world':[list(row) for row in obj.matrix_world],
             'modifiers':[{'name':m.name,'type':m.type} for m in obj.modifiers]}
        if obj.type=='MESH':
            raw=np.array([obj.matrix_world@v.co for v in obj.data.vertices])
            ev=obj.evaluated_get(deps);mesh=ev.to_mesh()
            pts=np.array([ev.matrix_world@v.co for v in mesh.vertices])
            rec.update(vertices=len(obj.data.vertices),faces=len(obj.data.polygons),
                       mesh_name=obj.data.name,raw_world_bounds=bounds(raw),evaluated_world_bounds=bounds(pts),
                       materials=[m.name if m else None for m in obj.data.materials],
                       vertex_groups=[g.name for g in obj.vertex_groups])
            ev.to_mesh_clear();allpoints.append(pts)
        if obj.type=='ARMATURE':
            rec['bones']=[{'name':b.name,'head_world':list(obj.matrix_world@b.head_local),
                           'tail_world':list(obj.matrix_world@b.tail_local)} for b in obj.data.bones]
        records.append(rec)
    report={'source':'source/scene.gltf','coordinate_system':'Blender world Z up; native imported units unverified',
            'frame':1,'objects':records,'combined_evaluated_bounds':bounds(np.vstack(allpoints)),
            'actions':[a.name for a in bpy.data.actions],
            'original_sha256':{str(p.relative_to(ASSET)):hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (ASSET/'source/scene.gltf',ASSET/'source/scene.bin',ASSET/'source/license.txt',ASSET/'usd/model_75a_-_harbor_porpoise.usd')}}
    (OUT/'inspection.json').write_text(json.dumps(report,indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    scene=bpy.context.scene;scene.render.engine='BLENDER_WORKBENCH'
    scene.display.shading.color_type='TEXTURE'
    scene.render.resolution_x=1100;scene.render.resolution_y=700;scene.render.resolution_percentage=100
    pts=np.vstack(allpoints);center=Vector((pts.min(axis=0)+pts.max(axis=0))/2);size=float(np.ptp(pts,axis=0).max())
    bpy.ops.object.camera_add();cam=bpy.context.object;scene.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=size*1.25
    for name,direction in [('top',(0,0,1)),('side',(1,0,0)),('front',(0,-1,0))]:
        cam.location=center+Vector(direction)*size*3
        cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
        scene.render.filepath=str(OUT/f'{name}.png');bpy.ops.render.render(write_still=True)
    print(json.dumps([{k:v for k,v in r.items() if k not in ('matrix_world','bones','vertex_groups')} for r in records],indent=2))


if __name__=='__main__': inspect()
