"""Run the same native capture protocol in either private Kit SDK. No MARLIN imports."""
import asyncio
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import traceback

import carb.settings
import carb.tokens
import numpy as np
import omni.kit.app
import omni.usd
from pxr import Ar, Sdf, Usd, UsdGeom, UsdRender

ROOT=Path(os.environ['WATER_REPRO_ROOT'])
OUTPUT=Path(os.environ['WATER_REPRO_OUTPUT'])
APP=omni.kit.app.get_app()


def write(path, value):
    path.write_text(json.dumps(value,indent=2)+'\n')


def gpu():
    values=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,memory.used,memory.free,driver_version','--format=csv,noheader,nounits'],text=True).strip().split(',')
    return dict(name=values[0].strip(),total_mib=int(values[1]),used_mib=int(values[2]),free_mib=int(values[3]),driver=values[4].strip())


def controls(stage, viewport):
    product=stage.GetPrimAtPath(viewport.render_product_path)
    if not product:raise RuntimeError('Native viewport render product unavailable')
    camera=stage.GetPrimAtPath('/World/Camera')
    camera.ApplyAPI('OmniRtxCameraAutoExposureAPI_1')
    camera.ApplyAPI('OmniRtxCameraExposureAPI_1')
    values={'omni:rtx:rendermode':'PathTracing','omni:rtx:fog:enabled':False,
            'omni:rtx:pt:fireflyFilter:enabled':False,'omni:rtx:rtpt:fireflyFilter:enabled':False,
            'omni:rtx:pt:limits:maxBounces':16,'omni:rtx:pt:limits:maxGlossyBounces':16,
            'omni:rtx:pt:samplesPerPixel':512,'omni:rtx:pt:samplesPerIteration':1,
            'omni:rtx:pt:adaptiveSampling:enabled':False,'omni:rtx:pt:denoising:enabled':True,
            'omni:rtx:pt:showLights:enabled':True,
            'omni:rtx:pt:pixelFilter:filter':'triangle','omni:rtx:pt:pixelFilter:radius':1.0,
            'omni:rtx:post:tonemap:operator':'acesApproximation'}
    for name,value in values.items():
        attr=product.GetAttribute(name)
        if not attr:raise RuntimeError('Required registered product control unavailable: '+name)
        allowed=attr.GetMetadata('allowedTokens')
        if allowed and value not in allowed:raise RuntimeError('Required value not in registered tokens: '+name+' '+str(value))
        attr.Set(value)
    for name,value in {'omni:rtx:autoExposure:enabled':False,'exposure':0.,'exposure:time':1.,
                       'exposure:fStop':1.,'exposure:iso':100.,'exposure:responsivity':1.}.items():
        attr=camera.GetAttribute(name)
        if not attr:raise RuntimeError('Required registered camera control unavailable: '+name)
        attr.Set(value)
    var=UsdRender.Var.Define(stage,'/Render/Vars/MediumHdr')
    var.CreateSourceNameAttr('HdrColor');var.CreateSourceTypeAttr('raw');var.CreateDataTypeAttr('color4h')
    UsdRender.Product(product).GetOrderedVarsRel().AddTarget(var.GetPath())
    return values


