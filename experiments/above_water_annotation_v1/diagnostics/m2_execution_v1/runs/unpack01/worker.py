"""Unpack only the eleven approved, payload-verified vendor archives."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import traceback
import omni.ext
import omni.kit.app

BASE = Path('/home/madil/kit-app-template/experiments/above_water_annotation_v1')
OUT = Path(os.environ['ANNOTATION_EXECUTION_OUTPUT'])


async def main():
    app = omni.kit.app.get_app()
    result = dict(passed=False, packages=[])
    try:
        qpath = BASE/'diagnostics/m2_execution_v1/quarantine_verification.json'
        expected = (qpath.with_suffix('.sha256')).read_text().split()[0]
        assert hashlib.sha256(qpath.read_bytes()).hexdigest() == expected
        q = json.loads(qpath.read_text())
        assert q['passed'] and not q['failures'] and len(q['packages']) == 11
        approval = Path(q['approval_record'])
        assert hashlib.sha256(approval.read_bytes()).hexdigest() == q['approval_sha256']
        dest = BASE/'dependencies/native_provider_1102_v1/extensions'
        dest.mkdir(exist_ok=False)
        for pid, item in sorted(q['packages'].items()):
            archive = Path(item['archive'])
            assert hashlib.sha256(archive.read_bytes()).hexdigest() == item['sha256']
            omni.ext.unpack_extension(str(archive), str(dest), ext_id=pid, skip_security_checks=False)
            folder = dest/pid
            assert (folder/'config/extension.toml').is_file(), str(folder)
            result['packages'].append(dict(package_id=pid, folder=str(folder)))
            print('Approved private unpack:', pid, flush=True)
            await app.next_update_async()
        result['passed'] = True
        result['destination'] = str(dest)
    except Exception:
        result['error'] = traceback.format_exc()
        print(result['error'], flush=True)
    finally:
        (OUT/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        app.post_quit(0 if result['passed'] else 1)


asyncio.ensure_future(main())
