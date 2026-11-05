"""M4 controlled restart: exact frozen stage, then recorded public controllers.

No marine setup or animal respawn. Ocean/controller phases are reconstructed;
the checkpoint API does not serialize their previous Python accumulators.
"""
import asyncio
import hashlib
import json
from pathlib import Path
import traceback

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'live_restore_gui_final'


def write(name, data):
    path = OUT / name
    assert not path.exists(), path
    path.write_text(json.dumps(data, indent=2)+'\n')


async def restore():
    import omni.kit.app
    from cris.madil.render_service.scene_diagnostics import restore_checkpoint, checkpoint_scene
    from cris.madil.render_service.ocean import start_ocean_animation, OceanAnimationDataModel
    from cris.madil.render_service.camera import start_chase_camera, ChaseCameraDataModel
    from cris.madil.render_service.hidef_marine import same_settings
    try:
        for _ in range(90):
            await omni.kit.app.get_app().next_update_async()
        from omni.kit.viewport.utility import get_active_viewport,create_viewport_window
        global _m4_offscreen_window
        if get_active_viewport() is None:
            _m4_offscreen_window=create_viewport_window('MARLIN M4 offscreen',width=640,height=480)
            for _ in range(10):await omni.kit.app.get_app().next_update_async()
        saved = json.loads((ROOT/'live_before/checkpoint.json').read_text())
        path = Path(saved['directory']) / 'scene.usdc'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == saved['scene_sha256']
        result = await restore_checkpoint(saved['checkpoint_id'])
        write('checkpoint_restore.json', result)
        assert result['ok'], result
        before = await checkpoint_scene()
        write('frozen_restored_checkpoint.json', before)
        ocean = json.loads((ROOT/'live_before/ocean.json').read_text())
        if ocean['running']:
            config = {k:ocean[k] for k in ('size','resolution','speed','choppiness','target_fps')}
            config.update(name='Ocean',wave_height=40.,wave_length=650.,position=(0,0,0))
            result = await start_ocean_animation(OceanAnimationDataModel(**config))
            write('ocean_restart.json', result)
            assert result['ok'], result
        chase = json.loads((ROOT/'live_before/chase.json').read_text())
        if chase['running']:
            fields = set(ChaseCameraDataModel.model_fields)
            config = {k:v for k,v in chase.items() if k in fields}
            config['activate_viewport'] = chase['viewport_active']
            result = await start_chase_camera(ChaseCameraDataModel(**config))
            write('chase_restart.json',result)
            assert result['ok'],result
        after = await checkpoint_scene()
        write('checkpoint_after.json', after)
        checks = {k:same_settings(saved[k],after[k]) for k in
                  ('camera','resolution','fill_frame','renderer_settings','display_options')}
        write('done.json',dict(ok=all(checks.values()),checks=checks,
              phase='Reconstructed ocean/chase; not an exact previous accumulator resume',
              new_animals_spawned=False,new_animation_bound=False))
    except BaseException as error:
        write('failure.json',dict(error=str(error),traceback=traceback.format_exc()))


asyncio.ensure_future(restore())
