"""Reopen saved M5 files under registered NVIDIA schemas, then leave GUI idle."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import traceback

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('_m5_native_audit',ROOT/'native_m5.py')
native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)


async def main():
    report=dict(passed=False,pid=os.getpid(),snapshots=[],scope='Native reopening of complete ocean/lighting state, including NVIDIA schema fallback values')
    try:
        import omni.kit.app
        from pxr import Usd
        from cris.madil.render_service.scene_diagnostics import restore_checkpoint,checkpoint_scene
        app=omni.kit.app.get_app()
        for _ in range(90):await app.next_update_async()
        baseline=json.loads((ROOT/'live_before/checkpoint.json').read_text())
        restored=await restore_checkpoint(baseline['checkpoint_id'])
        assert restored['ok'],restored
        report['runtime']=app.get_build_version()
        for run_id in ['primary02','fresh01']:
            run=json.loads((ROOT/run_id/'result.json').read_text());assert run['status']=='passed'
            for capture in run['captures']:
                if not capture['snapshot']:continue
                folder=Path(run['media_directory'])/capture['label']
                state=json.loads((folder/'state.json').read_text())
                assert native.digest(folder/'scene.usdc')==state['scene_sha256']
                stage=Usd.Stage.Open(str(folder/'scene.usdc'))
                actual=native.environment(stage)
                assert actual==state['environment'],(run_id,capture['label'],'Environment changed')
                assert native.fingerprint(actual)==state['environment_sha256']
                report['snapshots'].append(dict(run=run_id,label=capture['label'],scene_sha256=state['scene_sha256'],
                    environment_sha256=state['environment_sha256'],ocean_and_lighting_exact=True))
                del stage
                await app.next_update_async()
        assert len(report['snapshots'])==35
        report['final_checkpoint']=await checkpoint_scene()
        report['passed']=True
    except BaseException as error:report.update(error=str(error),traceback=traceback.format_exc())
    finally:native.write(ROOT/'native_frozen_audit.json',report)


_m5_finite_task=asyncio.ensure_future(main())
