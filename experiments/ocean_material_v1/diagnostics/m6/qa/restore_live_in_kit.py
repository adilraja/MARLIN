"""Restore the pre-M6 checkpoint and the recorded standard live controllers."""
import asyncio
import hashlib
import json
from pathlib import Path
import traceback

ROOT=Path(__file__).resolve().parents[1]


def write(name,value):
    (ROOT/'qa/live_restore'/name).write_text(json.dumps(value,indent=2)+'\n')


async def main():
    import omni.kit.app
    from cris.madil.render_service.scene_diagnostics import restore_checkpoint,checkpoint_scene
    from cris.madil.render_service.scene_setup import setup_marine_scene,MarineSceneSetupDataModel
    from cris.madil.render_service.hidef_marine import same_settings
    from omni.kit.viewport.utility import get_active_viewport
    try:
        for _ in range(90):
            await omni.kit.app.get_app().next_update_async()
        original=json.loads((ROOT/'qa/pre_work_checkpoint.json').read_text())
        assert hashlib.sha256((Path(original['directory'])/'scene.usdc').read_bytes()).hexdigest()==original['scene_sha256']
        restored=await restore_checkpoint(original['checkpoint_id'])
        write('checkpoint_restore.json',restored)
        assert restored['ok']
        await asyncio.wait_for(get_active_viewport().wait_for_rendered_frames(3),timeout=90)
        setup=await setup_marine_scene(MarineSceneSetupDataModel(start_swimming=False))
        write('setup.json',setup)
        assert setup['ok']
        after=await checkpoint_scene()
        write('checkpoint_after.json',after)
        checks={key:same_settings(original[key],after[key]) for key in ('camera','resolution','fill_frame','renderer_settings','display_options')}
        write('checks.json',checks)
        assert all(checks.values()),checks
        write('done.json',dict(ok=True,checkpoint_id=after['checkpoint_id'],phase='Reconstructed; not preserved across the process lifecycle'))
    except BaseException as exc:
        write('failure.json',dict(error=str(exc) or type(exc).__name__,traceback=traceback.format_exc()))


asyncio.ensure_future(main())
