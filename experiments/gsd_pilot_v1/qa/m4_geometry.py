"""Project the evaluated USD animal meshes into each actual pilot camera.

Run with Blender's USD Python. This labels the direct, amodal mesh geometry;
rendered appearance and underwater refraction are assessed separately.
"""
import hashlib
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
import numpy as np
from pxr import Usd, UsdGeom

ROOT=Path(__file__).resolve().parents[3]
EXP=ROOT/'experiments/gsd_pilot_v1'
sys.path.insert(0,str(EXP/'scenes'))
sys.path.insert(0,str(ROOT/'source/extensions/cris.madil.render_service/cris/madil/render_service'))
from build_scenes import CAMERA,TARGET,open_private,sha
from capture_projection import image_projection
OUT=EXP/'renders/milestone_4'


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def project(item):
    scene=EXP/item['snapshot']
    if sha(scene)!=item['snapshot_sha256']:raise ValueError('Snapshot hash changed: '+str(scene))
    stage=open_private(scene)
    if UsdGeom.GetStageUpAxis(stage)!='Y' or UsdGeom.GetStageMetersPerUnit(stage)!=.01:
        raise ValueError('Unexpected stage coordinate system')
    camera=UsdGeom.Camera(stage.GetPrimAtPath(CAMERA))
    if not camera:raise ValueError('Missing authored capture camera')
    camera_origin=np.asarray(UsdGeom.Xformable(camera).ComputeLocalToWorldTransform(Usd.TimeCode.Default()))[3,:3]*.01
    if np.max(np.abs(camera_origin-item['camera_world_position_m']))>1e-6:
        raise ValueError('Camera does not match paired manifest')
    attrs=camera.GetCamera(Usd.TimeCode(1))
    focal_px=attrs.focalLength/attrs.horizontalAperture*1024
    if abs(focal_px-10000)>1e-2:
        raise ValueError('Focal length/pixel pitch changed')
    if item['intervention']!='target_present':return None
    chunks=[];mesh_paths=[]
    for prim in sorted(Usd.PrimRange(stage.GetPrimAtPath(TARGET)),key=lambda p:str(p.GetPath())):
        if not prim.IsA(UsdGeom.Mesh):continue
        mesh=UsdGeom.Mesh(prim)
        local=np.asarray(mesh.GetPointsAttr().Get(),dtype=np.float64)
        transform=np.asarray(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default()))
        world=(np.column_stack([local,np.ones(len(local))])@transform)[:,:3]*.01
        chunks.append(world);mesh_paths.append(str(prim.GetPath()))
    if not chunks:raise ValueError('No evaluated animal mesh')
    vertices=np.concatenate(chunks)
    depth=camera_origin[1]-vertices[:,1]
    if np.min(depth)<=0:raise ValueError('Animal vertex behind camera')
    # The authored USD camera looks down -Y and its +X/+Z image directions
    # were independently checked in M3's calibrated camera fixture.
    u=512+focal_px*vertices[:,0]/depth
    v=384+focal_px*vertices[:,2]/depth
    x0,y0,x1,y1=map(float,(u.min(),v.min(),u.max(),v.max()))
    if not (0<=x0<x1<=1024 and 0<=y0<y1<=768):
        raise ValueError('Animal amodal mesh escaped image: '+str((x0,y0,x1,y1)))
    projected_sha=hashlib.sha256(np.column_stack([u,v]).astype('<f8').tobytes()).hexdigest()
    projection=image_projection(stage,CAMERA,(1024,768),Usd.TimeCode(1))
    return {'scene_id':item['scene_id'],'species':item['species'],
            'gsd_cm_px_requested':item['requested_gsd_cm_px'],
            'geometry_source':'all evaluated UsdGeom.Mesh vertices below '+TARGET+' with parent world transforms at frozen pose',
            'mesh_paths':mesh_paths,'vertex_count':int(len(vertices)),
            'projected_vertices_sha256':projected_sha,
            'camera_world_position_m':camera_origin.tolist(),
            'camera':CAMERA,'resolution_px':[1024,768],
            'projection':projection,
            'world_bounds_min_m':vertices.min(axis=0).tolist(),
            'world_bounds_max_m':vertices.max(axis=0).tolist(),
            'depth_range_m':[float(depth.min()),float(depth.max())],
            'reference_plane_gsd_cm_px':float(100*(camera_origin[1]-item['reference_plane_y_m'])/focal_px),
            'target_vertex_depth_gsd_range_cm_px':[float(100*depth.min()/focal_px),float(100*depth.max()/focal_px)],
            'target_mean_vertex_depth_gsd_cm_px':float(100*depth.mean()/focal_px),
            'amodal_bbox_xyxy_px':[x0,y0,x1,y1],
            'amodal_bbox_coco_xywh_px':[x0,y0,x1-x0,y1-y0],
            'bbox_width_px':x1-x0,'bbox_height_px':y1-y0,
            'projected_silhouette_area_px':None,
            'projected_silhouette_area_reason':'Triangle rasterization and self-occlusion have not been validated; bbox area is not a silhouette.',
            'visible_target_area_px':None,
            'visible_target_area_reason':'Image-pair appearance and underwater refraction require separate validation.',
            'annotation_semantics':'amodal direct mesh projection; not a refracted visible box'}


def main():
    items=json.loads((OUT/'variant_index.json').read_text())
    records=[]
    for item in items:
        if item['intervention']!='target_present':continue
        value=project(item);records.append(value)
        folder=EXP/item['snapshot'].split('/scene.usdc')[0]
        save(folder/'geometry.json',value)
        print(item['scene_id'],item['requested_gsd_cm_px'],'box',value['amodal_bbox_coco_xywh_px'],flush=True)
    save(EXP/'annotations/milestone_4_geometry.json',{'schema_version':1,'records':records})


if __name__=='__main__':main()
