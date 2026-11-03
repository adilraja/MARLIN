"""Opt-in medium binding and a perimeter-only enclosure for MARLIN's ocean."""
from functools import lru_cache
import json
import math
from pathlib import Path
from typing import Literal

import omni.usd
import numpy as np
from pydantic import BaseModel, Field
from pxr import Gf, Sdf, UsdGeom, UsdShade, Vt

from .api import router
from . import ocean
from .ocean_enclosure import enclose, grid_topology, topology, validate

KEY='marlin:waterMedium:config'
MATERIAL='OceanWaterEngineeringV1'
PRESET=Path(__file__).resolve().parents[3]/'config/ocean_medium_engineering_v1.json'


def configuration(prim):
    attr=prim.GetAttribute(KEY) if prim else None
    value=attr.Get() if attr else None
    return json.loads(value) if value else None


def selected(prim):
    return configuration(prim) is not None


@lru_cache(maxsize=4)
def cached_topology(resolution):
    faces=topology(resolution)
    return faces,[len(f) for f in faces],[i for f in faces for i in f]


def render_arrays(mesh,points,normals,extent):
    config=configuration(mesh.GetPrim())
    if config is None:
        return points,normals,extent,UsdGeom.Tokens.vertex
    faces,counts,indices=cached_topology(config['resolution'])
    if len(mesh.GetFaceVertexCountsAttr().Get()) != len(counts):
        mesh.GetFaceVertexCountsAttr().Set(counts)
        mesh.GetFaceVertexIndicesAttr().Set(indices)
    p,n,e=enclose(points,normals,config['resolution'],config['bottom_y_units'],faces,arrays=True)
    mesh.GetDoubleSidedAttr().Set(False)
    return (Vt.Vec3fArray.FromNumpy(np.asarray(p,dtype=np.float32)),
            Vt.Vec3fArray.FromNumpy(np.asarray(n,dtype=np.float32)),
            [Gf.Vec3f(*v) for v in e],UsdGeom.Tokens.faceVarying)


def author_frame(mesh,points,normals,extent):
    points,normals,extent,interpolation=render_arrays(mesh,points,normals,extent)
    mesh.GetPointsAttr().Set(points)
    mesh.CreateNormalsAttr().Set(normals)
    mesh.SetNormalsInterpolation(interpolation)
    mesh.GetExtentAttr().Set(extent)


def surface_arrays(mesh,config):
    r=config['resolution'];n=(r+1)**2
    points=list(mesh.GetPointsAttr().Get())[:n]
    values=list(mesh.GetNormalsAttr().Get())
    if mesh.GetNormalsInterpolation()==UsdGeom.Tokens.vertex:
        normals=values[:n]
    else:
        normals=[None]*n;offset=0
        for face in grid_topology(r):
            for i in face:
                normals[i]=values[offset];offset+=1
    return points,normals,[Gf.Vec3f(*(min(p[i] for p in points) for i in range(3))),
                           Gf.Vec3f(*(max(p[i] for p in points) for i in range(3)))]


def restart_signature(state):
    return dict(size=state['size'],resolution=state['resolution'],
                wave_height=sum(w['amplitude'] for w in state['waves']),
                wave_length=2*math.pi/state['waves'][0]['k'],choppiness=state['choppiness'],
                position=list(state['position']))


def validate_restart(prim,data):
    config=configuration(prim)
    if config:
        for key,expected in config['restart_signature'].items():
            actual=getattr(data,key)
            if isinstance(expected,list):
                equal=all(math.isclose(a,b,rel_tol=1e-8,abs_tol=1e-8) for a,b in zip(actual,expected))
            else:equal=math.isclose(actual,expected,rel_tol=1e-8,abs_tol=1e-8)
            if not equal:
                raise ValueError('Select the original water preset before changing ocean '+key)


