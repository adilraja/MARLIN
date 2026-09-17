"""Snapshot/replay using one existing Kit renderer and a restored live stage."""
import asyncio
import gc
import hashlib
import json
import math
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime, timezone

import carb.settings
import omni.timeline
import omni.kit.app
import omni.usd
from pxr import Sdf, Usd, UsdGeom
from pydantic import Field
from typing import Literal
from pydantic import BaseModel
from .api import router
from .hidef_api import HiDefRequest
from .hidef_camera import configuration
from .sony_camera import configuration as sony_configuration
from .calibration_geometry import build_camera
from .capture_projection import record_projection
from . import calibration_capture
from . import capture_state
from .hidef_maps import export_maps
from .underwater_cue import UNDERWATER_FOG_SETTING_PATHS
from .water_material import RTX_WATER_SETTINGS

ROOT = Path(__file__).resolve().parents[6]/'artifacts/hidef_marine'
CAMERA_PATH = '/MarlinHiDefCapture/Camera'
SETTING_KEYS = (
    '/rtx/rendermode', '/rtx/post/tonemap/op', '/rtx/post/tonemap/exposureBias',
    '/rtx/post/tonemap/filmIso', '/rtx/post/tonemap/cameraShutter',
    '/rtx/post/tonemap/fNumber', '/rtx/post/histogram/enabled',
    '/rtx/fog/enabled', '/rtx/raytracing/fractionalCutoutOpacity',
    '/rtx/translucency/enabled', '/rtx/reflections/enabled',
    '/rtx/pathtracing/spp', '/rtx/pathtracing/totalSpp',
)


class MarineRequest(HiDefRequest):
    projection_probe: bool = False
    target_x_m: float = Field(default=-3,ge=-1000,le=1000)
    target_z_m: float = Field(default=0,ge=-1000,le=1000)


class TileDiagnosticRequest(BaseModel):
    mode: Literal['baseline','guard64','rendered_frames','pt_denoised','pt_raw','pt_raw_8192','sdk_pair','sdk_single','sdk_smoke','sdk_low_repeat'] = 'baseline'

    class Config:
        extra = 'forbid'


def settings_record():
    settings = carb.settings.get_settings()
    return {key:settings.get(key) for key in sorted(set(SETTING_KEYS)|set(UNDERWATER_FOG_SETTING_PATHS)|set(RTX_WATER_SETTINGS))}


def same_settings(a,b):
    """USD render-setting roundtrips can quantize doubles to float32."""
    if isinstance(a,dict) and isinstance(b,dict):
        return a.keys()==b.keys() and all(same_settings(a[k],b[k]) for k in a)
    if isinstance(a,(list,tuple)) and isinstance(b,(list,tuple)):
        return len(a)==len(b) and all(same_settings(x,y) for x,y in zip(a,b))
    if type(a) in (int,float) and type(b) in (int,float):
        return math.isclose(a,b,rel_tol=1e-7,abs_tol=1e-9)
    return type(a)==type(b) and a==b


def restore_settings(record):
    """Undo Kit's automatic stage-open defaults; never apply a new preset."""
    settings = carb.settings.get_settings()
    for key,value in record.items():
        if settings.get(key)==value:
            continue
        if value is None:
            settings.destroy_item(key)
        else:
            settings.set(key,value)


