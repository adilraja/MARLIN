"""Fixed M4 checks on the existing ocean, using one existing viewport."""
import asyncio
import copy
import gc
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from typing import Literal

import carb.settings
import numpy as np
import omni.kit.app
import omni.usd
from pydantic import BaseModel
from pxr import Gf,Sdf,Usd,UsdGeom,UsdShade

from .api import router
from . import calibration_capture,capture_state,ocean,cetacean
from .ocean_medium import configuration,select_preset,PresetRequest,author_frame,surface_arrays
from .ocean_enclosure import topology,validate,grid_topology
from .camera import _active_viewport
from .hidef_marine import gpu_preflight,settings_record,restore_settings,freeze_stage
from .water_diagnostics import DiagnosticCamera,mesh,emissive
from .water_medium_diagnostics import capture_hdr,setup_medium_viewport,MediumRequest
from .calibration_geometry import build_camera
from .capture_projection import record_projection

ROOT=Path(__file__).resolve().parents[6]/'experiments/ocean_material_v1/diagnostics/m4'
DIAGNOSTIC='/World/MarlinOceanIntegrationDiagnostic'
_batch_preview=None


def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')


class BatchPreviewRequest(BaseModel):
    action:Literal['begin','end']
    class Config:extra='forbid'


@router.post('/scene/ocean/material/preset/diagnostic/batch-preview',summary='Hold the existing preview at the declared diagnostic size during a batch')
async def batch_preview(data:BatchPreviewRequest):
    global _batch_preview
    if calibration_capture._busy:return {'ok':False,'error':'Another diagnostic is running'}
    viewport=_active_viewport();stage=omni.usd.get_context().get_stage()
    if viewport is None or stage is None:return {'ok':False,'error':'A live viewport is required'}
    calibration_capture._busy=True;paused=capture_state.paused;capture_state.paused=True
    try:
        product=stage.GetPrimAtPath(viewport.render_product_path)
        mode=product.GetAttribute('omni:rtx:rendermode')
        if data.action=='end':
            if _batch_preview is None:return {'ok':True,'already_ended':True}
            saved=_batch_preview
            if saved['mode_authored']:mode.Set(saved['mode'])
            else:mode.Clear()
            viewport.resolution=tuple(saved['resolution']);viewport.fill_frame=saved['fill_frame']
            restore_settings(saved['settings']);_batch_preview=None
            return {'ok':True,'restored_resolution':saved['resolution'],'restored_mode':saved['mode']}
        if _batch_preview is not None:return {'ok':False,'error':'The diagnostic preview is already active'}
        saved=dict(resolution=list(viewport.resolution),fill_frame=viewport.fill_frame,
                   mode_authored=mode.HasAuthoredValueOpinion(),mode=mode.Get(),settings=settings_record())
        viewport.fill_frame=False;viewport.resolution=(512,384)
        for _ in range(30):await omni.kit.app.get_app().next_update_async()
        try:gpu=gpu_preflight(768)
        except Exception as exc:
            viewport.resolution=tuple(saved['resolution']);viewport.fill_frame=saved['fill_frame']
            return {'ok':False,'error':str(exc),'render_attempted':False}
        mode.Set('PathTracing')
        for _ in range(30):await omni.kit.app.get_app().next_update_async()
        _batch_preview=saved
        return {'ok':True,'resolution':list(viewport.resolution),'mode':mode.Get(),
                'gpu_after_resize_before_mode':gpu,'previous_resolution':saved['resolution']}
    finally:
        capture_state.paused=paused;calibration_capture._busy=False