async def hdr(viewport, folder):
    from omni.kit.viewport.utility import capture_viewport_to_buffer,capture_viewport_to_file
    loop=asyncio.get_running_loop();done=loop.create_future()
    def completed(buffer,size,width,height,byte_format):
        try:
            if 'SFLOAT' not in str(byte_format) and 'FLOAT' not in str(byte_format):
                raise ValueError('Not a floating-point native HDR format: '+str(byte_format))
            stride=int(size)//(int(width)*int(height))
            dtype=np.float16 if stride==8 else np.float32 if stride==16 else None
            if dtype is None or int(size)!=int(width)*int(height)*stride:raise ValueError('Unknown HDR stride')
            if type(buffer).__name__=='PyCapsule':
                get_name=ctypes.pythonapi.PyCapsule_GetName;get_name.restype=ctypes.c_char_p;get_name.argtypes=[ctypes.py_object]
                pointer=ctypes.pythonapi.PyCapsule_GetPointer;pointer.restype=ctypes.c_void_p;pointer.argtypes=[ctypes.py_object,ctypes.c_char_p]
                address=pointer(buffer,get_name(buffer))
                if not address:raise ValueError('Null native capture buffer')
                raw=ctypes.string_at(address,int(size))
            else:raw=bytes(memoryview(buffer))
            samples=np.frombuffer(raw,dtype=dtype).reshape(int(height),int(width),4).astype(np.float32)
            if samples.shape!=(384,512,4) or not np.isfinite(samples).all():raise ValueError('Invalid HDR dimensions or values')
            np.savez_compressed(folder/'hdr.npz',rgba=samples)
            record={'format':str(byte_format),'width':int(width),'height':int(height),'bytes':int(size),
                    'dtype':str(samples.dtype),'minimum':float(samples.min()),'maximum':float(samples.max()),
                    'centre_rgb':samples[184:200,248:264,:3].mean(axis=(0,1)).astype(float).tolist()}
            write(folder/'hdr_buffer.json',record);loop.call_soon_threadsafe(done.set_result,record)
        except Exception as exc:loop.call_soon_threadsafe(done.set_exception,exc)
    job=capture_viewport_to_buffer(viewport,completed,is_hdr=True)
    await job.wait_for_result(completion_frames=5)
    record=await asyncio.wait_for(done,20)
    job=capture_viewport_to_file(viewport,file_path=str(folder/'hdr.exr'),is_hdr=True)
    await job.wait_for_result(completion_frames=5)
    return record


async def capture(case, viewport):
    started=time.monotonic();preflight=gpu()
    if preflight['free_mib']<768:raise RuntimeError('768 MiB pre-capture GPU guard: '+str(preflight))
    folder=OUTPUT/case['name'];folder.mkdir(exist_ok=False)
    source=ROOT/case['file'];data=source.read_bytes()
    assert hashlib.sha256(data).hexdigest()==case['sha256']
    layer=Sdf.Layer.CreateAnonymous('standalone_medium.usda')
    if not layer.ImportFromString(data.decode()):raise RuntimeError('USDA import failed')
    stage=Usd.Stage.Open(layer)
    if case.get('dry_control'):stage.RemovePrim('/World/Water')
    ok,error=await omni.usd.get_context().attach_stage_async(stage)
    if not ok:raise RuntimeError(error)
    viewport.fill_frame=False;viewport.resolution=(512,384);viewport.camera_path='/World/Camera'
    for _ in range(30):await APP.next_update_async()
    viewport.fill_frame=False;viewport.resolution=(512,384)
    authored=controls(stage,viewport)
    for _ in range(5):await APP.next_update_async()
    await asyncio.wait_for(viewport.wait_for_rendered_frames(64),45)
    from omni.kit.viewport.utility import capture_viewport_to_file
    for filename in ('warmup.png','rgb.png'):
        job=capture_viewport_to_file(viewport,file_path=str(folder/filename))
        await job.wait_for_result(completion_frames=5)
    pixels=await hdr(viewport,folder)
    prims={'camera':stage.GetPrimAtPath('/World/Camera'),'render_product':stage.GetPrimAtPath(viewport.render_product_path),
           'shader':stage.GetPrimAtPath('/World/Looks/Water/Shader')}
    effective={label:{a.GetName():str(a.Get()) for a in prim.GetAttributes()} for label,prim in prims.items()}
    write(folder/'effective_settings.json',effective)
    shader=prims['shader'];asset=shader.GetAttribute('info:mdl:sourceAsset').Get()
    with Ar.ResolverContextBinder(stage.GetPathResolverContext()):resolved=str(Ar.GetResolver().Resolve(asset.path))
    matrix=UsdGeom.Camera(prims['camera']).GetCamera(Usd.TimeCode.Default()).transform
    product=UsdRender.Product(prims['render_product'])
    product_cameras=[str(path) for path in product.GetCameraRel().GetTargets()]
    if product_cameras!=['/World/Camera']:raise RuntimeError('Unexpected actual product camera: '+str(product_cameras))
    viewport_view=[[float(v) for v in row] for row in viewport.view]
    if not np.allclose(np.array(matrix.GetInverse()),viewport_view,atol=1e-6):raise RuntimeError('Viewport view differs from authored camera')
    frozen=stage.Flatten();frozen.Export(str(folder/'captured_scene.usdc'))
    record={'case':case,'gpu_before':preflight,'gpu_after':gpu(),'elapsed_seconds':time.monotonic()-started,
            'actual_resolution':list(viewport.resolution),'rendered_frame_wait':64,
            'configured_samples_per_pixel_limit':512,'actually_accumulated_samples_measured':False,
            'hdr':pixels,'camera_transform':[[float(v) for v in row] for row in matrix],
            'actual_viewport_view_matrix':viewport_view,'actual_product_cameras':product_cameras,
            'actual_product_resolution':list(product.GetResolutionAttr().Get()),
            'source_scene_sha256':case['sha256'],'captured_scene_sha256':hashlib.sha256((folder/'captured_scene.usdc').read_bytes()).hexdigest(),
            'authored_product_controls':authored,'resolved_mdl':resolved,
            'mdl_sha256':hashlib.sha256(Path(resolved).read_bytes()).hexdigest() if resolved and Path(resolved).is_file() else None,
            'native_hdr_domain':'HdrColor; absolute radiometric calibration unverified','marlin_imports':False}
    write(folder/'metadata.json',record)
    return record