def gpu_preflight(required_free_mib=768):
    """Fail closed before allocating another renderer on the local workstation."""
    result = subprocess.run(['nvidia-smi','--query-gpu=index,memory.total,memory.free,driver_version',
                             '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=10,check=True)
    row = result.stdout.splitlines()[0].split(',')
    record = dict(device_index=int(row[0]),total_mib=int(row[1]),free_mib=int(row[2]),driver=row[3].strip())
    if record['free_mib']<required_free_mib:
        raise ValueError('Insufficient GPU headroom before capture: %s MiB free; require at least %s MiB. No render attempted.'%(record['free_mib'],required_free_mib))
    return record


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


def freeze_stage(source, time_code):
    """Flatten composition, then replace animated values by one evaluated sample.

    Procedural ocean/mesh deformations are already authored as current points.
    Sampling SkelAnimation attributes freezes skeletal pose too, independently
    of the main timeline. This function never writes to the source stage.
    """
    frozen = Usd.Stage.Open(source.Flatten())
    sampled = 0
    for prim in frozen.TraverseAll():
        for attr in prim.GetAttributes():
            if attr.GetNumTimeSamples():
                value = attr.Get(time_code)
                attr.Clear()
                if value is not None:
                    attr.Set(value)
                sampled += 1
    return frozen, sampled


def open_snapshot(path):
    """Read disk into a private layer, bypassing USD's dirty layer cache.

    Kit authors viewport products/exposure onto an attached layer. Reopening
    its filename with Stage.Open can reuse that dirty layer on the next replay.
    Snapshots are flattened with resolved asset paths; no source layer is edited.
    """
    layer = Sdf.Layer.OpenAsAnonymous(str(path))
    if layer is None:
        raise ValueError('Could not read snapshot from disk')
    return Usd.Stage.Open(layer)


def asset_dependencies(stage):
    records = {}
    for prim in stage.TraverseAll():
        for attr in prim.GetAttributes():
            if attr.GetTypeName() not in (Sdf.ValueTypeNames.Asset,Sdf.ValueTypeNames.AssetArray):
                continue
            value = attr.Get()
            values = list(value) if attr.GetTypeName()==Sdf.ValueTypeNames.AssetArray and value is not None else [value]
            for asset in values:
                if not asset or not asset.path:
                    continue
                path = asset.resolvedPath or asset.path
                if path in records:
                    continue
                local = Path(path)
                runtime = bool(set(local.parts)&{'_build','extscache','__pycache__','.cache'}) or local.suffix=='.pyc'
                hashable = not runtime and local.is_file()
                records[path] = dict(path=path, authored_path=asset.path,
                                     sha256=digest(local) if hashable else None,
                                     status='local_hashed' if hashable else 'runtime_or_unresolved')
    return list(records.values())


def animals_record(stage, config, translation):
    parent = stage.GetPrimAtPath('/World/Cetaceans')
    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(),['default','render','proxy'])
    records = []
    for prim in parent.GetChildren() if parent else []:
        bounds = cache.ComputeWorldBound(prim).ComputeAlignedRange()
        if bounds.IsEmpty():
            continue
        lo,hi = bounds.GetMin(),bounds.GetMax()
        projected = [config.project(tuple(p*config.meters_per_scene_unit-t for p,t in zip((x,y,z),translation)))
                     for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])]
        xs,ys=zip(*projected)
        records.append(dict(path=str(prim.GetPath()),bounds_min_scene_units=list(lo),bounds_max_scene_units=list(hi),
                            projected_bounds_xyxy_px=[min(xs),min(ys),max(xs),max(ys)],
                            bounds_intersect_frame=max(xs)>0 and min(xs)<config.image_width_px and max(ys)>0 and min(ys)<config.image_height_px,
                            visibility=str(UsdGeom.Imageable(prim).ComputeVisibility()),
                            note='Projected world AABB only, not segmentation or evidence of visibility through water.'))
    return records


async def run_capture(data=None, replay_id=None, camera_model='hidef', diagnostic=None):
    if calibration_capture._busy:
        return {'ok':False,'error':'Another camera capture is running'}
    calibration_capture._busy = True
    capture_state.paused = True
    timeline = omni.timeline.get_timeline_interface()
    was_playing = timeline.is_playing()
    original_time = timeline.get_current_time()
    timeline.pause()
    try:
        return await asyncio.wait_for(_run(data,replay_id,camera_model,diagnostic),timeout=600)
    except Exception as exc:
        return {'ok':False,'error':str(exc) or type(exc).__name__}
    finally:
        timeline.set_current_time(original_time)
        if was_playing:
            timeline.play()
        capture_state.paused = False
        calibration_capture._busy = False


