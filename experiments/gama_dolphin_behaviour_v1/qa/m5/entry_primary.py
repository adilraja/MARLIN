"""One smoke check and one explicitly released, finite primary M5 job."""
import asyncio
import importlib.util
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('_marlin_m5_native', ROOT/'native_m5.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


async def run():
    import omni.kit.app
    await native.main('smoke01', 'smoke')
    result = json.loads((ROOT/'smoke01/result.json').read_text())
    if result['status'] != 'passed':
        return
    native.write(ROOT/'primary_release_ready.json', dict(ready=True, fixed_next_job='primary01'))
    started = time.monotonic()
    while time.monotonic()-started < 900:
        if (ROOT/'release_primary01.json').is_file():
            await native.main('primary01', 'primary')
            return
        await omni.kit.app.get_app().next_update_async()
    native.write(ROOT/'primary_release_timeout.json', dict(failed=True, no_primary_job_executed=True))


_m5_finite_task = asyncio.ensure_future(run())
