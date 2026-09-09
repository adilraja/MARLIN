"""Rebuild a presentation gallery through MARLIN HTTP; capture provisional porpoise.

Run with Kit already running. Changes the live scene, not source assets.
Other animals retain engineering display scales, not biological calibration.
"""
import json
import shutil
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/porpoise_kit_review'


def request(path, data=None, allow_partial=False):
    payload = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request('http://localhost:8011' + path, data=payload,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as response:
        result = json.load(response)
    if not result.get('ok') and not allow_partial:
        raise RuntimeError(result)
    return result


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    results = {}
    results['gallery'] = request('/scene/cetaceans/gallery', {'elevation': 0, 'activate_viewport_camera': False})
    results['survey'] = request('/scene/survey/gallery', {'elevation': 0, 'activate_viewport_camera': False}, allow_partial=True)
    failures = [a for a in results['survey'].get('animals', []) if not a.get('ok')]
    if any(a.get('species') != 'harbour_porpoise' or 'Unowned prim' not in a.get('error', '') for a in failures):
        raise RuntimeError(results['survey'])
    # Separate survey slots from the original marine gallery. Bounds placement
    # is presentation-only; do not infer physical scale or biological posture.
    inspection = request('/debug/scene/inspection')
    index = 0
    for prim in inspection['prims']:
        name = prim['path'].split('/')[-1]
        if not prim['path'].startswith('/World/Cetaceans/'):
            continue
        low, high = prim['bounds_min'], prim['bounds_max']
        transform = next(op['value'] for op in prim['xform_ops'] if op['name'] == 'xformOp:translate')
        position = [float(v) for v in transform.strip('()').split(',')]
        bird = name in {'SurveyInspect_common_tern', 'SurveyInspect_european_storm_petrel', 'SurveyInspect_guillemot', 'SurveyInspect_northern_gannet'}
        ratio = (350 if bird else 800) / max(b-a for a, b in zip(low, high))
        old_scale = next(op['value'] for op in prim['xform_ops'] if op['name'] == 'xformOp:scale')
        scale = float(old_scale.strip('()').split(',')[0]) * ratio
        position = [(index % 5 - 2)*1400 - ratio*((low[0]+high[0])/2-position[0]),
                    -ratio*(low[1]+(.1 if bird else .65)*(high[1]-low[1])-position[1]),
                    (index // 5 - 1.5)*1400-ratio*((low[2]+high[2])/2-position[2])]
        request('/scene/cetacean/transform', {'name': name, 'position': position, 'scale': scale})
        index += 1
    asset = ROOT / 'assets/cetaceans/model_75a_-_harbor_porpoise/working/calibration_v1/usd/harbour_porpoise_static_candidate.usd'
    # 100 scene units per metre follows the existing centimetre presentation.
    # This is explicit reference conversion, not an additional species scaling.
    results['candidate'] = request('/scene/cetacean/spawn', {
        'name': 'SurveyInspect_harbour_porpoise', 'asset_path': str(asset),
        'position': [0, 0, -4500], 'model_rotation': [-90, 0, 0], 'scale': 100})
    for label, camera in [
        ('whole_scene', {'distance': 14000, 'height': 13000, 'side_offset': 0, 'look_ahead': 3500}),
        ('porpoise_closeup', {'distance': 160, 'height': 110, 'side_offset': 240, 'look_ahead': 0}),
    ]:
        request('/scene/camera/chase/start', {
            'target_name': 'SurveyInspect_harbour_porpoise', 'camera_name': 'PorpoiseReviewCamera',
            'documentary_mode': False, 'look_height': 0, 'focal_length': 35, **camera})
        time.sleep(3)
        request('/debug/viewport/capture', {})  # Discard stale first frame after camera switch.
        capture = request('/debug/viewport/capture', {})
        shutil.copy2(capture['file_path'], OUT / (label + '.png'))
    results['scene'] = request('/debug/scene/inspection')
    results['scientific_render_ready'] = False
    results['note'] = 'Static candidate; landmark correspondence and biological waterline remain provisional. Other animals are presentation-only.'
    (OUT / 'review.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps({'output': str(OUT), 'animal_count': sum(p['path'].startswith('/World/Cetaceans/') for p in results['scene']['prims'])}))


if __name__ == '__main__':
    run()
