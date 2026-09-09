"""Bounded calibration capture in a separate USD context and viewport."""
import asyncio
import hashlib
import json
from pathlib import Path
import tempfile
import uuid

import omni.kit.app
import omni.usd
from pydantic import BaseModel, Field

from .api import router
from .calibration_geometry import CalibrationConfig, build_stage

_busy = False
OUTPUT_ROOT = Path(__file__).resolve().parents[6] / 'artifacts/calibration'


class CalibrationRequest(BaseModel):
    meters_per_scene_unit: float = Field(gt=0)
    image_width_px: int = Field(ge=64, le=2048)
    image_height_px: int = Field(ge=64, le=2048)
    focal_length_mm: float = Field(gt=0)
    pixel_pitch_um: float = Field(gt=0)
    height_above_target_m: float = Field(gt=0)
    target_width_m: float = Field(gt=0)
    target_height_m: float = Field(gt=0)
    target_plane_y_m: float
    pitch_deg: float = Field(default=0, ge=0, le=60)
    roll_deg: float = Field(default=0, ge=-45, le=45)


async def _capture(config):
    from omni.kit.viewport.utility import create_viewport_window, capture_viewport_to_file
    from pxr import Usd
    context_name = 'marlin_calibration_' + uuid.uuid4().hex
    context = None
    window = None
    main_stage = omni.usd.get_context().get_stage()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='oblique_' if config.pitch_deg or config.roll_deg else 'nadir_', dir=str(OUTPUT_ROOT)))
    try:
        omni.usd.create_context(context_name)
        context = omni.usd.get_context(context_name)
        stage = Usd.Stage.CreateNew(str(directory / 'scene.usda'))
        camera = build_stage(stage, config)
        stage.GetRootLayer().Save()
        ok, error = await context.attach_stage_async(stage)
        if not ok:
            raise RuntimeError(error)
        window = create_viewport_window('MARLIN calibration test', usd_context_name=context_name,
                                        width=640, height=480, camera_path=camera.GetPath())
        if window is None:
            raise RuntimeError('Could not create isolated viewport')
        viewport = window.viewport_api
        viewport.fill_frame = False
        viewport.resolution = (config.image_width_px, config.image_height_px)
        viewport.camera_path = str(camera.GetPath())
        for _ in range(60):
            await omni.kit.app.get_app().next_update_async()
        # Initial window layout can overwrite the requested render size.
        # Reapply after layout, then fail rather than mislabel a scaled image.
        viewport.fill_frame = False
        viewport.resolution = (config.image_width_px, config.image_height_px)
        for _ in range(30):
            await omni.kit.app.get_app().next_update_async()
        if tuple(viewport.resolution) != (config.image_width_px, config.image_height_px):
            raise RuntimeError('Viewport did not retain the explicit capture resolution')
        # Warm-up capture avoids delivering the preceding frame or uncompiled material.
        for filename in ('warmup.png', 'rgb.png'):
            capture = capture_viewport_to_file(viewport, file_path=str(directory / filename))
            await capture.wait_for_result(completion_frames=5)
        if omni.usd.get_context().get_stage() != main_stage:
            raise RuntimeError('Default context stage changed during capture')
        metadata = config.metadata()
        metadata.update(actual_viewport_resolution=list(viewport.resolution),
                        actual_view_matrix=[list(row) for row in viewport.view],
                        actual_projection_matrix=[list(row) for row in viewport.projection],
                        usd_context=context_name, default_stage_retained=True,
                        scene_sha256=hashlib.sha256((directory/'scene.usda').read_bytes()).hexdigest(),
                        rendered_image='rgb.png', scene_file='scene.usda',
                        validation_status='rendered_not_yet_measured')
        (directory/'metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
        return {'ok': True, 'directory': str(directory), 'metadata': metadata}
    finally:
        try:
            if window is not None:
                window.destroy()
        finally:
            if context is not None:
                try:
                    await context.close_stage_async()
                finally:
                    omni.usd.destroy_context(context_name)


@router.post('/scene/survey/calibration/capture', summary='Capture an isolated ideal-pinhole metric target')
async def capture_calibration(data: CalibrationRequest):
    global _busy
    if _busy:
        return {'ok': False, 'error': 'A calibration capture is already running'}
    _busy = True
    try:
        config = CalibrationConfig(**data.dict())
        return await asyncio.wait_for(_capture(config), timeout=60)
    except Exception as exc:
        return {'ok': False, 'error': str(exc) or type(exc).__name__}
    finally:
        _busy = False
