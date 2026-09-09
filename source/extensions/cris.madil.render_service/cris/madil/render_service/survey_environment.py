"""Apply a fixed survey appearance through the existing MARLIN services."""
import json
from pathlib import Path

import omni.usd
from .api import router
from .environment import EnvironmentDataModel, create_environment
from .ocean import (OceanAnimationDataModel, OceanMaterialDataModel,
                    start_ocean_animation, apply_ocean_material)
from .underwater_api import UnderwaterCueDataModel, apply_underwater_cue

PRESET_PATH = Path(__file__).resolve().parents[3] / 'config' / 'survey_environment_v1.json'


@router.post('/scene/demonstration/environment', summary='Restore gentle demonstration water and lighting without rebuilding animals')
async def apply_demonstration_environment():
    import carb.settings

    if omni.usd.get_context().get_stage() is None:
        return {'ok': False, 'error': 'No live USD stage is open.'}
    steps = [
        ('ocean', start_ocean_animation, OceanAnimationDataModel(
            size=16000, resolution=128, wave_height=5, wave_length=650,
            choppiness=0.15, speed=0.4, target_fps=15)),
        ('material', apply_ocean_material, OceanMaterialDataModel(
            roughness=0.045, ior=1.333, transmission=1,
            base_weight=0.02, base_color=(0.02, 0.10, 0.13),
            transmission_color=(0.78, 0.92, 0.95), transmission_depth=100,
            scattering_color=(0.005, 0.02, 0.03), thin_walled=True)),
        ('environment', create_environment, EnvironmentDataModel(
            sky_intensity=500, sky_exposure=1, sky_color=(0.45, 0.65, 1.0),
            sun_intensity=5000, sun_rotation=(-35, 25, 0))),
        ('underwater_cue', apply_underwater_cue, UnderwaterCueDataModel(enabled=True)),
    ]
    results = {}
    for name, function, request in steps:
        results[name] = await function(request)
        if not results[name].get('ok'):
            return {'ok': False, 'failed_step': name, 'results': results}
    settings = carb.settings.get_settings()
    settings.set('/app/viewport/grid/enabled', False)
    return {'ok': True, 'grid_enabled': settings.get('/app/viewport/grid/enabled'),
            'results': results,
            'note': 'Demonstration appearance only; survey preset file and animal transforms unchanged. Static animals do not follow waves.'}


@router.post('/scene/survey/environment', summary='Apply fixed calm-water and overcast survey appearance')
async def apply_survey_environment():
    stage = omni.usd.get_context().get_stage()
    if stage is None:
        return {'ok': False, 'error': 'No live USD stage is open.'}
    preset = json.loads(PRESET_PATH.read_text())
    # Validate every request before modifying the scene.
    steps = [
        ('ocean', start_ocean_animation, OceanAnimationDataModel(**preset['ocean'])),
        ('material', apply_ocean_material, OceanMaterialDataModel(**preset['material'])),
        ('environment', create_environment, EnvironmentDataModel(**preset['environment'])),
        ('underwater_cue', apply_underwater_cue, UnderwaterCueDataModel(**preset['underwater_cue'])),
    ]
    results = {}
    for name, function, request in steps:
        try:
            results[name] = await function(request)
        except Exception as exc:
            results[name] = {'ok': False, 'error': str(exc)}
        if not results[name].get('ok'):
            return {'ok': False, 'failed_step': name, 'results': results}
    return {'ok': True, 'preset': preset, 'results': results,
            'note': 'Appearance preset applied; visual and camera calibration remain pending.'}
