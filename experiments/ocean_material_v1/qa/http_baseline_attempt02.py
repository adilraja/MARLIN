"""Bounded audit fallback using only existing MARLIN endpoints."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
from urllib.request import Request, urlopen

OUT = Path(__file__).resolve().parents[1]
DEST = OUT/'baseline/frozen_01'


def request(path, data=None):
    req = Request('http://localhost:8011'+path,
                  data=json.dumps(data).encode() if data is not None else None,
                  headers={'Content-Type':'application/json'})
    with urlopen(req, timeout=60) as stream:
        result=json.load(stream)
    if result.get('ok') is False or 'error' in result:
        raise RuntimeError(json.dumps(result))
    return result


def save(name, value):
    (DEST/name).write_text(json.dumps(value, indent=2)+'\n')


def main():
    if DEST.exists():
        if {p.name for p in DEST.iterdir()} != {'checkpoint.json', 'scene.usdc'}:
            raise RuntimeError('Refusing to overwrite any previous baseline execution')
        checkpoint=json.loads((DEST/'checkpoint.json').read_text())
    else:
        DEST.mkdir()
        checkpoint=request('/debug/scene/checkpoint', {})
        save('checkpoint.json',checkpoint)
        source=Path(checkpoint['directory'])
        shutil.copyfile(source/'scene.usdc', DEST/'scene.usdc')
    assert hashlib.sha256((DEST/'scene.usdc').read_bytes()).hexdigest()==checkpoint['scene_sha256']
    save('ocean_before.json', request('/scene/ocean/animation/status'))
    save('camera_stop.json', request('/scene/camera/chase/stop', {}))
    save('ocean_stop.json', request('/scene/ocean/animation/stop', {}))
    restore='/debug/scene/checkpoint/'+checkpoint['checkpoint_id']+'/restore'
    save('restore_01.json', request(restore, {}))
    save('material_before.json', request('/scene/ocean/material/status'))
    save('settings_before.json', request('/debug/render-settings'))
    save('inspection.json', request('/debug/scene/inspection'))
    results=[]
    for name in ('warmup.png','baseline_01.png','baseline_02.png','baseline_03.png'):
        gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,memory.used,memory.free,driver_version',
                                     '--format=csv,noheader,nounits'],text=True,timeout=10)
        if int(gpu.splitlines()[0].split(',')[3])<768:
            raise RuntimeError('GPU memory guard: less than 768 MiB free')
        before=time.monotonic()
        result=request('/debug/viewport/capture', {})
        shutil.copyfile(result['file_path'], DEST/name)
        results.append({'name':name,'gpu_before':gpu,'elapsed_seconds':time.monotonic()-before,'response':result})
        save('captures.json',results)
    save('restore_02.json', request(restore, {}))
    after=request('/scene/ocean/material/status');save('material_after.json',after)
    settings=request('/debug/render-settings');save('settings_after.json',settings)
    assert after==json.loads((DEST/'material_before.json').read_text())
    assert settings==json.loads((DEST/'settings_before.json').read_text())
    save('result.json',{'status':'executed','captures':4,'material_roundtrip_equal':True,
                        'water_and_fog_settings_roundtrip_equal':True,
                        'camera':checkpoint['camera'],'resolution':checkpoint['resolution'],
                        'limitations':'Nonmetric appearance baseline; controller phases not serialized; no candidate material applied.'})
    print((DEST/'result.json').read_text())


if __name__=='__main__':
    main()