def configure_renderer(stage,config):
    import carb.settings
    from .underwater_cue import UNDERWATER_CUE_REQUESTED_SETTING
    from .camera import _active_viewport
    viewport=_active_viewport()
    if viewport is None:raise ValueError('An active viewport is required')
    if viewport.resolution[0]*viewport.resolution[1]>512*384:
        raise ValueError('M4 renderer configuration is qualified only at 512x384 or smaller; use configure_renderer=false for binding alone')
    product=stage.GetPrimAtPath(viewport.render_product_path)
    camera=stage.GetPrimAtPath(str(viewport.camera_path))
    camera.ApplyAPI('OmniRtxCameraAutoExposureAPI_1')
    changes=[(product,'omni:rtx:rendermode','PathTracing'),
             (product,'omni:rtx:fog:enabled',False),
             (product,'omni:rtx:pt:fireflyFilter:enabled',False),
             (product,'omni:rtx:rtpt:fireflyFilter:enabled',False),
             (camera,'omni:rtx:autoExposure:enabled',False)]
    for prim,name,value in changes:
        attr=prim.GetAttribute(name)
        if not attr:raise ValueError('Missing installed render control: '+name)
        identity=[str(prim.GetPath()),name]
        if not any(x['identity']==identity for x in config['renderer_before']):
            config['renderer_before'].append(dict(identity=identity,authored=attr.HasAuthoredValueOpinion(),value=attr.Get()))
        attr.Set(value)
    settings=carb.settings.get_settings()
    if UNDERWATER_CUE_REQUESTED_SETTING not in config['global_before']:
        config['global_before'][UNDERWATER_CUE_REQUESTED_SETTING]=settings.get(UNDERWATER_CUE_REQUESTED_SETTING)
    settings.set(UNDERWATER_CUE_REQUESTED_SETTING,False)


def preserve_renderer_after_setup(stage):
    prim=stage.GetPrimAtPath('/World/Ocean');config=configuration(prim)
    if config and config['configure_renderer']:
        configure_renderer(stage,config)
        prim.GetAttribute(KEY).Set(json.dumps(config))


def restore_original(stage,mesh):
    from .hidef_marine import restore_settings
    config=configuration(mesh.GetPrim())
    if not config:return {'ok':True,'selection':'original','already_original':True}
    points,normals,extent=surface_arrays(mesh,config)
    faces=grid_topology(config['resolution'])
    mesh.GetPrim().GetAttribute(KEY).Set('')
    mesh.GetFaceVertexCountsAttr().Set([4]*len(faces))
    mesh.GetFaceVertexIndicesAttr().Set([i for f in faces for i in f])
    author_frame(mesh,points,normals,extent)
    mesh.GetDoubleSidedAttr().Set(config['original_double_sided'])
    prim=mesh.GetPrim()
    if config['original_binding_targets']:
        rel=prim.CreateRelationship('material:binding')
        rel.SetTargets([Sdf.Path(p) for p in config['original_binding_targets']])
        strength=config['original_binding_strength']
        if strength is None:rel.ClearMetadata('bindMaterialAs')
        else:rel.SetMetadata('bindMaterialAs',strength)
    else:prim.RemoveProperty('material:binding')
    for record in config['renderer_before']:
        path,name=record['identity'];p=stage.GetPrimAtPath(path)
        if p:
            attr=p.GetAttribute(name)
            if attr:
                if record['authored']:attr.Set(record['value'])
                else:attr.Clear()
    restore_settings(config['global_before'])
    return {'ok':True,'selection':'original','restored_top_vertices':len(points),
            'restored_top_faces':len(faces),'renderer_properties_restored':len(config['renderer_before'])}


class PresetRequest(BaseModel):
    selection: Literal['engineering_v1','original']='engineering_v1'
    bottom_depth_m: float=Field(default=20,ge=2,le=100)
    configure_renderer: bool=False
    class Config:extra='forbid'


