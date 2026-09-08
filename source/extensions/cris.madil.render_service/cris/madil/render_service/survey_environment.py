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
