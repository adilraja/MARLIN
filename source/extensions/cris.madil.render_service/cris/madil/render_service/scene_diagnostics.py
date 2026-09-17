"""Scene inspection and bounded local checkpoints for safe Kit restarts."""
import json
import re
import tempfile
from pathlib import Path
import omni.usd
from pxr import Usd, UsdGeom
from .api import router
from .camera import _active_viewport

CHECKPOINT_ROOT = Path(__file__).resolve().parents[6]/'artifacts/scene_checkpoints'


@router.get('/debug/capture-capabilities', summary='Inspect installed capture SDK availability without loading it')
async def capture_capabilities():
    import omni.kit.app
    manager=omni.kit.app.get_app().get_extension_manager()
    names={'omni.kit.capture.viewport','omni.graph','omni.graph.nodes','omni.graph.examples.cpp'}
    extensions=[{key:entry.get(key) for key in ('id','name','version','enabled')}
                for entry in manager.get_extensions() if entry.get('name') in names]
    return {'ok':True,'extensions':extensions}


@router.post('/debug/capture-capabilities/enable', summary='Enable the fixed NVIDIA capture SDK dependencies')
async def enable_capture_sdk():
    import omni.kit.app
    from . import calibration_capture
    if calibration_capture._busy:
        return {'ok':False,'error':'A camera capture is running'}
    manager=omni.kit.app.get_app().get_extension_manager()
    # Fixed allowlist, not a general extension installer or code execution API.
    names=('omni.kit.capture.viewport','omni.graph','omni.graph.nodes','omni.graph.examples.cpp')
    results=[]
    for name in names:
        ok=manager.set_extension_enabled_immediate(name,True)
        results.append({'name':name,'enabled':bool(ok)})
        if not ok:
            break
    return {'ok':len(results)==len(names) and all(r['enabled'] for r in results),
            'results':results,'capabilities':await capture_capabilities()}


@router.post('/debug/scene/checkpoint', summary='Save a recoverable frozen scene without allocating render buffers')
async def checkpoint_scene():
    import carb.settings
    import omni.timeline
    from .hidef_marine import freeze_stage, settings_record, digest
    from . import calibration_capture
    if calibration_capture._busy:
        return {'ok':False,'error':'A camera capture is running'}
    stage=omni.usd.get_context().get_stage()
    viewport=_active_viewport()
    if stage is None or viewport is None:
        return {'ok':False,'error':'An active scene and viewport are required'}
    # No await: controllers cannot advance between sampling and serialization.
    seconds=omni.timeline.get_timeline_interface().get_current_time()
    frozen,count=freeze_stage(stage,Usd.TimeCode(seconds*stage.GetTimeCodesPerSecond()))
    if frozen.GetPrimAtPath('/Render'):
        frozen.RemovePrim('/Render')
    CHECKPOINT_ROOT.mkdir(parents=True,exist_ok=True)
    directory=Path(tempfile.mkdtemp(prefix='checkpoint_',dir=CHECKPOINT_ROOT))
    frozen.GetRootLayer().Export(str(directory/'scene.usdc'))
    record=dict(schema_version=1,scene_sha256=digest(directory/'scene.usdc'),
        camera=str(viewport.camera_path),resolution=list(viewport.resolution),
        fill_frame=viewport.fill_frame,renderer_settings=settings_record(),
        display_options=carb.settings.get_settings().get('/persistent/app/viewport/displayOptions'),
        timeline_seconds=seconds,frozen_sampled_attributes=count,
        limitations='Frozen visual state with external asset dependencies; controller/animation phase is not serialized.')
    (directory/'metadata.json').write_text(json.dumps(record,indent=2)+'\n')
    return {'ok':True,'checkpoint_id':directory.name,'directory':str(directory),**record}


@router.post('/debug/scene/checkpoint/{checkpoint_id}/restore', summary='Restore a MARLIN checkpoint; does not start animation controllers')
async def restore_checkpoint(checkpoint_id: str):
    import carb.settings
    from .hidef_marine import open_snapshot, restore_settings, digest
    from . import calibration_capture, capture_state
    if calibration_capture._busy:
        return {'ok':False,'error':'A camera capture is running'}
    if not re.fullmatch(r'checkpoint_[a-z0-9_]+',checkpoint_id):
        return {'ok':False,'error':'Use a checkpoint_id returned by MARLIN'}
    directory=CHECKPOINT_ROOT/checkpoint_id
    record=json.loads((directory/'metadata.json').read_text())
    if digest(directory/'scene.usdc')!=record['scene_sha256']:
        return {'ok':False,'error':'Checkpoint hash mismatch'}
    stage=open_snapshot(directory/'scene.usdc')
    viewport=_active_viewport()
    if viewport is None or not stage.GetPrimAtPath(record['camera']):
        return {'ok':False,'error':'Missing viewport or saved camera'}
    calibration_capture._busy=True
    was_paused=capture_state.paused
    capture_state.paused=True
    try:
        ok,error=await omni.usd.get_context().attach_stage_async(stage)
        if not ok:
            raise RuntimeError(error)
        restore_settings(record['renderer_settings'])
        viewport.camera_path=record['camera']
        viewport.resolution=tuple(record['resolution'])
        viewport.fill_frame=record['fill_frame']
        restore_settings({'/persistent/app/viewport/displayOptions':record['display_options']})
        return {'ok':True,'checkpoint_id':checkpoint_id,'camera':record['camera'],
                'controllers_started':False}
    finally:
        capture_state.paused=was_paused
        calibration_capture._busy=False


@router.get('/debug/scene/inspection', summary='Inspect live layers, ocean and animal transforms')
async def inspect_scene():
    stage = omni.usd.get_context().get_stage()
    if stage is None:
        return {'ok': False, 'error': 'No stage'}
    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ['default', 'render', 'proxy'])
    paths = ['/World', '/World/Ocean', '/World/Environment', '/Environment']
    animals = stage.GetPrimAtPath('/World/Cetaceans')
    if animals:
        paths.extend(str(p.GetPath()) for p in animals.GetChildren())
    records = []
    for path in paths:
        prim = stage.GetPrimAtPath(path)
        if not prim:
            continue
        record = {'path': path, 'type': prim.GetTypeName(),
                  'prim_stack': [str(s.layer.identifier) for s in prim.GetPrimStack()]}
        if prim.IsA(UsdGeom.Imageable):
            record['visibility'] = str(UsdGeom.Imageable(prim).ComputeVisibility())
            bounds = cache.ComputeWorldBound(prim).ComputeAlignedRange()
            if not bounds.IsEmpty():
                record['bounds_min'] = list(bounds.GetMin())
                record['bounds_max'] = list(bounds.GetMax())
        if prim.IsA(UsdGeom.Xformable):
            record['xform_ops'] = [{'name': op.GetOpName(), 'value': str(op.Get()),
                'layers': [str(s.layer.identifier) for s in op.GetAttr().GetPropertyStack()]}
                for op in UsdGeom.Xformable(prim).GetOrderedXformOps()]
        records.append(record)
    viewport = _active_viewport()
    return {'ok': True, 'root_layer': stage.GetRootLayer().identifier,
            'edit_layer': stage.GetEditTarget().GetLayer().identifier,
            'layers': [layer.identifier for layer in stage.GetLayerStack()],
            'camera': str(viewport.camera_path) if viewport else None,
            'prims': records}
