"""Run with official Blender --background --python tools/inspect_petrel.py.

Read-only source inspection. Writes a report and reference renders under
assets/birds/european_storm_petrel/working/inspection/.
"""
import bpy
import json
from pathlib import Path
from mathutils import Vector
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets/birds/european_storm_petrel/working/inspection'


def inspect():
    OUT.mkdir(parents=True,exist_ok=True)
    source=ROOT/'assets/avians/storm_petrel/source/scene.gltf'
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source))
    bpy.context.view_layer.update()
    report={'source':str(source.relative_to(ROOT)), 'format':'glTF 2.0', 'blender':bpy.app.version_string, 'objects':[]}
    points=[]; edges=[]; offset=0
    for obj in bpy.context.scene.objects:
        rec={'name':obj.name,'type':obj.type,'parent':obj.parent.name if obj.parent else None,
             'location':list(obj.location),'rotation_euler':list(obj.rotation_euler),
             'scale':list(obj.scale),'matrix_world':[list(row) for row in obj.matrix_world]}
        if obj.type=='MESH':
            m=obj.data; m.calc_loop_triangles()
            world=np.array([list(obj.matrix_world@v.co) for v in m.vertices])
            rec.update(vertices=len(m.vertices),polygons=len(m.polygons),triangles=len(m.loop_triangles),
                       local_dimensions=list(obj.dimensions),
                       local_mesh_bounds_min=[min(v.co[i] for v in m.vertices) for i in range(3)],
                       local_mesh_bounds_max=[max(v.co[i] for v in m.vertices) for i in range(3)],
                       world_min=world.min(axis=0).tolist(),world_max=world.max(axis=0).tolist(),
                       materials=[slot.material.name if slot.material else None for slot in obj.material_slots])
            points.extend(world.tolist())
            edges.extend((e.vertices[0]+offset,e.vertices[1]+offset) for e in m.edges)
            offset+=len(m.vertices)
        report['objects'].append(rec)
    pts=np.array(points)
    # Analysis-only coordinate welding resolves glTF mesh chunks and UV seams.
    _,inverse=np.unique(np.round(pts,5),axis=0,return_inverse=True)
    parents=list(range(int(inverse.max())+1))
    def find(a):
        while parents[a]!=a:
            parents[a]=parents[parents[a]];a=parents[a]
        return a
    for a,b in edges:
        a=find(int(inverse[a]));b=find(int(inverse[b]));parents[a]=b
    labels=np.array([find(int(i)) for i in inverse])
    groups,counts=np.unique(labels,return_counts=True)
    components=[]
    for label,count in sorted(zip(groups,counts),key=lambda x:-x[1])[:20]:
        p=pts[labels==label]
        components.append({'vertices':int(count),'minimum':p.min(axis=0).tolist(),'maximum':p.max(axis=0).tolist()})
    report.update(mesh_count=sum(o.type=='MESH' for o in bpy.context.scene.objects),
                  armature_count=sum(o.type=='ARMATURE' for o in bpy.context.scene.objects),
                  vertex_count=len(pts),world_min=pts.min(axis=0).tolist(),world_max=pts.max(axis=0).tolist(),
                  world_dimensions=np.ptp(pts,axis=0).tolist(),
                  welded_component_count=len(groups),largest_components=components,
                  weld_tolerance_note='Coordinates rounded to 5 decimal places for analysis only; original mesh unchanged.')
    report['materials']=[{'name':m.name,'nodes':[{'type':n.type,'image':n.image.filepath if n.type=='TEX_IMAGE' and n.image else None} for n in m.node_tree.nodes]} for m in bpy.data.materials if m.node_tree]
    props=bpy.ops.wm.usd_export.get_rna_type().properties
    report['usd_export_api']={p.identifier:{'type':p.type,'description':p.description,
        'default':str(getattr(p,'default',None)),
        'enum_items':[i.identifier for i in p.enum_items] if p.type=='ENUM' else []} for p in props}
    (OUT/'inspection.json').write_text(json.dumps(report,indent=2)+'\n')
    scene=bpy.context.scene;scene.render.engine='BLENDER_WORKBENCH'
    scene.display.shading.color_type='TEXTURE';scene.render.resolution_x=900;scene.render.resolution_y=900;scene.render.resolution_percentage=100
    center=Vector((pts.min(axis=0)+pts.max(axis=0))/2);size=float(np.ptp(pts,axis=0).max())
    bpy.ops.object.camera_add();cam=bpy.context.object;scene.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=size*1.15
    for name,d in [('top',(0,0,1)),('front',(0,-1,0)),('side',(1,0,0))]:
        cam.location=center+Vector(d)*size*3;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
        scene.render.filepath=str(OUT/f'{name}.png');bpy.ops.render.render(write_still=True)
    print(json.dumps({k:report[k] for k in ['mesh_count','armature_count','vertex_count','world_dimensions','welded_component_count','largest_components']},indent=2))


if __name__=='__main__': inspect()
