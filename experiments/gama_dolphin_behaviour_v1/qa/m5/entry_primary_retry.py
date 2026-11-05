"""Retained smoke-02 retry, followed by one released finite primary job."""
import asyncio
import importlib.util
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('_marlin_m5_native_v2', ROOT/'native_m5.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


async def run():
    import omni.kit.app
    await native.main('smoke02', 'smoke')
    result = json.loads((ROOT/'smoke02/result.json').read_text())
    if result['status'] != 'passed':
        return
    native.write(ROOT/'primary_release_ready02.json', dict(ready=True, fixed_next_job='primary01'))
    started = time.monotonic()
    while time.monotonic()-started < 900:
        if (ROOT/'release_primary01.json').is_file():
            await native.main('primary01', 'primary')
            return
        await omni.kit.app.get_app().next_update_async()
    native.write(ROOT/'primary_release_timeout02.json', dict(failed=True, no_primary_job_executed=True))


_m5_finite_task = asyncio.ensure_future(run())