@router.post('/scene/ocean/material/preset/diagnostic/regression',summary='Run fixed M4 geometry/sampler/controller equivalence checks')
async def regression():
    if calibration_capture._busy:return {'ok':False,'error':'A capture is running'}
    stage=omni.usd.get_context().get_stage();state=ocean._ocean_animation_state
    if stage is None or state is None:return {'ok':False,'error':'Start the existing marine scene first'}
    surface=UsdGeom.Mesh(stage.GetPrimAtPath('/World/Ocean'))
    if configuration(surface.GetPrim()):return {'ok':False,'error':'Select original before the regression transaction'}
    calibration_capture._busy=True
    paused=capture_state.paused;capture_state.paused=True
    saved_ocean=copy.deepcopy(state)
    old_swimmer=cetacean._cetacean_swim_state;old_subscription=cetacean._cetacean_swim_subscription
    animal=stage.GetPrimAtPath('/World/Cetaceans/Dolphin_001')
    saved_ops={a.GetName():a.Get() for a in animal.GetAttributes() if a.GetName().startswith('xformOp')}
    directory=Path(tempfile.mkdtemp(prefix='regression_',dir=str(ROOT)))
    result={}
    try:
        phases=[]
        for phase in (0,.5,1,2,4):
            state['elapsed']=phase
            p,n,e=ocean._calculate_animated_ocean(state,phase)
            author_frame(surface,p,n,e)
            positions=[(0,0),(50,50),(-500,400),(3000,-2500)]
            heights=[ocean._sample_ocean_surface_height(x,z) for x,z in positions]
            choice=select_preset(stage,PresetRequest(configure_renderer=False))
            assert choice['ok']
            config=configuration(surface.GetPrim());arrays=surface_arrays(surface,config)
            top_delta=float(np.max(np.abs(np.array(arrays[0])-np.array(p))))
            normal_delta=float(np.max(np.abs(np.array(arrays[1])-np.array(n))))
            sampler_delta=max(abs(a-ocean._sample_ocean_surface_height(x,z)) for (x,z),a in zip(positions,heights))
            geometry=validate(list(surface.GetPointsAttr().Get()),topology(state['resolution']),state['resolution'])
            assert top_delta<=1e-6 and normal_delta<=1e-6 and sampler_delta<=1e-8
            phases.append(dict(phase_seconds=phase,top_vertex_max_error_units=top_delta,
                top_normal_max_error=normal_delta,sampler_max_error_units=sampler_delta,geometry=geometry,
                horizontal_derivative_bound=config['horizontal_derivative_bound']))
            select_preset(stage,PresetRequest(selection='original'))
            await omni.kit.app.get_app().next_update_async()
        controllers=[]
        for boundary_x in (0,2200):
            trajectories=[]
            for selection in ('original','engineering_v1'):
                ocean._ocean_animation_state=copy.deepcopy(saved_ocean)
                working=ocean._ocean_animation_state;working['elapsed']=0;working['accumulator']=0
                p,n,e=ocean._calculate_animated_ocean(working,0);author_frame(surface,p,n,e)
                UsdGeom.XformCommonAPI(animal).SetTranslate(Gf.Vec3d(boundary_x,-5,0))
                started=await cetacean.start_cetacean_swimming(cetacean.CetaceanSwimDataModel(
                    body_animation=False,follow_ocean_surface=True,depth_below_surface=25))
                assert started['ok']
                select_preset(stage,PresetRequest(selection=selection,configure_renderer=False))
                capture_state.paused=False
                trajectory=[]
                for step in range(20):
                    swimmer=cetacean._cetacean_swim_state
                    swimmer['target_depth_below_surface']=25 if step<7 else 80 if step<14 else 10
                    event=SimpleNamespace(payload={'dt':.3})
                    ocean._update_animated_ocean(event);cetacean._update_cetacean_swimming(event)
                    trajectory.append([swimmer[k] for k in ('x','z','current_y','current_depth_below_surface',
                        'actual_depth_below_surface','heading','pitch','bank','boundary_avoidance')])
                    if step%5==4:
                        capture_state.paused=True
                        await omni.kit.app.get_app().next_update_async()
                        capture_state.paused=False
                capture_state.paused=True
                trajectories.append(trajectory)
                select_preset(stage,PresetRequest(selection='original'))
            delta=float(np.max(np.abs(np.array(trajectories[0],dtype=float)-np.array(trajectories[1],dtype=float))))
            assert delta<=1e-8
            controllers.append(dict(initial_x_units=boundary_x,steps=20,dt_seconds=.3,max_output_error_units=delta,
                                    original=trajectories[0],engineering=trajectories[1]))
        result={'ok':True,'phase_checks':phases,'controller_checks':controllers,
                'controller':'Existing cetacean swimming update; dive/surface and boundary paths exercised',
                'waves':'Existing ocean callback and sampler; no substitute wave/controller equations'}
        write(directory/'result.json',result)
        return {'ok':True,'directory':str(directory),'phase_count':len(phases),'controller_case_count':len(controllers)}
    except Exception as exc:
        result={'ok':False,'error':str(exc) or type(exc).__name__};write(directory/'result.json',result);return {**result,'directory':str(directory)}
    finally:
        capture_state.paused=True
        if configuration(surface.GetPrim()):select_preset(stage,PresetRequest(selection='original'))
        ocean._ocean_animation_state=saved_ocean
        p,n,e=ocean._calculate_animated_ocean(saved_ocean,saved_ocean['elapsed']);author_frame(surface,p,n,e)
        cetacean._cetacean_swim_subscription=old_subscription;cetacean._cetacean_swim_state=old_swimmer
        for name,value in saved_ops.items():animal.GetAttribute(name).Set(value)
        for attr in list(animal.GetAttributes()):
            if attr.GetName().startswith('xformOp') and attr.GetName() not in saved_ops:animal.RemoveProperty(attr.GetName())
        capture_state.paused=paused;calibration_capture._busy=False


