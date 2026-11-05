"""M1-only live inventory and optional frozen checkpoint through existing APIs."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import urllib.error
import urllib.request

REPO = Path(__file__).resolve().parents[3]
BASE = REPO / 'experiments/gama_dolphin_behaviour_v1'


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def request(path, method='GET'):
    start = datetime.datetime.now(datetime.timezone.utc).isoformat()
    req = urllib.request.Request('http://localhost:8011' + path,
                                 data=b'{}' if method == 'POST' else None,
                                 headers={'Content-Type': 'application/json'}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as response:
            status, data = response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        status, data = exc.code, json.loads(exc.read())
    return dict(method=method, path=path, started_utc=start,
                finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                http_status=status, response=data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--checkpoint', action='store_true')
    args = parser.parse_args()
    assert args.name.replace('_', '').isalnum()
    out = BASE / 'baseline' / args.name
    out.mkdir(parents=True, exist_ok=False)
    schema = request('/openapi.json')
    write(out / 'openapi.json', schema)
    paths = schema['response']['paths']
    calls = {
        'inspection': '/debug/scene/inspection',
        'ocean': '/scene/ocean/animation/status',
        'swimmer': '/scene/cetacean/swim/status',
        'gallery': '/scene/cetaceans/gallery/swim/status',
        'chase': '/scene/camera/chase/status',
        'material': '/scene/ocean/material/status',
        'preset': '/scene/ocean/material/preset/status',
        'capture_sdk': '/debug/capture-capabilities',
        'diagnostic_capabilities': '/scene/ocean/material/diagnostic/capabilities',
        'gama_v1': '/integration/gama/actor/status',
        'gama_v2': '/integration/gama/v2/actor/status',
    }
    records = {}
    for name, path in calls.items():
        records[name] = request(path)
        write(out / (name + '.json'), records[name])
    prims = records['inspection']['response'].get('prims', [])
    for prim in prims:
        name = prim['path'].rsplit('/', 1)[-1]
        if any(s in name.lower() for s in ('dolphin', 'bottlenose')):
            result = request('/scene/cetacean/rig/status?name=' + name)
            write(out / ('rig_' + name + '.json'), result)
    gpu = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,memory.used,memory.free,driver_version',
                          '--format=csv,noheader'], capture_output=True, text=True)
    write(out / 'gpu.json', dict(returncode=gpu.returncode, stdout=gpu.stdout, stderr=gpu.stderr))
    if args.checkpoint:
        record = request('/debug/scene/checkpoint', 'POST')
        write(out / 'checkpoint.json', record)
        assert record['http_status'] == 200 and record['response']['ok'], record
        checkpoint = record['response']
        source = Path(checkpoint['directory'])
        assert source.parent == REPO / 'artifacts/scene_checkpoints'
        shutil.copyfile(source / 'scene.usdc', out / 'scene.usdc')
        shutil.copyfile(source / 'metadata.json', out / 'checkpoint_metadata.json')
        assert hashlib.sha256((out / 'scene.usdc').read_bytes()).hexdigest() == checkpoint['scene_sha256']
        for name in ('ocean', 'swimmer', 'gallery', 'chase', 'preset'):
            write(out / (name + '_after_checkpoint.json'), request(calls[name]))
    write(out / 'collection.json', dict(
        scope='M1 read-only inventory; optional existing frozen-checkpoint endpoint only',
        schema_paths=len(paths), gama_routes=[p for p in paths if p.startswith('/integration/gama')],
        writes_to_runtime=['POST /debug/scene/checkpoint'] if args.checkpoint else [],
        new_behaviour_or_animation_implemented=False,
        caveat='HTTP observations bracket the frozen scene; controller phases are not atomically serialized by the checkpoint endpoint.'))
    print(json.dumps(dict(output=str(out), observations=len(records), checkpoint=args.checkpoint,
                          gama_routes=len([p for p in paths if p.startswith('/integration/gama')]))))


if __name__ == '__main__':
    main()
