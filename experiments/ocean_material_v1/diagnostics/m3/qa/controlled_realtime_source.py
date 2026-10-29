"""Bounded M3 medium experiments using the existing water/capture fixtures."""
import asyncio
import ctypes
from dataclasses import asdict
import gc
import json
from pathlib import Path
from typing import Literal

import carb.settings
import numpy as np
from pydantic import BaseModel

from .api import router
from . import calibration_capture, capture_state
from .hidef_marine import gpu_preflight, settings_record, restore_settings
from .water_diagnostics import DiagnosticCamera, build_fixture, hide_fixture_overlays
from .water_material import OmniSurfaceWaterParameters

ROOT = Path(__file__).resolve().parents[6] / 'experiments/ocean_material_v1/diagnostics/m3/captures_controlled'


class MediumRequest(BaseModel):
    depth_m: Literal[0.25, 0.75, 1.25] = 0.75
    condition: Literal['clear', 'absorption', 'scattering_low', 'scattering_high'] = 'clear'
    native_distance: Literal[1, 50, 100, 200] = 100
    meters_per_scene_unit: Literal[0.01, 1.0] = 0.01
    tone_map_probe: bool = False
    exposure_probe: bool = False

    class Config:
        extra = 'forbid'


def setup_medium_viewport(viewport, request):
    from pxr import UsdRender
    hide_fixture_overlays(viewport)
    # The default product requests LdrColor only. Request HDR explicitly on
    # this isolated product, without adding a renderer or another viewport.
    stage = viewport.stage
    product = UsdRender.Product(stage.GetPrimAtPath(viewport.render_product_path))
    if not product:
        raise RuntimeError('Isolated viewport has no valid render product')
    var = UsdRender.Var.Define(stage, '/Render/Vars/MarlinMediumHdr')
    var.CreateSourceNameAttr('HdrColor')
    var.CreateSourceTypeAttr('raw')
    var.CreateDataTypeAttr('color4h')
    product.GetOrderedVarsRel().AddTarget(var.GetPath())
    # Author effective USD controls. Legacy global carb values alone can be
    # superseded when Kit creates the camera/product and applies API defaults.
    camera = stage.GetPrimAtPath(str(viewport.camera_path))
    camera.ApplyAPI('OmniRtxCameraAutoExposureAPI_1')
    camera.ApplyAPI('OmniRtxCameraExposureAPI_1')
    controls = {'omni:rtx:autoExposure:enabled': False, 'exposure': 1.0 if request.exposure_probe else 0.0,
                'exposure:time': 1.0, 'exposure:fStop': 1.0,
                'exposure:iso': 100.0, 'exposure:responsivity': 1.0}
    for name, value in controls.items():
        attr = camera.GetAttribute(name)
        if not attr:
            raise RuntimeError('Missing registered camera control: ' + name)
        attr.Set(value)
    product_prim = product.GetPrim()
    for name, value in {'omni:rtx:fog:enabled': False,
                        'omni:rtx:post:tonemap:operator': 'raw' if request.tone_map_probe else 'acesApproximation'}.items():
        attr = product_prim.GetAttribute(name)
        if not attr:
            raise RuntimeError('Missing registered render-product control: ' + name)
        attr.Set(value)
    stage.GetRootLayer().Save()


