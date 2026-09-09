"""Build a morphology-preserving test rig using Blender 5.0.1.

Input is the existing support-cleaned v1; original scan copied for provenance.
No smoothing, remeshing, scale change or rest-pose reshaping is performed.
"""
import bpy
import json
import math
import shutil
import numpy as np
from pathlib import Path
from mathutils import Vector, Quaternion

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets/birds/european_storm_petrel'
FORWARD=Vector((11.5,-21,0)).normalized()
LEFT=Vector((-FORWARD.y,FORWARD.x,0))
CENTER=Vector((-1,-15,8))
POSES={'glide':(0,0,0),'wings_up':(18,10,0),'wings_down':(-15,-8,0),
       'bank_left':(3,0,-12),'bank_right':(3,0,12)}


def ramp(value,low,high):
    t=max(0,min(1,(value-low)/(high-low)))
    return t*t*(3-2*t)


def apply_pose(arm,pose):
    for p in arm.pose.bones:
        p.rotation_mode='QUATERNION';p.rotation_quaternion=Quaternion()
    shoulder,outer,bank=POSES[pose]
    for side,sign in [('L',1),('R',-1)]:
        for suffix,angle in [('shoulder',shoulder),('mid',outer),('tip',outer*0.3)]:
            p=arm.pose.bones[f'wing_{side}_{suffix}']
            axis=p.bone.matrix_local.to_3x3().inverted()@FORWARD
            p.rotation_quaternion=Quaternion(axis,math.radians(sign*angle))
    p=arm.pose.bones['root']
    axis=p.bone.matrix_local.to_3x3().inverted()@FORWARD
    p.rotation_quaternion=Quaternion(axis,math.radians(bank))
    bpy.context.view_layer.update()