async def _run(data, replay_id, camera_model='hidef', diagnostic=None):
    if camera_model not in ('hidef', 'sony'):
        raise ValueError('Unsupported camera profile')
    sony = camera_model == 'sony'
    root = ROOT.parent/'sony_marine' if sony else ROOT
    camera_path = '/MarlinSonyCapture/Camera' if sony else CAMERA_PATH
    prefix = 'sony_' if sony else 'oblique_'
    main_context = omni.usd.get_context()
    main_stage = main_context.get_stage()
    if main_stage is None:
        raise ValueError('Load the marine scene first')
    # get_stage() may expose a weak Python handle. A separate USD StageCache
    # owns a strong reference even when Kit removes the stage from its cache.
    retained_stages = Usd.StageCache()
    retained_stages.Insert(main_stage)
    before = settings_record()
    # A failed coroutine can leave USD handles in traceback reference cycles.
    # Collect unreachable objects before checking whether another render fits.
    gc.collect()
    gpu = gpu_preflight()
    from omni.kit.viewport.utility import get_active_viewport
    main_view = get_active_viewport()
    main_camera = str(main_view.camera_path) if main_view else None
    main_resolution = tuple(main_view.resolution) if main_view else None
    if replay_id is not None:
        if not re.fullmatch(prefix+r'[a-z0-9_]+',replay_id):
            raise ValueError('Use the capture_id from a successful marine capture')
        directory = root/replay_id
        saved = json.loads((directory/'metadata.json').read_text())
        if digest(directory/'scene.usdc') != saved['scene_sha256']:
            raise ValueError('Saved scene hash mismatch')
        if not same_settings(before,saved['renderer_settings']):
            raise ValueError('Renderer settings differ from the saved capture; refusing to change global settings. Restore the saved settings before replay.')
        for dependency in saved['asset_dependencies']:
            if dependency['sha256'] and digest(dependency['path']) != dependency['sha256']:
                raise ValueError('Asset dependency changed: '+dependency['path'])
        config = (sony_configuration(saved['config']['downsample']) if sony else
                  configuration(saved['config']['roll_deg'],saved['config']['downsample'],saved['config']['aperture_basis']))
        if sony and config.downsample != 8:
            raise ValueError('Native Sony rendering is deferred; only preview replay is enabled')
        replay_scene = directory/'scene.usdc'
        frozen = open_snapshot(replay_scene)
        extra = {key:saved[key] for key in ('snapshot','camera_translation_m','camera_target_xz_m',
                  'animals','asset_dependencies','environment_status')}
        if saved.get('projection_probe'):
            extra.update(projection_probe=True,targets=saved['targets'])
        if diagnostic is not None:
            if sony or config.downsample!=1:
                raise ValueError('Tile diagnostics require a native HiDef snapshot')
            extra['tile_diagnostic']=dict(mode=diagnostic,source_capture=replay_id,
                source_scene_sha256=saved['scene_sha256'],
                tile_indices=[3] if diagnostic=='sdk_smoke' else [3,3,3] if diagnostic in ('sdk_single','sdk_low_repeat') else ([3,4,3,4] if diagnostic=='sdk_pair' else [3,4,4,5,11,12,13]),purpose='Focused overlaps and identical-tile repeat; not a complete image')
    else:
        if data.downsample==1 and not getattr(data, 'allow_full_resolution', False):
            raise ValueError('Full resolution requires allow_full_resolution=true and adequate GPU memory')
        if not main_stage.GetPrimAtPath('/World/Ocean') or not main_stage.GetPrimAtPath('/World/Cetaceans'):
            raise ValueError('Expected /World/Ocean and /World/Cetaceans in the live marine scene')
        if UsdGeom.GetStageUpAxis(main_stage)!='Y' or not math.isclose(UsdGeom.GetStageMetersPerUnit(main_stage),.01):
            raise ValueError('Marine capture requires the current Y-up centimetre stage')
        config = (sony_configuration(data.downsample) if sony else
                  configuration(data.roll_deg,data.downsample,data.aperture_basis))
        seconds = omni.timeline.get_timeline_interface().get_current_time()
        time_code = seconds*main_stage.GetTimeCodesPerSecond()
        # No await until the copy is complete: main-thread animation cannot
        # advance between snapshot sampling and flattened-stage acquisition.
        frozen,sampled = freeze_stage(main_stage,Usd.TimeCode(time_code))
        # Viewport-owned render products are transient, context-specific data.
        # Do not copy their render buffers/settings into the isolated context.
        removed_render_products = bool(frozen.GetPrimAtPath('/Render'))
        if removed_render_products:
            frozen.RemovePrim('/Render')
        center = config.ray_plane(config.image_width_px/2,config.image_height_px/2)
        translation = (data.target_x_m-center[0],0,data.target_z_m-center[2])
        extra = dict(snapshot=dict(captured_utc=datetime.now(timezone.utc).isoformat(),
                    source_timeline_seconds=seconds,source_time_code=time_code,
                    frozen_time_sampled_attributes=sampled,
                    viewport_render_tree_excluded=removed_render_products,
                    method='Flattened USD composition with every time-sampled attribute evaluated at the recorded time; current procedural mesh points retained.'),
                    camera_translation_m=translation,camera_target_xz_m=[data.target_x_m,data.target_z_m],
                    animals=animals_record(frozen,config,translation),
                    asset_dependencies=asset_dependencies(frozen),
                    environment_status='Snapshot of existing presentation environment, not a certified controlled survey preset. Lighting, water and animal geometry are not modified.')
        build_camera(frozen,config,camera_path,translation)
        if getattr(data,'projection_probe',False):
            # Diagnostic changes exist only on the frozen copy. Same camera,
            # renderer, capture code, resolution and restoration as marine RGB.
            from .calibration_geometry import build_stage
            from pxr import Gf
            for path in ('/World','/Environment'):
                prim=frozen.GetPrimAtPath(path)
                if prim and prim.IsA(UsdGeom.Imageable):
                    UsdGeom.Imageable(prim).MakeInvisible()
            build_stage(frozen,config)
            UsdGeom.Xformable(frozen.GetPrimAtPath('/Calibration')).AddTranslateOp().Set(
                Gf.Vec3d(*(v/config.meters_per_scene_unit for v in translation)))
            extra['projection_probe']=True
            extra['targets']=config.targets()
            extra['environment_status']='Diagnostic targets on frozen marine copy; live environment untouched; not wildlife data'
    if main_view is None or not main_view.updates_enabled:
        raise ValueError('An active updating viewport is required')
    retained_stages.Insert(frozen)
    root.mkdir(parents=True,exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix=prefix,dir=root))
    if replay_id is not None:
        # Preserve the exact verified source bytes. USD crate reserialization
        # can change binary layout even when the layer content is identical.
        shutil.copyfile(replay_scene,directory/'scene.usdc')
    else:
        frozen.GetRootLayer().Export(str(directory/'scene.usdc'))
    if replay_id is not None and digest(directory/'scene.usdc') != saved['scene_sha256']:
        raise ValueError('Replay copy differs from the saved scene before rendering; refusing a contaminated replay')
    (directory/'snapshot_inputs.json').write_text(json.dumps(dict(config=config.metadata(),**extra,
                        renderer_settings=before,gpu_preflight=gpu,status='render_pending'),indent=2)+'\n')
    original_fill = main_view.fill_frame
    original_selection = main_context.get_selection().get_selected_prim_paths()
    settings = carb.settings.get_settings()
    display_key = '/persistent/app/viewport/displayOptions'
    original_display = settings.get(display_key)
    # Fixed diagnostic presets only: never accept arbitrary renderer settings.
    diagnostic_overrides = {}
    if diagnostic in ('pt_denoised','pt_raw','pt_raw_8192','sdk_pair','sdk_single','sdk_smoke','sdk_low_repeat'):
        diagnostic_overrides = {'/rtx/rendermode':'PathTracing',
            '/rtx/pathtracing/spp':64 if diagnostic=='pt_raw_8192' else 8,
            '/rtx/pathtracing/totalSpp':8192 if diagnostic=='pt_raw_8192' else (16 if diagnostic in ('sdk_smoke','sdk_low_repeat') else 1024),
            '/rtx/pathtracing/optixDenoiser/enabled':diagnostic=='pt_denoised'}
    diagnostic_before = {key:settings.get(key) for key in diagnostic_overrides}
    from omni.kit.viewport.utility import capture_viewport_to_file
    metadata = config.metadata()
    try:
        # One context/one renderer. Retain main_stage as a strong CPU reference.
        ok,error = await main_context.attach_stage_async(frozen)
        if not ok:
            raise RuntimeError(error)
        restore_settings(before)
        restore_settings(diagnostic_overrides)
        if diagnostic_overrides:
            # Renderer switches can recreate the viewport product and restore
            # its UI-sized buffer asynchronously. Let that transition finish
            # before selecting the native tile camera and its resolution.
            await asyncio.wait_for(main_view.wait_for_rendered_frames(3),timeout=30)
        if diagnostic is not None:
            extra['tile_diagnostic']['renderer_overrides'] = diagnostic_overrides
            extra['tile_diagnostic']['settings_before_override'] = diagnostic_before
        main_context.get_selection().clear_selected_prim_paths()
        settings.set(display_key,0)
        main_view.camera_path = camera_path
        main_view.fill_frame = False
        if config.downsample==1:
            from .native_tiles import capture_tiles
            metadata.update(await capture_tiles(frozen,main_view,config,directory,gpu_preflight,diagnostic))
        else:
            main_view.resolution = (config.image_width_px,config.image_height_px)
            for _ in range(90):
                await omni.kit.app.get_app().next_update_async()
            main_view.fill_frame = False
            main_view.resolution = (config.image_width_px,config.image_height_px)
            for _ in range(30):
                await omni.kit.app.get_app().next_update_async()
            if tuple(main_view.resolution)!=(config.image_width_px,config.image_height_px):
                raise RuntimeError('Viewport resolution mismatch')
            for filename in ('warmup.png','rgb.png'):
                capture = capture_viewport_to_file(main_view,file_path=str(directory/filename))
                await capture.wait_for_result(completion_frames=5)
            metadata.update(record_projection(frozen,main_view))
    finally:
        try:
            ok,error = await main_context.attach_stage_async(main_stage)
        finally:
            # Restore overrides even if stage restoration itself fails.
            restore_settings(before)
            restore_settings(diagnostic_before)
        if not ok:
            raise RuntimeError('Could not restore the live stage: '+error)
        main_view.camera_path = main_camera
        main_view.resolution = main_resolution
        main_view.fill_frame = original_fill
        main_context.get_selection().set_selected_prim_paths(original_selection,False)
        if original_display is None:
            settings.destroy_item(display_key)
        else:
            settings.set(display_key,original_display)
        # The main context owns its restored stage again. Do not retain an
        # extra cache ownership of either stage after the scoped render ends.
        retained_stages.Clear()
        frozen=None
        gc.collect()
    for field in ('targets','expected_bbox_xywh_px','gsd_cm_px'):
        metadata.pop(field,None)
    metadata.update(extra)
    metadata.update(test_kind=camera_model+('_marine_snapshot_native_tiled' if config.downsample==1 else '_marine_snapshot_preview'),capture_id=directory.name,
                    replay_of=replay_id,renderer_settings=before,
                    gpu_preflight=gpu,
                    scene_sha256=digest(directory/'scene.usdc'),scene_file='scene.usdc',
                    rendered_image='rgb.png' if diagnostic is None else None,
                    renderer_lifecycle='Existing viewport temporarily displays frozen scene; live stage, camera, resolution, selection and controller updates restored afterwards. No second Hydra renderer.',
                    reproducibility='Frozen scene, camera and hashed local dependencies; RGB is not promised bitwise identical across RTX frames, drivers or machines.',
                    biological_detectability_tested=False,validation_status='rendered_pending_visual_review',
                    directional_gsd=export_maps(directory,config,extra['camera_translation_m']) if diagnostic is None else {'status':'not generated for tile-only diagnostic'})
    if diagnostic is not None:
        metadata['test_kind'] = 'hidef_native_tile_diagnostic_not_full_image'
        metadata['validation_status'] = 'diagnostic_only_not_certified'
    metadata['camera_position_m'] = [a+b for a,b in zip(config.camera_position(),extra['camera_translation_m'])]
    metadata['restoration_checks'] = dict(
        original_stage_retained=main_stage==main_context.get_stage(),
        renderer_settings_preserved=same_settings(before,settings_record()),
        camera_preserved=str(main_view.camera_path)==main_camera,
        resolution_preserved=tuple(main_view.resolution)==main_resolution,
        fill_frame_preserved=main_view.fill_frame==original_fill,
        selection_preserved=main_context.get_selection().get_selected_prim_paths()==original_selection,
        display_options_preserved=settings.get(display_key)==original_display)
    metadata['restoration_checks']['diagnostic_settings_preserved'] = same_settings(
        diagnostic_before,{key:settings.get(key) for key in diagnostic_before})
    metadata['renderer_settings_after_restore'] = settings_record()
    metadata['renderer_comparison_tolerance'] = 'Only float32 roundtrip tolerance: relative 1e-7, absolute 1e-9; strings/bools exact.'
    metadata['main_viewport_preserved'] = all(metadata['restoration_checks'].values())
    metadata['output_sha256'] = {p.name:digest(p) for p in directory.iterdir() if p.suffix in ('.png','.npz')}
    (directory/'metadata.json').write_text(json.dumps(metadata,indent=2,allow_nan=False)+'\n')
    if metadata.get('native_tiling') and not metadata['native_tiling']['overlaps_passed']:
        return dict(ok=False,error='Native tile overlap validation failed; image is diagnostic only',directory=str(directory))
    if not metadata['main_viewport_preserved']:
        return dict(ok=False,error='Main viewport or renderer settings changed during capture',directory=str(directory))
    return dict(ok=True,capture_id=directory.name,directory=str(directory),
                image=str(directory/'rgb.png') if diagnostic is None else None,metadata=str(directory/'metadata.json'),
                gsd_maps=str(directory/'directional_gsd.npz') if diagnostic is None else None,
                diagnostic_only=diagnostic is not None,main_viewport_preserved=True,
                replay_of=replay_id)


@router.post('/scene/camera/hidef/marine/capture',summary='Freeze and capture the marine scene with the oblique HiDef camera')
async def capture_marine(data: MarineRequest):
    return await run_capture(data=data)


@router.post('/scene/camera/hidef/marine/{capture_id}/replay',summary='Re-render a frozen marine capture and restore the live overview')
async def replay_marine(capture_id: str):
    return await run_capture(replay_id=capture_id)


@router.post('/scene/camera/hidef/marine/{capture_id}/tile-diagnostic',summary='Replay selected native tiles, including an identical repeat; no full-image certification')
async def diagnose_tiles(capture_id: str, data: TileDiagnosticRequest):
    return await run_capture(replay_id=capture_id,diagnostic=data.mode)