async def main():
    window=None;records=[]
    try:
        tokens=carb.tokens.get_tokens_interface()
        token_values={name:tokens.resolve('${'+name+'}') for name in ('kit','app','cache','data','logs','omni_cache','omni_data','omni_global_cache','omni_global_data')}
        manager=APP.get_extension_manager()
        runtime={'build_version':APP.get_build_version(),'tokens':token_values,'gpu':gpu(),
                 'extensions':[{k:e.get(k) for k in ('id','name','version','path')} for e in manager.get_extensions() if e.get('enabled')],
                 'python_modules_before_capture':sorted(name for name in __import__('sys').modules if name.startswith('cris.'))}
        assert not runtime['python_modules_before_capture']
        write(OUTPUT/'runtime.json',runtime)
        from omni.kit.viewport.utility import get_active_viewport,create_viewport_window
        viewport=get_active_viewport()
        if viewport is None:
            window=create_viewport_window('Standalone medium',width=512,height=384,visible=False)
            viewport=window.viewport_api
        settings=carb.settings.get_settings()
        for guide in ('grid','axis','selection','boundingBox'):
            settings.set(f'/persistent/app/viewport/{viewport.id}/guide/{guide}/visible',False)
        settings.set('/app/viewport/outline/enabled',False)
        cases=json.loads((ROOT/'scene_manifest.json').read_text())['cases']
        cases=[case for case in cases if case['initial'] or os.environ['WATER_REPRO_SUITE']=='all']
        if os.environ['WATER_REPRO_SUITE']=='dry':
            cases=[dict(case,dry_control=True) for case in cases if case['condition']=='clear']
        for case in cases:
            # Empty private caches require one native pipeline compilation.
            # Keep the delivered-frame/ray budgets identical after warmup.
            case=dict(case,capture_timeout_seconds=240 if not records else 90)
            record=await asyncio.wait_for(capture(case,viewport),case['capture_timeout_seconds'])
            records.append(record);write(OUTPUT/'capture_records.json',records)
            print('CAPTURE',case['name'],record['hdr']['centre_rgb'],flush=True)
        result={'ok':True,'captures':len(records),'status':'rendered_requires_independent_optical_analysis'}
    except Exception as exc:
        result={'ok':False,'error':str(exc) or type(exc).__name__,'traceback':traceback.format_exc(),'successful_captures':len(records)}
    finally:
        if window is not None:window.destroy()
    write(OUTPUT/'result.json',result);print(json.dumps(result),flush=True)
    APP.post_quit(0 if result['ok'] else 1)


asyncio.ensure_future(main())
