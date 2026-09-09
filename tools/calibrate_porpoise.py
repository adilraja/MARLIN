"""Build a reversible static calibration candidate; originals and rig stay intact."""
import hashlib
import json
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
from pxr import Usd, UsdGeom

ROOT=Path(__file__).resolve().parents[1]
ASSET=ROOT/'assets/cetaceans/model_75a_-_harbor_porpoise'
OUT=ASSET/'working/calibration_v1'


def run():
    output=OUT/'harbour_porpoise_calibration_candidate.blend'
    if output.exists(): raise RuntimeError('Working candidate exists; preserve it')
    inspection=json.loads((OUT/'inspection.json').read_text())
    for p,digest in inspection['original_sha256'].items():
        assert hashlib.sha256((ASSET/p).read_bytes()).hexdigest()==digest
    bpy.ops.wm.open_mainfile(filepath=str(OUT/'harbour_porpoise_inspected.blend'))
    body=bpy.data.objects['Object_7'];eye=bpy.data.objects['Object_8']
    arm=bpy.data.objects['GLTF_created_0']
    helper=bpy.data.objects['Icosphere']
    users=[b.name for b in arm.pose.bones if b.custom_shape==helper]
    assert len(users)==20
    points=np.array([body.matrix_world@v.co for v in body.data.vertices],dtype=float)
    # Candidate landmarks checked in native top/side anatomy: rostrum tip and
    # posterior centreline fluke notch, NOT the longest fin-inclusive bound.
    nose_index=3703;notch_index=7266
    nose,notch=points[nose_index],points[notch_index]
    native_length=float(np.linalg.norm(notch-nose))
    specimen_length=1.555
    factor=specimen_length/native_length
    origin=(nose+notch)/2
    # Explicit engineering surfacing candidate; not a measured waterline.
    waterline_native_z=0.10
    origin[2]=waterline_native_z
    snapshot=bpy.data.scenes.new('StaticCalibrationCandidate')
    bpy.context.window.scene=snapshot
    snapshots=[];world=[]
    for source,name in ((body,'PorpoiseBody'),(eye,'PorpoiseEyes')):
        obj=bpy.data.objects.new(name,source.data.copy());snapshot.collection.objects.link(obj)
        for src,dst in zip(source.data.vertices,obj.data.vertices):
            dst.co=Vector((np.array(source.matrix_world@src.co)-origin)*factor)
        snapshots.append(obj);world.extend([list(v.co) for v in obj.data.vertices])
    p=np.array(world)
    assert sum(len(o.data.vertices) for o in snapshots)==23456
    bpy.ops.object.select_all(action='DESELECT')
    for obj in snapshots: obj.select_set(True)
    bpy.context.view_layer.objects.active=snapshots[0]
    snapshot.unit_settings.system='METRIC';snapshot.unit_settings.scale_length=1
    usd=OUT/'usd/harbour_porpoise_static_candidate.usd';usd.parent.mkdir(exist_ok=True)
    bpy.ops.wm.usd_export(filepath=str(usd),selected_objects_only=True,export_animation=False,
                          export_armatures=False,export_materials=True,export_textures_mode='NEW',relative_paths=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    stage=Usd.Stage.Open(str(usd))
    meshes=[prim for prim in stage.Traverse() if prim.IsA(UsdGeom.Mesh)]
    assert len(meshes)==2 and not any('Icosphere' in str(prim.GetPath()) for prim in stage.Traverse())
    assert UsdGeom.GetStageMetersPerUnit(stage)==1
    cache=UsdGeom.BBoxCache(Usd.TimeCode.Default(),['default','render','proxy'])
    bounds=cache.ComputeWorldBound(stage.GetDefaultPrim()).ComputeAlignedRange()
    np.testing.assert_allclose(list(bounds.GetMin()),p.min(axis=0),atol=1e-5)
    np.testing.assert_allclose(list(bounds.GetMax()),p.max(axis=0),atol=1e-5)
    report={'status':'specimen_length_anchored_candidate_requires_landmark_and_waterline_review',
            'source_specimen':{'name':'Freja','sex':'female','total_length_m':specimen_length,
              'source':'https://api.sketchfab.com/v3/models/eb02e57f17d741329a66844a3a8d2094',
              'author':'DigitalLife3D','license':'CC-BY-NC-4.0'},
            'helper':{'name':'Icosphere','purpose':'Blender imported bone custom shape','bone_users':users,
                      'excluded_from_measurement_and_static_export':True,'deleted_from_original':False},
            'body_mesh':'Object_7','eyes_mesh':'Object_8','armature_preserved_in_inspected_blend':True,
            'measurement_pose':'raw mesh/bind geometry after parent world transforms, NOT animated frame 1',
            'landmarks':{'body_mesh_vertex_indices':[nose_index,notch_index],
                         'candidate_rostrum_tip_native':nose.tolist(),'candidate_fluke_notch_native':notch.tolist(),
                         'method':'straight-line 3D endpoint distance; needs anatomical/method correspondence review'},
            'native_landmark_length':native_length,'uniform_scale_to_m':factor,
            'native_origin_subtracted':origin.tolist(),
            'metric_landmark_length_m':float(np.linalg.norm((notch-nose)*factor)),
            'metric_xyz_bounds':{'min':p.min(axis=0).tolist(),'max':p.max(axis=0).tolist(),'dimensions':np.ptp(p,axis=0).tolist()},
            'usd_up_axis':'Z','usd_meters_per_unit':1,'kit_y_up_reference_rotation_xyz_deg':[-90,0,0],
            'native_forward':'-Y','kit_forward_after_rotation':'+Z',
            'surfacing_candidate':{'water_plane_blender_z_m':0,'native_waterline_z':waterline_native_z,
              'status':'engineering placement only; blowhole clearance and biological waterline not verified'},
            'retained_mesh_vertices':23456,'usd_mesh_count':len(meshes),
            'usd_bounds_check_passed':True,'primary_asset_replaced':False,'scientific_render_ready':False}
    (OUT/'calibration.json').write_text(json.dumps(report,indent=2)+'\n')
    snapshot.render.engine='BLENDER_WORKBENCH';snapshot.display.shading.color_type='TEXTURE'
    snapshot.display.shading.background_type='WORLD';snapshot.world=bpy.data.worlds.new('ReviewWorld');snapshot.world.color=(.15,.15,.15)
    snapshot.render.resolution_x=1200;snapshot.render.resolution_y=800;snapshot.render.resolution_percentage=100
    center=Vector((p.min(axis=0)+p.max(axis=0))/2);size=float(np.ptp(p,axis=0).max())
    bpy.ops.object.camera_add();cam=bpy.context.object;snapshot.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=size*1.2
    # Reference waterline only, not an ocean material or modified animal mesh.
    curve=bpy.data.curves.new('CandidateWaterline','CURVE');curve.dimensions='3D';curve.bevel_depth=.0015
    spline=curve.splines.new('POLY');spline.points.add(1)
    spline.points[0].co=(.35,-1.1,0,1);spline.points[1].co=(.35,1.1,0,1)
    line=bpy.data.objects.new('CandidateWaterline',curve);snapshot.collection.objects.link(line)
    for name,direction in [('candidate_side',(1,0,0)),('candidate_top',(0,0,1))]:
        cam.data.ortho_scale=size*1.2*(1.5 if name.endswith('top') else 1)
        line.hide_render=name.endswith('top')
        cam.location=center+Vector(direction)*size*3;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
        snapshot.render.filepath=str(OUT/f'{name}.png');bpy.ops.render.render(write_still=True)
    for path,digest in inspection['original_sha256'].items():
        assert hashlib.sha256((ASSET/path).read_bytes()).hexdigest()==digest
    print(json.dumps(report,indent=2))


if __name__=='__main__': run()
