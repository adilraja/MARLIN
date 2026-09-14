"""Sony preview shares the guarded marine snapshot/replay implementation."""
from typing import Literal
from pydantic import BaseModel, Field
from .api import router
from .hidef_marine import run_capture


class SonyRequest(BaseModel):
    projection_probe: bool = False
    downsample: Literal[8] = 8
    target_x_m: float = Field(default=0, ge=-1000, le=1000)
    target_z_m: float = Field(default=0, ge=-1000, le=1000)

    class Config:
        extra = 'forbid'


@router.post('/scene/camera/sony/marine/capture', summary='Capture a provisional Sony nadir preview without changing the live environment')
async def capture_sony(data: SonyRequest):
    return await run_capture(data=data, camera_model='sony')


@router.post('/scene/camera/sony/marine/{capture_id}/replay', summary='Replay a frozen Sony preview and restore the live scene')
async def replay_sony(capture_id: str):
    return await run_capture(replay_id=capture_id, camera_model='sony')
