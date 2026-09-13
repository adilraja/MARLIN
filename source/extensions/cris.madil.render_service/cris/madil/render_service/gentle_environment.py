"""Reversible overcast appearance experiment; no animal/camera mutations."""
import asyncio
import math
import carb.settings
import omni.usd
from pxr import Sdf, UsdGeom
from .api import router
from . import ocean
from .environment import EnvironmentDataModel, create_environment
from .underwater_api import UnderwaterCueDataModel, apply_underwater_cue
from .underwater_cue import UNDERWATER_FOG_SETTING_PATHS, UNDERWATER_CUE_REQUESTED_SETTING
from .water_material import RTX_WATER_SETTINGS

_saved = None
_lock = asyncio.Lock()
PATHS = ('/World/Ocean', '/World/Looks/OceanWater', '/World/Environment')
PRESET = {
    'id': 'gentle_overcast_v1',
    'wave_height': 20.0, 'wave_length': 900.0, 'choppiness': .12, 'speed': .3,
    'sky_intensity': 500.0, 'sky_color': (1.0, 1.0, 1.0), 'sun_intensity': 0.0,
    'roughness': .06, 'base_weight': .08,
    'base_color': (.02, .10, .13), 'transmission_color': (.25, .65, .75),
}


def _snapshot(stage):
    state = ocean._ocean_animation_state
    if state is None:
        raise ValueError('Start the marine ocean before applying this preset.')
    if not math.isclose(UsdGeom.GetStageMetersPerUnit(stage), .01):
        raise ValueError('This appearance preset requires the existing centimetre stage.')
    request = ocean.OceanAnimationDataModel(
        name=str(state['ocean_path']).split('/')[-1], size=state['size'],
        resolution=state['resolution'], position=state['position'],
        wave_height=state['waves'][0]['amplitude']/.52,
        wave_length=math.tau/state['waves'][0]['k'],
        choppiness=state['choppiness'], speed=state['speed'], target_fps=state['target_fps'])
    layer = Sdf.Layer.CreateAnonymous('gentle_environment_restore')
    flat = stage.Flatten()
    for path in PATHS:
        if flat.GetPrimAtPath(path):
            Sdf.CreatePrimInLayer(layer, Sdf.Path(path).GetParentPath())
            Sdf.CopySpec(flat, path, layer, path)
    settings = carb.settings.get_settings()
    keys = tuple(RTX_WATER_SETTINGS) + UNDERWATER_FOG_SETTING_PATHS + (UNDERWATER_CUE_REQUESTED_SETTING,)
    default = stage.GetPrimAtPath('/Environment')
    return {'stage': stage, 'layer': layer, 'request': request,
            'settings': {key: settings.get(key) for key in keys},
            'default_visibility': UsdGeom.Imageable(default).GetVisibilityAttr().Get() if default else None}


async def _restore(saved):
    stage = saved['stage']
    await ocean.start_ocean_animation(saved['request'])
    target = stage.GetEditTarget().GetLayer()
    for path in PATHS:
        stage.RemovePrim(path)
        if saved['layer'].GetPrimAtPath(path):
            Sdf.CreatePrimInLayer(target, Sdf.Path(path).GetParentPath())
            Sdf.CopySpec(saved['layer'], path, target, path)
    default = stage.GetPrimAtPath('/Environment')
    if default:
        attr = UsdGeom.Imageable(default).GetVisibilityAttr()
        if saved['default_visibility'] is None:
            attr.Clear()
        else:
            attr.Set(saved['default_visibility'])
    settings = carb.settings.get_settings()
    for key, value in saved['settings'].items():
        settings.destroy_item(key) if value is None else settings.set(key, value)


@router.post('/scene/environment/gentle-overcast', summary='Apply reversible gentle waves and diffuse overcast sky')
async def apply_gentle_overcast():
    global _saved
    async with _lock:
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return {'ok': False, 'error': 'No stage; create the marine scene first.'}
        if _saved is not None and _saved['stage'] != stage:
            return {'ok': False, 'error': 'Stage changed; reload extension before starting another environment review.'}
        try:
            if _saved is None:
                _saved = _snapshot(stage)
            previous = _saved['request']
            result = await ocean.start_ocean_animation(ocean.OceanAnimationDataModel(
                name=previous.name, size=previous.size, resolution=128, position=previous.position,
                wave_height=PRESET['wave_height'], wave_length=PRESET['wave_length'],
                choppiness=PRESET['choppiness'], speed=PRESET['speed'], target_fps=15))
            if not result.get('ok'):
                raise ValueError(result)
            result = await ocean.apply_ocean_material(ocean.OceanMaterialDataModel(
                roughness=PRESET['roughness'], base_weight=PRESET['base_weight'],
                base_color=PRESET['base_color'], transmission_color=PRESET['transmission_color'],
                transmission=1, transmission_depth=100))
            if not result.get('ok'):
                raise ValueError(result)
            result = await create_environment(EnvironmentDataModel(
                sky_intensity=PRESET['sky_intensity'], sky_exposure=0,
                sky_color=PRESET['sky_color'], sun_intensity=0))
            if not result.get('ok'):
                raise ValueError(result)
            default = stage.GetPrimAtPath('/Environment')
            if default:
                UsdGeom.Imageable(default).MakeInvisible()
            await apply_underwater_cue(UnderwaterCueDataModel(enabled=False))
            return {'ok': True, 'preset': PRESET, 'restore_available': True,
                    'note': 'One blue-green water material. Fixed wave phases restart at zero; wall-clock updates are not frame-deterministic. No animal or camera controls changed.'}
        except Exception as exc:
            if _saved is not None:
                await _restore(_saved)
                _saved = None
            return {'ok': False, 'error': str(exc)}


@router.post('/scene/environment/gentle-overcast/restore', summary='Restore water and lighting saved before the overcast experiment')
async def restore_gentle_overcast():
    global _saved
    async with _lock:
        if _saved is None:
            return {'ok': False, 'error': 'No saved environment in this Kit session.'}
        if omni.usd.get_context().get_stage() != _saved['stage']:
            return {'ok': False, 'error': 'Stage changed; refusing to restore into another scene.'}
        await _restore(_saved)
        _saved = None
        return {'ok': True, 'restored': True, 'note': 'Original wave parameters restored with phase restart; animal motion is not rewound.'}
