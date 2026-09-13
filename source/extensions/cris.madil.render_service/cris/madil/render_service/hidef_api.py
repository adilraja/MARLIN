"""Bounded HiDef replica capture using the existing isolated Kit workflow."""
import asyncio
from typing import Literal
from pydantic import BaseModel
from .api import router
from . import calibration_capture
from .hidef_camera import configuration, build_hidef_stage


class HiDefRequest(BaseModel):
    roll_deg: Literal[7.77,23.17,7.7675,23.1748] = 7.77
    downsample: Literal[1,2,4] = 4
    aperture_basis: Literal['paper_effective','manufacturer_roi_hypothesis'] = 'paper_effective'
    allow_full_resolution: bool = False


@router.post('/scene/camera/hidef/capture', summary='Render isolated oblique HiDef metric targets, not Sony or nadir')
async def capture_hidef(data: HiDefRequest):
    if data.downsample == 1 and not data.allow_full_resolution:
        return {'ok': False, 'error': 'Full 6576x2192 capture requires allow_full_resolution=true; check GPU memory first.'}
    if calibration_capture._busy:
        return {'ok': False, 'error': 'Another calibration capture is running'}
    calibration_capture._busy = True
    try:
        config = configuration(data.roll_deg, data.downsample, data.aperture_basis)
        return await asyncio.wait_for(calibration_capture._capture(config, build_hidef_stage), timeout=120)
    except Exception as exc:
        return {'ok': False, 'error': str(exc) or type(exc).__name__}
    finally:
        calibration_capture._busy = False
