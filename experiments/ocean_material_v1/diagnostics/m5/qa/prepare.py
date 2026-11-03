"""Pin pre-M5 evidence and checkpoint the live scene before source changes."""
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[3]


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    out = ROOT / 'qa/preparation.json'
    if out.exists():
        raise RuntimeError('Preserve the existing preparation')
    base = REPO / 'experiments/ocean_material_v1'
    pins = []
    counts = {}
    for name in ('m1', 'm2', 'm3', 'm4', 'm4_underwater', 'm4_standalone'):
        manifest = base / 'manifest.json' if name == 'm1' else base / 'diagnostics' / name / 'manifest.json'
        records = json.loads(manifest.read_text())['files']
        prefix = base if name == 'm1' else REPO
        for record in records:
            path = prefix / record['path']
            assert not set(path.parts) & {'_build', 'extscache', '__pycache__', '.cache'}
            data = path.read_bytes()
            assert hashlib.sha256(data).hexdigest() == record['sha256'], str(path)
            pins.append(dict(path=str(path.relative_to(REPO)), sha256=record['sha256']))
        counts[name] = len(records)
    write(ROOT / 'qa/historical_pins.json', pins)
    sources = []
    for path in sorted((REPO / 'source').rglob('*')):
        if set(path.parts) & {'__pycache__', '.cache', '_build', 'extscache'} or not path.is_file() or path.suffix == '.pyc':
            continue
        sources.append(dict(path=str(path.relative_to(REPO)), sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    write(ROOT / 'qa/source_before.json', sources)
    checkpoint_path = ROOT / 'qa/pre_checkpoint.json'
    if checkpoint_path.exists():
        checkpoint = json.loads(checkpoint_path.read_text())
        assert hashlib.sha256((Path(checkpoint['directory']) / 'scene.usdc').read_bytes()).hexdigest() == checkpoint['scene_sha256']
    else:
        with urlopen(Request('http://localhost:8011/debug/scene/checkpoint', data=b'{}', headers={'Content-Type': 'application/json'}), timeout=40) as response:
            checkpoint = json.load(response)
        write(checkpoint_path, checkpoint)
    assert checkpoint['ok']
    with urlopen('http://localhost:8011/openapi.json', timeout=10) as response:
        schema = json.load(response)
    write(ROOT / 'qa/openapi_before.json', schema)
    gpu = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,memory.used,memory.free,driver_version', '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=10)
    record = dict(host=platform.node(), platform=platform.platform(), historical_counts=counts,
                  gpu=dict(returncode=gpu.returncode, stdout=gpu.stdout, stderr=gpu.stderr),
                  loaded_driver=Path('/proc/driver/nvidia/version').read_text(),
                  checkpoint_id=checkpoint['checkpoint_id'])
    write(out, record)
    if gpu.returncode:
        payload = dict(selection='engineering_v1', phase_seconds=0, view='oblique')
        with urlopen(Request('http://localhost:8011/scene/ocean/material/preset/diagnostic/capture', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}), timeout=20) as response:
            result = json.load(response)
        write(ROOT / 'qa/guarded_capture_attempt01.json', dict(request=payload, response=result))
        assert result.get('ok') is False and result.get('render_attempted') is False
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