def select_preset(stage,data):
    if stage is None:raise ValueError('No live USD stage is open')
    prim=stage.GetPrimAtPath('/World/Ocean');mesh=UsdGeom.Mesh(prim)
    if not mesh:raise ValueError('Create the existing MARLIN ocean first')
    if data.selection=='original':return restore_original(stage,mesh)
    current=configuration(prim)
    if current:
        if not math.isclose(current['bottom_depth_m'],data.bottom_depth_m,rel_tol=1e-8):
            raise ValueError('Select the original preset before changing enclosure depth')
        if data.configure_renderer and not current['configure_renderer']:
            configure_renderer(stage,current);current['configure_renderer']=True
            prim.GetAttribute(KEY).Set(json.dumps(current))
        return {'ok':True,'selection':'engineering_v1','already_selected':True,'configuration':current}
    state=ocean._ocean_animation_state
    if state is None or state['ocean_path']!='/World/Ocean':
        raise ValueError('Start the existing ocean animation before selecting its medium')
    resolution=state['resolution'];points=list(mesh.GetPointsAttr().Get());normals=list(mesh.GetNormalsAttr().Get())
    expected=grid_topology(resolution)
    if list(mesh.GetFaceVertexCountsAttr().Get())!=[4]*len(expected) or list(mesh.GetFaceVertexIndicesAttr().Get())!=[i for f in expected for i in f]:
        raise ValueError('Ocean topology differs from the existing regular grid')
    if mesh.GetNormalsInterpolation()!=UsdGeom.Tokens.vertex:raise ValueError('Expected original smooth vertex normals')
    transform=UsdGeom.XformCache().GetLocalToWorldTransform(prim)
    for row in range(3):
        for col in range(4):
            if abs(float(transform[row][col])-(1 if row==col else 0))>1e-8:
                raise ValueError('The medium requires the existing translation-only ocean transform')
    bound=sum(abs(state['choppiness']*w['amplitude']*w['k']) for w in state['waves'])
    if bound>=1:raise ValueError('Wave horizontal derivative bound permits folding; medium not applied')
    unit=UsdGeom.GetStageMetersPerUnit(stage)
    if not 1e-6<=unit<=100:raise ValueError('Unsupported stage unit scale')
    config=dict(version=1,preset='engineering_v1',resolution=resolution,
                bottom_y_units=-data.bottom_depth_m/unit,bottom_depth_m=data.bottom_depth_m,
                metres_per_unit=unit,horizontal_derivative_bound=bound,
                restart_signature=restart_signature(state),original_double_sided=mesh.GetDoubleSidedAttr().Get(),
                original_binding_targets=[str(p) for p in prim.GetRelationship('material:binding').GetTargets()],
                original_binding_strength=prim.GetRelationship('material:binding').GetMetadata('bindMaterialAs'),
                renderer_before=[],global_before={},configure_renderer=data.configure_renderer)
    enclosed=enclose(points,normals,resolution,config['bottom_y_units'])
    geometry=validate(enclosed[0],topology(resolution),resolution)
    model=json.loads(PRESET.read_text())['material_parameters']
    model.update(ocean_name='Ocean',material_name=MATERIAL,transmission_depth=1/unit)
    material=ocean.OceanMaterialDataModel(**model)
    # Validation above precedes mutations. Roll back ownership on any failure.
    prim.CreateAttribute(KEY,Sdf.ValueTypeNames.String,custom=True).Set(json.dumps(config))
    try:
        result=ocean.bind_ocean_material(material)
        if not result['ok']:raise ValueError(result.get('error','Material binding failed'))
        author_frame(mesh,points,normals,mesh.GetExtentAttr().Get())
        if data.configure_renderer:configure_renderer(stage,config)
        prim.GetAttribute(KEY).Set(json.dumps(config))
    except Exception:
        prim.GetAttribute(KEY).Set(json.dumps(config));restore_original(stage,mesh);raise
    return {'ok':True,'selection':'engineering_v1','material':result,'configuration':config,'geometry':geometry,
            'scientific_water_calibrated':False}


@router.post('/scene/ocean/material/preset',summary='Select the opt-in engineering ocean medium or restore its original')
async def ocean_medium_preset(data:PresetRequest):
    from . import calibration_capture
    if calibration_capture._busy:return {'ok':False,'error':'A capture is running'}
    try:return select_preset(omni.usd.get_context().get_stage(),data)
    except Exception as exc:return {'ok':False,'error':str(exc)}


@router.get('/scene/ocean/material/preset/status',summary='Inspect the selected ocean medium and render enclosure')
async def ocean_medium_status():
    stage=omni.usd.get_context().get_stage()
    prim=stage.GetPrimAtPath('/World/Ocean') if stage else None
    config=configuration(prim)
    if not config:
        mesh=UsdGeom.Mesh(prim)
        return {'ok':True,'selection':'original','vertices':len(mesh.GetPointsAttr().Get()) if mesh else None,
                'faces':len(mesh.GetFaceVertexCountsAttr().Get()) if mesh else None}
    mesh=UsdGeom.Mesh(prim)
    try:
        geometry=validate(list(mesh.GetPointsAttr().Get()),topology(config['resolution']),config['resolution'])
        return {'ok':True,'selection':'engineering_v1','configuration':config,'geometry':geometry,
                'bound_material':str(UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial()[0].GetPath())}
    except Exception as exc:return {'ok':False,'error':str(exc),'configuration':config}