def run():
    blend=OUT/'working/european_storm_petrel_rigged.blend'
    if blend.exists(): raise RuntimeError('Refusing to overwrite existing rig')
    shutil.copytree(ROOT/'assets/avians/storm_petrel/source',OUT/'source',dirs_exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/avians/storm_petrel/working/support_cleanup_v1/storm_petrel_working.blend'))
    scene=bpy.context.scene
    meshes=[o for o in scene.objects if o.type=='MESH' and len(o.data.vertices)]
    original={o.name:np.array([list(o.matrix_world@v.co) for v in o.data.vertices]) for o in meshes}
    # Bake the existing parent transforms into coordinates, preserving the
    # complete surface in Blender world space. Rig is then identity transform.
    for o in meshes:
        matrix=o.matrix_world.copy();o.parent=None;o.data.transform(matrix)
        o.matrix_world.identity()
    for o in list(scene.objects):
        if o not in meshes: bpy.data.objects.remove(o,do_unlink=True)
    bpy.ops.object.armature_add(enter_editmode=True,location=(0,0,0))
    arm=bpy.context.object;arm.name='EuropeanStormPetrelRig'
    bones=arm.data.edit_bones
    for b in list(bones):bones.remove(b)
    definitions=[]
    def bone(name,head,tail,parent=None):
        b=bones.new(name);b.head=head;b.tail=tail
        if parent:b.parent=bones[parent]
        definitions.append({'name':name,'head':list(head),'tail':list(tail),'parent':parent})
    bone('root',CENTER-Vector((0,0,8)),CENTER-Vector((0,0,4)))
    bone('body',CENTER-FORWARD*4,CENTER+FORWARD*4,'root')
    bone('neck',CENTER+FORWARD*4,CENTER+FORWARD*9+Vector((0,0,2)),'body')
    bone('head',CENTER+FORWARD*9+Vector((0,0,2)),CENTER+FORWARD*15+Vector((0,0,3)),'neck')
    all_points=np.concatenate(list(original.values()))
    lateral=(all_points-np.array(CENTER))@np.array(LEFT)
    for side,sign in [('L',1),('R',-1)]:
        landmarks=[CENTER+LEFT*(sign*4)]
        for distance in [13,23]:
            band=all_points[(lateral*sign>distance-2)&(lateral*sign<distance+2)]
            if not len(band):raise RuntimeError('Missing wing landmark band')
            landmarks.append(Vector(np.median(band,axis=0)))
        tip=landmarks[-1]+LEFT*sign*3
        for suffix,h,t,parent in [('shoulder',landmarks[0],landmarks[1],'body'),
            ('mid',landmarks[1],landmarks[2],f'wing_{side}_shoulder'),
            ('tip',landmarks[2],tip,f'wing_{side}_mid')]:bone(f'wing_{side}_{suffix}',h,t,parent)
    bone('tail',CENTER-FORWARD*5,CENTER-FORWARD*16,'body')
    bpy.ops.object.mode_set(mode='OBJECT')
    max_weight_error=0;wrong_side=0
    for o in meshes:
        groups={d['name']:o.vertex_groups.new(name=d['name']) for d in definitions}
        for v in o.data.vertices:
            delta=v.co-CENTER;lat=delta.dot(LEFT);long=delta.dot(FORWARD)
            wing=ramp(abs(lat),4,8)*ramp(v.co.z,0,4)
            weights={}
            if wing>0:
                side='L' if lat>0 else 'R'
                outer=ramp(abs(lat),10,17);tip=ramp(abs(lat),19,25)
                weights[f'wing_{side}_shoulder']=wing*(1-outer)
                weights[f'wing_{side}_mid']=wing*outer*(1-tip)
                weights[f'wing_{side}_tip']=wing*outer*tip
            residual=1-wing
            neck=ramp(long,6,10);head=ramp(long,10,14);tail=ramp(-long,7,12)
            weights['head']=residual*neck*head
            weights['neck']=residual*neck*(1-head)
            weights['tail']=residual*(1-neck)*tail
            weights['body']=residual*(1-neck)*(1-tail)
            total=sum(weights.values());max_weight_error=max(max_weight_error,abs(total-1))
            for name,weight in weights.items():
                if weight>1e-8:groups[name].add([v.index],weight,'REPLACE')
                if weight>0 and ((name.startswith('wing_L') and lat<0) or (name.startswith('wing_R') and lat>0)):wrong_side+=1
        modifier=o.modifiers.new('PetrelSkeleton','ARMATURE');modifier.object=arm
        modifier.use_deform_preserve_volume=False
        o.parent=arm
    apply_pose(arm,'glide')
    rest_error=0
    deps=bpy.context.evaluated_depsgraph_get()
    for o in meshes:
        evaluated=o.evaluated_get(deps);m=evaluated.to_mesh()
        points=np.array([list(evaluated.matrix_world@v.co) for v in m.vertices])
        rest_error=max(rest_error,float(np.abs(points-original[o.name]).max()))
        evaluated.to_mesh_clear()
    assert rest_error<1e-4 and max_weight_error<1e-6 and wrong_side==0
    # Isolated-bone numeric checks: verify movement exists, torso and opposite
    # wing remain unaffected by each wing bone. No automatic weighting used.
    influence_tests=[]
    for name in [d['name'] for d in definitions if d['name']!='root']:
        apply_pose(arm,'glide');p=arm.pose.bones[name]
        axis=p.bone.matrix_local.to_3x3().inverted()@FORWARD
        p.rotation_quaternion=Quaternion(axis,math.radians(8));bpy.context.view_layer.update()
        max_movement=0;torso_movement=0;opposite_movement=0
        for o in meshes:
            e=o.evaluated_get(bpy.context.evaluated_depsgraph_get());m=e.to_mesh()
            pts=np.array([list(e.matrix_world@v.co) for v in m.vertices]);base=original[o.name]
            move=np.linalg.norm(pts-base,axis=1);max_movement=max(max_movement,float(move.max()))
            lat=(base-np.array(CENTER))@np.array(LEFT)
            long=(base-np.array(CENTER))@np.array(FORWARD)
            torso=(np.abs(lat)<3)&(np.abs(long)<5)
            if torso.any():torso_movement=max(torso_movement,float(move[torso].max()))
            opposite=lat<-8 if name.startswith('wing_L') else lat>8
            if opposite.any():opposite_movement=max(opposite_movement,float(move[opposite].max()))
            e.to_mesh_clear()
        assert max_movement>1e-4,name
        if name.startswith('wing_'):assert torso_movement<1e-4 and opposite_movement<1e-4,name
        influence_tests.append({'bone':name,'max_displacement':max_movement,'torso_displacement':torso_movement,'opposite_wing_displacement':opposite_movement})
    apply_pose(arm,'glide')
    scene.render.fps=24;scene.frame_start=1;scene.frame_end=49
    for frame,pose in [(1,'glide'),(13,'wings_up'),(25,'glide'),(37,'wings_down'),(49,'glide')]:
        apply_pose(arm,pose)
        for p in arm.pose.bones:p.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=p.name)
    arm.animation_data.action.name='wingbeat_test'
    scene.frame_set(1)
    pose_data={}
    action=arm.animation_data.action;arm.animation_data.action=None
    for name in POSES:
        apply_pose(arm,name)
        pose_data[name]={p.name:list(p.rotation_quaternion) for p in arm.pose.bones}
        # Named actions are convenient for inspection in Blender.
        for p in arm.pose.bones:p.keyframe_insert(data_path='rotation_quaternion',frame=1,group=p.name)
        arm.animation_data.action.name=name;arm.animation_data.action.use_fake_user=True
        arm.animation_data.action=None
    arm.animation_data.action=action;scene.frame_set(1)
    (OUT/'usd').mkdir(exist_ok=True)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    # These option identifiers were inspected from the installed RNA API.
    bpy.ops.wm.usd_export(filepath=str(OUT/'usd/european_storm_petrel_rigged.usd'),
        export_animation=True,export_armatures=True,export_materials=True,
        export_textures_mode='NEW',relative_paths=True)
    arm.animation_data.action=None
    for name in POSES:
        apply_pose(arm,name)
        bpy.ops.wm.usd_export(filepath=str(OUT/f'usd/{name}.usd'),export_animation=False,
            export_armatures=True,export_materials=True,export_textures_mode='NEW',relative_paths=True)
    report={'input':'assets/avians/storm_petrel/working/support_cleanup_v1/storm_petrel_working.blend',
        'orientation':{'up':'+Z','forward':list(FORWARD),'left':list(LEFT),'body_center':list(CENTER)},
        'bones':definitions,'poses':pose_data,'pose_angles_degrees':POSES,
        'max_rest_coordinate_error':rest_error,'max_weight_sum_error':max_weight_error,
        'wrong_side_weights':wrong_side,'isolated_bone_tests':influence_tests,
        'test_animation':{'frames':[1,49],'fps':24,'timing':'arbitrary validation timing, not biological'},
        'original_vertex_count':sum(len(v) for v in original.values()),
        'rest_world_min':all_points.min(axis=0).tolist(),'rest_world_max':all_points.max(axis=0).tolist(),
        'limitations':['Support-cleaned v1 retains imperfect foot contact edges.',
            'Native asymmetric scan preserved; bone landmarks follow actual wing bands.',
            'Weights are geometric and conservative, not anatomical muscle modelling.']}
    (OUT/'working/rig_report.json').write_text(json.dumps(report,indent=2)+'\n')
    # Render named poses with the same camera and framing for visual QA.
    scene.render.engine='BLENDER_WORKBENCH';scene.display.shading.color_type='TEXTURE'
    scene.render.resolution_x=900;scene.render.resolution_y=700;scene.render.resolution_percentage=100
    bpy.ops.object.camera_add();cam=bpy.context.object;scene.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=70
    cam.location=CENTER+Vector((20,-80,35));cam.rotation_euler=(CENTER-cam.location).to_track_quat('-Z','Y').to_euler()
    for name in POSES:
        apply_pose(arm,name);scene.render.filepath=str(OUT/f'working/{name}.png');bpy.ops.render.render(write_still=True)
    print('Rig built and poses rendered',blend,flush=True)


if __name__=='__main__':run()
