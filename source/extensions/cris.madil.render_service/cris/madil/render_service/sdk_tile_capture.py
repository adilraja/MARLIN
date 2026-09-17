"""Bounded SDK experiment; SDK completion is not a measured RTX sample count."""
import asyncio
import shutil
import time
import json
from pathlib import Path


def create_tile_product(stage, root, camera_path, resolution):
    from pxr import UsdRender, Gf
    if stage.GetPrimAtPath(root):
        raise RuntimeError('Temporary capture path already exists')
    stage.DefinePrim(root, 'Scope')
    product = UsdRender.Product.Define(stage, root+'/Product')
    product.CreateResolutionAttr().Set(Gf.Vec2i(*resolution))
    product.CreatePixelAspectRatioAttr().Set(1)
    product.CreateCameraRel().SetTargets([camera_path])
    # Match the AOV prim name and sourceName: SDK output discovery uses the
    # latter while the PNG writer uses the former.
    var = UsdRender.Var.Define(stage, root+'/LdrColor')
    var.CreateSourceNameAttr().Set('LdrColor')
    var.CreateSourceTypeAttr().Set('raw')
    var.CreateDataTypeAttr().Set('color3f')
    product.CreateOrderedVarsRel().SetTargets([var.GetPath()])
    return product


async def capture_sdk_tile(stage, viewport, resolution, destination, samples=1024):
    if samples not in (16,1024):
        raise ValueError('Only fixed diagnostic sample budgets are supported')
    import omni.kit.app
    from omni.kit.capture.viewport import CaptureExtension, CaptureOptions, CaptureRenderPreset, CaptureStatus
    from .capture_projection import record_product_projection

    capture = CaptureExtension.get_instance()
    if capture is None or capture.progress.capture_status not in (CaptureStatus.NONE, CaptureStatus.DONE):
        raise RuntimeError('NVIDIA capture SDK is unavailable or already capturing')
    root = '/Render/MarlinTileDiagnostic'
    if stage.GetPrimAtPath(root):
        raise RuntimeError('Temporary capture path already exists')
    old_product = viewport.render_product_path
    old_options = capture.options
    old_window = capture.show_default_progress_window
    projection = None
    started = False
    started_at = time.monotonic()
    trace=[]
    def trace_state(phase):
        prim=stage.GetPrimAtPath(root+'/Product')
        product_size=prim.GetAttribute('resolution').Get() if prim else None
        trace.append({'phase':phase,'seconds':time.monotonic()-started_at,
            'viewport_resolution':list(viewport.resolution),'fill_frame':viewport.fill_frame,
            'product_resolution':list(product_size) if product_size is not None else None,
            'viewport_render_mode':viewport.render_mode,
            'sdk_renderer_switch':getattr(capture,'_switch_renderer',None),
            'product':str(viewport.render_product_path),
            'sdk_status':str(capture.progress.capture_status)})
    import carb.settings
    settings=carb.settings.get_settings()
    fill_setting='/persistent/app/viewport/%s/fillViewport'%viewport.id
    saved_fill={fill_setting:settings.get(fill_setting)}
    try:
        # The menu tracks this preference separately from ViewportAPI.fill_frame.
        # SDK changes it on start if left true, reapplying the menu's 1280x720
        # preset on the next update. Settle the menu before setting tile size.
        settings.set_bool(fill_setting,False)
        await asyncio.wait_for(viewport.wait_for_rendered_frames(3),timeout=30)
        product = create_tile_product(stage,root,viewport.camera_path,resolution)
        viewport.fill_frame = False
        viewport.render_product_path = str(product.GetPath())
        viewport.resolution = tuple(resolution)
        # Binding a new Hydra texture initially applies its default dimensions.
        # Settle that one-time setup before starting the SDK sample lifecycle.
        from .native_tiles import wait_for_fixed_resolution
        await asyncio.wait_for(wait_for_fixed_resolution(viewport,resolution,3),timeout=30)
        trace_state('before_sdk_start')
        options = CaptureOptions(camera=str(viewport.camera_path),
            res_width=resolution[0], res_height=resolution[1],
            render_product=str(product.GetPath()),
            render_preset=CaptureRenderPreset.PATH_TRACE,
            path_trace_spp=samples, spp_per_iteration=8,
            output_folder=str(destination.parent), file_name=destination.stem+'_sdk',
            file_name_num_pattern='', file_type='.png')
        capture.options = options
        capture.show_default_progress_window = False
        if not capture.start():
            raise RuntimeError('NVIDIA capture SDK refused to start')
        started = True
        trace_state('after_sdk_start')
        async def wait_done():
            nonlocal projection
            while not capture.done:
                await omni.kit.app.get_app().next_update_async()
                if len(trace)<100:
                    trace_state('sdk_update')
                # Check the actual bound product throughout capture, not just
                # the authored product left behind after SDK restoration.
                if str(viewport.render_product_path) != str(product.GetPath()):
                    raise RuntimeError('SDK switched away from the owned render product')
                projection = record_product_projection(stage,str(product.GetPath()),options.camera,resolution,viewport.time)
                projection['actual_viewport_resolution']=list(viewport.resolution)
                if projection['render_product']['resolution'] != list(resolution):
                    raise RuntimeError('SDK tile dimensions changed during capture')
        await asyncio.wait_for(wait_done(), timeout=120)
        outputs = [Path(p) for p in capture.get_outputs()]
        if len(outputs) != 1 or not outputs[0].is_file() or projection is None:
            raise RuntimeError('SDK did not produce exactly one validated colour image')
        shutil.copyfile(outputs[0], destination)
        projection['sample_completion'] = {
            'requested_spp':samples, 'spp_per_iteration':8, 'sdk_done':True,
            'actual_gpu_samples_verified':False,
            'basis':'SDK synchronized capture lifecycle; SDK increments an iteration counter, not hardware sample telemetry',
            'elapsed_seconds':time.monotonic()-started_at}
        return projection
    except BaseException as exc:
        destination.with_suffix('.failure.json').write_text(json.dumps({
            'status':'failed_not_certified','error':str(exc) or type(exc).__name__,
            'requested_resolution':list(resolution),
            'observed_resolution':list(viewport.resolution),
            'requested_spp':samples,'actual_gpu_samples_verified':False,
            'elapsed_seconds':time.monotonic()-started_at},indent=2)+'\n')
        raise
    finally:
        destination.with_suffix('.trace.json').write_text(json.dumps(trace,indent=2)+'\n')
        try:
            if started and not capture.done:
                capture.cancel()
                async def wait_cancel():
                    while not capture.done:
                        await omni.kit.app.get_app().next_update_async()
                await asyncio.wait_for(wait_cancel(), timeout=15)
        finally:
            viewport.render_product_path = old_product
            capture.options = old_options
            capture.show_default_progress_window = old_window
            # SDK may author render settings into the session layer. Remove
            # only our newly owned subtree from every local stage layer.
            from pxr import Usd
            for layer in stage.GetLayerStack():
                if layer.GetPrimAtPath(root):
                    with Usd.EditContext(stage,layer):
                        stage.RemovePrim(root)
            from .hidef_marine import restore_settings
            restore_settings(saved_fill)
            if stage.GetPrimAtPath(root):
                raise RuntimeError('SDK temporary product cleanup failed')