async def capture_hdr(viewport, directory):
    """Copy SDK-owned float memory before its callback returns; retain native EXR."""
    from omni.kit.viewport.utility import capture_viewport_to_buffer, capture_viewport_to_file
    from omni.kit.widget.viewport.capture import Capture
    class Inventory(Capture):
        def capture(self, aov_map, frame_info, hydra_texture, result_handle):
            info = {key: {'keys': list(value), 'has_resource': value.get('texture', {}).get('rp_resource') is not None}
                    for key, value in aov_map.items()}
            (directory / 'aov_inventory.json').write_text(json.dumps(info, indent=2) + '\n')
            self._set_completed(info)
    inventory = viewport.schedule_capture(Inventory())
    available = await inventory.wait_for_result(completion_frames=2)
    if 'HdrColor' not in available:
        raise RuntimeError('Native HdrColor unavailable; retained aov_inventory.json')
    loop = asyncio.get_running_loop()
    done = loop.create_future()

    def completed(buffer, buffer_size, width, height, byte_format):
        info = {'aov': 'HdrColor', 'format': str(byte_format), 'buffer_bytes': int(buffer_size),
                'width': int(width), 'height': int(height), 'buffer_type': type(buffer).__name__}
        try:
            (directory / 'hdr_buffer.json').write_text(json.dumps(info, indent=2) + '\n')
            name = str(byte_format).upper()
            if not ('FLOAT' in name or 'SFLOAT' in name):
                raise RuntimeError('Native HDR output is not a declared float format: ' + name)
            # Only accept tightly packed four-channel float outputs of verified size.
            stride = int(buffer_size) // (int(width) * int(height))
            dtype = np.float32 if stride == 16 else np.float16 if stride == 8 else None
            if dtype is None or int(buffer_size) != int(width) * int(height) * stride:
                raise RuntimeError('Unsupported HDR buffer size/stride')
            if type(buffer).__name__ == 'PyCapsule':
                get_name = ctypes.pythonapi.PyCapsule_GetName
                get_name.restype, get_name.argtypes = ctypes.c_char_p, [ctypes.py_object]
                get_pointer = ctypes.pythonapi.PyCapsule_GetPointer
                get_pointer.restype, get_pointer.argtypes = ctypes.c_void_p, [ctypes.py_object, ctypes.c_char_p]
                pointer = get_pointer(buffer, get_name(buffer))
                if not pointer:
                    raise RuntimeError('Null HDR buffer')
                raw = ctypes.string_at(pointer, int(buffer_size))
            else:
                raw = bytes(memoryview(buffer))
            pixels = np.frombuffer(raw, dtype=dtype).reshape(int(height), int(width), 4).astype(np.float32)
            if not np.isfinite(pixels).all():
                raise RuntimeError('Nonfinite HDR samples')
            np.savez_compressed(directory / 'hdr.npz', rgba=pixels)
            info.update(dtype=str(pixels.dtype), minimum=float(pixels.min()), maximum=float(pixels.max()))
            (directory / 'hdr_buffer.json').write_text(json.dumps(info, indent=2) + '\n')
            loop.call_soon_threadsafe(done.set_result, info)
        except Exception as exc:
            loop.call_soon_threadsafe(done.set_exception, exc)

    stage = viewport.stage
    camera = stage.GetPrimAtPath(str(viewport.camera_path))
    product = stage.GetPrimAtPath(viewport.render_product_path)
    effective = {label: {a.GetName(): str(a.Get()) for a in prim.GetAttributes()
                         if not a.GetName().startswith('outputs:')}
                 for label, prim in [('camera', camera), ('render_product', product)]}
    (directory / 'effective_settings.json').write_text(json.dumps(effective, indent=2) + '\n')
    assert camera.GetAttribute('omni:rtx:autoExposure:enabled').Get() is False
    assert product.GetAttribute('omni:rtx:fog:enabled').Get() is False
    job = capture_viewport_to_buffer(viewport, completed, is_hdr=True)
    await job.wait_for_result(completion_frames=5)
    info = await asyncio.wait_for(done, timeout=15)
    job = capture_viewport_to_file(viewport, file_path=str(directory / 'hdr.exr'), is_hdr=True)
    await job.wait_for_result(completion_frames=5)
    return {'hdr_image': 'hdr.exr', 'hdr_array': 'hdr.npz', 'hdr_buffer': info,
            'hdr_domain': 'Native HdrColor float AOV; absolute radiometric calibration unverified'}


@router.post('/scene/ocean/material/diagnostic/medium/capture',
             summary='Capture one fixed depth/medium engineering condition with HDR')
async def capture_medium(data: MediumRequest):
    if calibration_capture._busy:
        return {'ok': False, 'error': 'Another camera capture is running', 'render_attempted': False}
    gc.collect()
    try:
        gpu = gpu_preflight(768)
    except Exception as exc:
        return {'ok': False, 'error': str(exc) or type(exc).__name__, 'render_attempted': False}
    calibration_capture._busy = True
    previous_paused = capture_state.paused
    before = settings_record()
    settings = carb.settings.get_settings()
    display_path = '/persistent/app/viewport/displayOptions'
    previous_display = settings.get(display_path)
    capture_state.paused = True
    scatter = {'clear': 0, 'absorption': 0, 'scattering_low': .02, 'scattering_high': .05}[data.condition]
    parameters = OmniSurfaceWaterParameters(ior=1.333, roughness=.001, base_weight=0,
        transmission_color=(1, 1, 1) if data.condition == 'clear' else (.6, .8, .9),
        transmission_depth=data.native_distance, scattering_color=(scatter,) * 3,
        scattering_anisotropy=0, thin_walled=False)
    try:
        settings.set('/rtx/fog/enabled', False)
        settings.set('/exts/cris.madil.render_service/underwaterCue/enabled', False)
        settings.set('/rtx/post/histogram/enabled', False)
        settings.set(display_path, 0)
        if data.tone_map_probe:
            settings.set('/rtx/post/tonemap/op', 0)
        config = DiagnosticCamera(meters_per_scene_unit=data.meters_per_scene_unit,
            image_width_px=512, image_height_px=384, focal_length_mm=35, pixel_pitch_um=40,
            height_above_target_m=3 + data.depth_m, target_plane_y_m=-data.depth_m,
            target_width_m=.18, target_height_m=.18, pitch_deg=0)
        active = settings_record()
        result = await asyncio.wait_for(calibration_capture._capture(config,
            stage_builder=lambda stage, c: build_fixture(stage, c, 'water', 'positive_depth',
                target_y=-data.depth_m, background_y=-1.8, medium_parameters=parameters),
            output_root=ROOT, viewport_setup=lambda v: setup_medium_viewport(v, data), rendered_frames=64,
            extra_capture=capture_hdr), timeout=90)
        result['metadata'].update(test_kind='ocean_material_medium_engineering',
            request=data.dict(), medium_parameters=asdict(parameters), renderer_settings=active,
            physical_water_path_m=data.depth_m, authored_water_path_units=data.depth_m / data.meters_per_scene_unit,
            camera_position_m=[0, 3, 0], completed_rendered_frame_wait=64,
            gpu_before=gpu, scientific_water_calibrated=False, target_visibility_modified=False,
            protocol='controlled_v2_effective_usd_settings')
        (Path(result['directory']) / 'metadata.json').write_text(json.dumps(result['metadata'], indent=2) + '\n')
        return result
    except Exception as exc:
        return {'ok': False, 'error': str(exc) or type(exc).__name__}
    finally:
        restore_settings(before)
        restore_settings({display_path: previous_display})
        capture_state.paused = previous_paused
        calibration_capture._busy = False
