"""Validate the persisted M6 scene as the first marine stage in a fresh process."""
import ast
import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[3]
OLD=ROOT/'runs/attempt01'
OUT=ROOT/'runs/reload_process01'
PACKAGE=REPO/'experiments/ocean_material_v1/presets/engineering_v1'
ANIMAL='/World/Cetaceans/Dolphin_001'
CAMERA='/World/MarlinOceanM6Camera'
spec=importlib.util.spec_from_file_location('m6_helpers',ROOT/'qa/audit_helpers.py')
helper=importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
plain,write,sha,state_record=(getattr(helper,n) for n in ('plain','write','sha','state_record'))
nodes=[n for n in ast.parse((ROOT/'qa/audit_in_kit.py').read_text()).body
       if isinstance(n,ast.FunctionDef) and n.name in ('animal_record','projected_box')]
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(ROOT/'qa/audit_in_kit.py'),'exec'),globals())


async def main():
    import carb.settings
    import numpy as np
    import omni.kit.app
    import omni.usd
    from pxr import Gf,UsdGeom,UsdShade
    from omni.kit.viewport.utility import get_active_viewport,capture_viewport_to_file
    from cris.madil.render_service import calibration_capture,capture_state
    from cris.madil.render_service.hidef_marine import open_snapshot,restore_settings,settings_record,freeze_stage,gpu_preflight
    from cris.madil.render_service.ocean_medium import configuration,select_preset,PresetRequest,surface_arrays
    from cris.madil.render_service.water_medium_diagnostics import setup_medium_viewport,MediumRequest,capture_hdr
    from cris.madil.render_service.capture_projection import record_projection
    app=omni.kit.app.get_app()
    OUT.mkdir(parents=True,exist_ok=False)
    records=[]
    calibration_capture._busy=True
    capture_state.paused=True
    try:
        for _ in range(90):
            await app.next_update_async()
        source=PACKAGE/'demonstration_scene.usdc'
        reference=json.loads((OLD/'engineering_intersecting/metadata.json').read_text())
        assert sha(source.read_bytes())==reference['scene_sha256']
        stage=open_snapshot(source)
        ok,error=await omni.usd.get_context().attach_stage_async(stage)
        if not ok:
            raise RuntimeError(error)
        viewport=get_active_viewport()
        restore_settings(reference['global_settings'])
        viewport.camera_path=CAMERA
        viewport.fill_frame=False
        viewport.resolution=(512,384)
        for name in ('grid','axis','selection','boundingBox'):
            carb.settings.get_settings().set(f'/persistent/app/viewport/{viewport.id}/guide/{name}/visible',False)
        for name in ('/app/viewport/outline/enabled','/app/viewport/boundingBoxes/enabled'):
            carb.settings.get_settings().set(name,False)
        carb.settings.get_settings().set('/persistent/app/viewport/displayOptions',0)
        omni.usd.get_context().get_selection().clear_selected_prim_paths()
        await asyncio.wait_for(viewport.wait_for_rendered_frames(3),timeout=90)
        viewport.resolution=(512,384)
        setup_medium_viewport(viewport,MediumRequest(renderer='PathTracing'),hide_overlays=False)
        preparation=json.loads((OLD/'preparation.json').read_text())
        unit=preparation['world_units_m']
        UsdGeom.Camera(stage.GetPrimAtPath(CAMERA)).GetClippingRangeAttr().Set(Gf.Vec2f(.01/unit,preparation['camera_physical_far_m']/unit))
        mesh=UsdGeom.Mesh(stage.GetPrimAtPath('/World/Ocean'))
        selected=configuration(mesh.GetPrim())
        assert selected and selected['preset']=='engineering_v1'
        expected_top=np.asarray(surface_arrays(mesh,selected)[0],dtype=np.float32)
        write(OUT/'fresh_process_input.json',dict(source=str(source),source_sha256=reference['scene_sha256'],
              fresh_layer_identifier=stage.GetRootLayer().identifier,preset_survived=True,
              kit_build=app.get_build_version(),camera_far_m=preparation['camera_physical_far_m']))

        async def capture(label,selection):
            directory=OUT/label
            directory.mkdir(exist_ok=False)
            started=time.monotonic()
            try:
                gpu=gpu_preflight(768)
                await asyncio.wait_for(viewport.wait_for_rendered_frames(64),timeout=30)
                projection=record_projection(stage,viewport)
                animal=animal_record(stage)
                assert animal['identity_sha256']==reference['animal']['identity_sha256']
                before=settings_record()
                for name in ('warmup.png','rgb.png'):
                    job=capture_viewport_to_file(viewport,file_path=str(directory/name))
                    await job.wait_for_result(completion_frames=5)
                hdr=await capture_hdr(viewport,directory)
                frozen,_=freeze_stage(stage,0)
                frozen.GetRootLayer().Export(str(directory/'scene.usdc'))
                config=configuration(mesh.GetPrim())
                top=surface_arrays(mesh,config)[0] if config else mesh.GetPointsAttr().Get()
                assert np.array_equal(np.asarray(top,dtype=np.float32),expected_top)
                record=dict(label=label,pose='intersecting',selection=selection,gpu_before=gpu,
                    elapsed_seconds=time.monotonic()-started,rendered_frame_wait_completed=64,
                    configured_sample_count_is_not_hardware_telemetry=True,projection=projection,animal=animal,
                    direct_geometric_bbox_xyxy_px=projected_box(animal,projection),
                    annotation_definition=reference['annotation_definition'],hdr=hdr,global_settings=before,
                    scene_sha256=sha((directory/'scene.usdc').read_bytes()),scene_state=state_record(stage),
                    ocean_top_points_unchanged=True,bound_material=str(UsdShade.MaterialBindingAPI(mesh.GetPrim()).ComputeBoundMaterial()[0].GetPath()),
                    ocean_vertices=len(mesh.GetPointsAttr().Get()),ocean_faces=len(mesh.GetFaceVertexCountsAttr().Get()),
                    preset_configuration=config,layer_identifier=stage.GetRootLayer().identifier)
                write(directory/'metadata.json',record)
                records.append(record)
                write(OUT/'capture_records.json',records)
            except BaseException as exc:
                write(directory/'failure.json',dict(error=str(exc) or type(exc).__name__,traceback=traceback.format_exc()))
                raise
        await asyncio.wait_for(capture('reload_intersecting','engineering_v1'),timeout=60)
        rollback=select_preset(stage,PresetRequest(selection='original'))
        assert rollback['ok']
        await asyncio.wait_for(capture('rollback_intersecting','original'),timeout=60)
        assert sha(source.read_bytes())==reference['scene_sha256']
        write(OUT/'done.json',dict(ok=True,fresh_process_reload=True,rollback=rollback,
              source_bytes_preserved=True,hardware_samples_measured=False))
    except BaseException as exc:
        write(OUT/'audit_failure.json',dict(error=str(exc) or type(exc).__name__,traceback=traceback.format_exc()))
    finally:
        calibration_capture._busy=False
        capture_state.paused=False
        app.post_quit(0 if (OUT/'done.json').exists() else 1)


asyncio.ensure_future(main())
