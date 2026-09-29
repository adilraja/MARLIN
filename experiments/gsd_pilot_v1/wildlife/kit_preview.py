"""Create two named calibration instances using existing MARLIN HTTP endpoints.

Requires the empty startup stage checkpointed for this milestone. Leaves the
review scene open; never rebuilds an existing marine scene or overwrites animals.
These close-ups validate assets and transforms, not experiment camera/GSD.
"""
import json
from pathlib import Path
import shutil
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / 'kit_review'


def request(path, data=None):
    req = urllib.request.Request('http://localhost:8011' + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=90) as response:
        result = json.load(response)
    if result.get('ok') is False:
        raise RuntimeError(result)
    return result


def run():
    if (OUT / 'preview.json').exists():
        raise RuntimeError('Review record already exists; preserve this run')
    OUT.mkdir(exist_ok=True)
    measurement = json.loads((OUT.parent / 'measurements.json').read_text())
    before = request('/debug/scene/inspection')
    if any(p['path'] not in ('/World', '/Environment') for p in before['prims']):
        raise RuntimeError('Expected the empty startup stage; refusing to replace an existing scene')
    checkpoints = json.loads(Path('/tmp/marlin-m2-before-checkpoint.json').read_text())
    report = {'before': before, 'before_checkpoint': checkpoints, 'steps': {}, 'animals': {}}
    report['steps']['environment'] = request('/scene/survey/environment', {})
    report['steps']['grid'] = request('/debug/viewport/grid/hide', {})
    for species, name, position, views in [
        ('european_storm_petrel', 'M2CalibrationPetrel', [-200, 100, 0],
         [('oblique', 70, 30, 50), ('top', 1, 115, 0), ('side', 1, 0, 115)]),
        ('harbour_porpoise', 'M2CalibrationPorpoise', [200, 120, 0],
         [('oblique', 350, 180, 300), ('top', 1, 550, 0), ('side', 1, 0, 550)]),
    ]:
        data = measurement[species]
        payload = {'name': name, 'asset_path': str(ROOT / data['asset_path']),
                   'position': position, 'rotation': [0, 0, 0],
                   'model_rotation': data['correction_xyz_deg'],
                   'scale': data['spawn_scale_for_centimetre_stage']}
        item = {'request': payload, 'spawn': request('/scene/cetacean/spawn', payload), 'views': []}
        report['animals'][species] = item
        for label, distance, height, side in views:
            camera = request('/scene/camera/chase/start', {
                'target_name': name, 'camera_name': 'M2CalibrationCamera',
                'distance': distance, 'height': height, 'side_offset': side,
                'look_ahead': 0, 'look_height': 0, 'focal_length': 50,
                'documentary_mode': False})
            time.sleep(1)
            request('/debug/viewport/capture', {})
            capture = request('/debug/viewport/capture', {})
            destination = OUT / (species + '_' + label + '.png')
            shutil.copy2(capture['file_path'], destination)
            item['views'].append({'label': label, 'camera': camera, 'file': str(destination.relative_to(ROOT))})
            (OUT / 'progress.json').write_text(json.dumps(report, indent=2) + '\n')
    report['after'] = request('/debug/scene/inspection')
    report['checkpoint'] = request('/debug/scene/checkpoint', {})
    report['scope'] = 'Dry, above-water asset close-ups; not GSD imagery or underwater-visibility certification'
    (OUT / 'preview.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'ok': True, 'output': str(OUT), 'checkpoint': report['checkpoint']['checkpoint_id']}))


if __name__ == '__main__':
    run()