class CaptureRequest(BaseModel):
    selection: Literal['original','engineering_v1']='engineering_v1'
    phase_seconds: Literal[0,.5,1,2,4]=0
    view: Literal['nadir','oblique','inside','exit','edge','outer_edge']='oblique'
    advance_live: bool=False
    class Config:extra='forbid'


class OceanCamera(DiagnosticCamera):
    def camera_position(self):
        x,y,z=super().camera_position()
        return x+12,y,z


@router.post('/scene/ocean/material/preset/diagnostic/capture',summary='Capture the integrated ocean at fixed wave phases with one viewport')
async def capture_integrated(data:CaptureRequest):
    try:return await asyncio.wait_for(_capture_integrated(data),timeout=90)
    except asyncio.TimeoutError:return {'ok':False,'error':'Bounded integration capture timed out; temporary layer/settings cleanup executed'}


async def _capture_integrated(data):
    if calibration_capture._busy:return {'ok':False,'error':'A capture is running','render_attempted':False}
    if data.advance_live:
        from . import camera as camera_control
        if cetacean._cetacean_swim_state is not None or camera_control._chase_camera_state is not None:
            return {'ok':False,'error':'Live-advance inspection requires chase and animal controllers stopped so the declared camera and animal pose remain fixed','render_attempted':False}
    gc.collect()
    try:gpu=gpu_preflight(768)
    except Exception as exc:return {'ok':False,'error':str(exc),'render_attempted':False}
    stage=omni.usd.get_context().get_stage();state=ocean._ocean_animation_state;viewport=_active_viewport()
    if stage is None or state is None or viewport is None:return {'ok':False,'error':'An existing animated ocean and viewport are required'}
    if stage.GetPrimAtPath(DIAGNOSTIC):return {'ok':False,'error':'Diagnostic namespace is already occupied'}
    calibration_capture._busy=True;paused=capture_state.paused;capture_state.paused=True
    before=settings_record();settings=carb.settings.get_settings()
    old_camera=str(viewport.camera_path);old_resolution=tuple(viewport.resolution);old_fill=viewport.fill_frame
    elapsed,accumulator=state['elapsed'],state['accumulator']
    original_edit=stage.GetEditTarget();session=stage.GetSessionLayer()
    root_layer=stage.GetRootLayer()
    owned_paths=[DIAGNOSTIC,'/WaterDiagnostic','/Render/Vars/MarlinMediumHdr']
    owned_before={p:bool(stage.GetPrimAtPath(p)) for p in owned_paths}
    # Kit may author camera/product overrides directly on the root layer while
    # UI callbacks run. Preserve the exact live specs as well as the overlay.
    snapshot=Sdf.Layer.CreateAnonymous('marlin_m4_live_specs.usda')
    saved_specs={}
    for path in ('/World/Ocean',viewport.render_product_path,old_camera):
        present=bool(root_layer.GetPrimAtPath(path));saved_specs[path]=present
        if present:
            Sdf.CreatePrimInLayer(snapshot,Sdf.Path(path).GetParentPath())
            Sdf.CopySpec(root_layer,path,snapshot,path)
    layer=Sdf.Layer.CreateAnonymous('marlin_m4_transaction.usda');session.subLayerPaths.insert(0,layer.identifier)
    stage.SetEditTarget(layer)
    root=ROOT/'captures';root.mkdir(exist_ok=True)
    directory=Path(tempfile.mkdtemp(prefix=data.view+'_',dir=str(root)))
    # Fixed installed guide settings, rather than changing any animal visibility.
    guide_paths=[f'/persistent/app/viewport/{viewport.id}/guide/{name}/visible' for name in ('grid','axis','selection','boundingBox')]
    guide_paths+=['/app/viewport/outline/enabled','/app/viewport/boundingBoxes/enabled']
    guides={p:settings.get(p) for p in guide_paths}
    try:
        select_preset(stage,PresetRequest(selection='original'))
        state['elapsed']=data.phase_seconds;state['accumulator']=0
        surface=UsdGeom.Mesh(stage.GetPrimAtPath('/World/Ocean'))
        p,n,e=ocean._calculate_animated_ocean(state,state['elapsed']);author_frame(surface,p,n,e)
        unit=UsdGeom.GetStageMetersPerUnit(stage)
        c=OceanCamera(meters_per_scene_unit=unit,image_width_px=512,image_height_px=384,
            focal_length_mm=35,pixel_pitch_um=40,height_above_target_m=.5 if data.view in ('inside','exit') else 4,
            target_plane_y_m=-1,target_width_m=.18,target_height_m=.18,pitch_deg=40 if data.view=='oblique' else 0)
        camera=build_camera(stage,c,DIAGNOSTIC+'/Camera')
        if data.view in ('exit','edge','outer_edge'):
            matrix=camera.GetCamera(Usd.TimeCode.Default()).transform
            if data.view=='exit':
                matrix=Gf.Matrix4d(1)
                for i,row in enumerate(((1,0,0),(0,0,1),(0,-1,0))):matrix.SetRow(i,Gf.Vec4d(*row,0))
                matrix.SetRow(3,Gf.Vec4d(12/unit,-.5/unit,0,1))
            else:matrix.SetRow(3,Gf.Vec4d((80 if data.view=='outer_edge' else 79)/unit,3/unit,0,1))
            camera.MakeMatrixXform().Set(matrix)
        target=mesh(stage,DIAGNOSTIC+'/Target',[(11.91,-1,-.09),(11.91,-1,.09),(12.09,-1,.09),(12.09,-1,-.09)],[[0,1,2,3]],unit)
        emissive(stage,target,'M4Fiducial',(10,10,10))
        background=mesh(stage,DIAGNOSTIC+'/Background',[(10,-1.8,-2),(10,-1.8,2),(14,-1.8,2),(14,-1.8,-2)],[[0,1,2,3]],unit)
        emissive(stage,background,'M4Black',(0,0,0))
        viewport.fill_frame=False;viewport.resolution=(512,384);viewport.camera_path=str(camera.GetPath())
        for path in guide_paths:settings.set(path,False)
        settings.set('/rtx/fog/enabled',False)
        settings.set('/exts/cris.madil.render_service/underwaterCue/enabled',False)
        for _ in range(30):await omni.kit.app.get_app().next_update_async()
        stage.SetEditTarget(layer)
        viewport.resolution=(512,384)
        # M3 capture settings are applied only to the temporary diagnostic camera/product layer.
        setup_medium_viewport(viewport,MediumRequest(renderer='PathTracing'),hide_overlays=False)
        if data.selection=='engineering_v1':select_preset(stage,PresetRequest(configure_renderer=False))
        live_frames=[]
        if data.advance_live:
            capture_state.paused=False
            for _ in range(10):
                await omni.kit.app.get_app().next_update_async()
                live_frames.append({'elapsed':state['elapsed'],'binding':str(UsdShade.MaterialBindingAPI(surface.GetPrim()).ComputeBoundMaterial()[0].GetPath()),'points':len(surface.GetPointsAttr().Get())})
            capture_state.paused=True
        await asyncio.wait_for(viewport.wait_for_rendered_frames(64),timeout=30)
        from omni.kit.viewport.utility import capture_viewport_to_file
        for name in ('warmup.png','rgb.png'):
            job=capture_viewport_to_file(viewport,file_path=str(directory/name));await job.wait_for_result(completion_frames=5)
        hdr=await capture_hdr(viewport,directory)
        frozen,count=freeze_stage(stage,Usd.TimeCode.Default());frozen.GetRootLayer().Export(str(directory/'scene.usdc'))
        config=configuration(surface.GetPrim())
        geometry=validate(list(surface.GetPointsAttr().Get()),topology(state['resolution']),state['resolution']) if config else {'open_original_surface':True}
        metadata=dict(c.metadata(),**hdr,request=data.dict(),gpu_before=gpu,effective_phase_seconds=state['elapsed'],
            integrated_geometry=geometry,material=str(UsdShade.MaterialBindingAPI(surface.GetPrim()).ComputeBoundMaterial()[0].GetPath()),
            live_frames=live_frames,scene_sha256=hashlib.sha256((directory/'scene.usdc').read_bytes()).hexdigest(),
            renderer_instance_policy='Existing live viewport; no second USD context or Hydra renderer',scientific_water_calibrated=False,
            camera_override=data.view in ('edge','outer_edge','exit'),viewport_resolution=list(viewport.resolution))
        metadata.update(record_projection(stage,viewport));write(directory/'metadata.json',metadata)
        return {'ok':True,'directory':str(directory),'metadata':metadata}
    except Exception as exc:
        result={'ok':False,'error':str(exc) or type(exc).__name__,'directory':str(directory)};write(directory/'failure.json',result);return result
    finally:
        capture_state.paused=True
        stage.SetEditTarget(original_edit);session.subLayerPaths.remove(layer.identifier)
        viewport.camera_path=old_camera;viewport.resolution=old_resolution;viewport.fill_frame=old_fill
        for path,present in saved_specs.items():
            if present:Sdf.CopySpec(snapshot,path,root_layer,path)
        for path,present in owned_before.items():
            if not present:
                for owner in (root_layer,session):
                    with Usd.EditContext(stage,owner):stage.RemovePrim(path)
        state['elapsed']=elapsed;state['accumulator']=accumulator
        restore_settings(before);restore_settings(guides)
        restored_attributes={}
        for name in ('points','normals','faceVertexCounts','faceVertexIndices','doubleSided','marlin:waterMedium:config'):
            path='/World/Ocean.'+name
            old_spec=snapshot.GetAttributeAtPath(path);new_spec=root_layer.GetAttributeAtPath(path)
            restored_attributes[name]=bool(old_spec and new_spec and old_spec.default==new_spec.default) if old_spec else not bool(new_spec)
        write(directory/'restoration.json',dict(ocean_root_attributes_restored=restored_attributes,
            camera_restored=str(viewport.camera_path)==old_camera,resolution_restored=tuple(viewport.resolution)==old_resolution,
            fill_frame_restored=viewport.fill_frame==old_fill,
            temporary_namespaces_removed=all(owned_before[p] or not stage.GetPrimAtPath(p) for p in owned_paths),
            ocean_clock_restored=state['elapsed']==elapsed and state['accumulator']==accumulator))
        capture_state.paused=paused;calibration_capture._busy=False
