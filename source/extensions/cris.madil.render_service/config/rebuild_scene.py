"""Rebuild all 18 instances via existing Kit HTTP APIs.

Usage: python3 rebuild_scene.py --mode survey
       python3 rebuild_scene.py --mode demonstration
Placement is provisional display calibration, never physical calibration.
"""
import argparse
import json
import urllib.request
from pathlib import Path


def request(path, data=None):
    req = urllib.request.Request('http://localhost:8011' + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as response:
        result = json.load(response)
    if result.get('ok') is False:
        raise RuntimeError(f'{path}: {result}')
    return result


def rebuild(mode):
    request('/scene/cetaceans/gallery/swim/stop', {})
    request('/scene/marine/setup', {'start_swimming': False, 'start_chase_camera': False})
    original = request('/scene/cetaceans/gallery', {'elevation': 0, 'spacing': 2000, 'activate_viewport_camera': True})
    added = request('/scene/survey/gallery', {'elevation': 0, 'activate_viewport_camera': False})
    names = ['Dolphin_001'] + [a['name'] for a in original['animals']] + [a['name'] for a in added['animals']]
    # First reset roots, retaining the original gallery's model corrections.
    for name in names:
        rotation = [-90, 0, 0] if name == 'SurveyInspect_harbour_porpoise' else [0, 0, 0]
        request('/scene/cetacean/transform', {'name': name, 'position': [0,0,0], 'scale': 1, 'rotation': rotation})
    inspection = request('/debug/scene/inspection')
    records = {p['path'].rsplit('/',1)[-1]:p for p in inspection['prims']}
    bird_names = {'SurveyInspect_common_tern', 'SurveyInspect_european_storm_petrel', 'SurveyInspect_guillemot', 'SurveyInspect_northern_gannet'}
    placements = []
    for index, name in enumerate(names):
        record = records[name]
        lo, hi = record['bounds_min'], record['bounds_max']
        dimensions = [b-a for a,b in zip(lo,hi)]
        bird = name in bird_names
        scale = (350 if bird else 800) / max(dimensions)
        # Full composed bounds include helper geometry. Surface placement is
        # explicitly provisional until individual body-only waterlines exist.
        waterline = lo[1] + (0.1 if bird else 0.65) * dimensions[1]
        position = [(index%5-2)*1400-scale*(lo[0]+hi[0])/2,
                    -scale*waterline,
                    (index//5-1.5)*1400-scale*(lo[2]+hi[2])/2]
        request('/scene/cetacean/transform', {'name':name, 'position':position, 'scale':scale})
        placements.append({'name':name,'position':position,'scale':scale,'status':'provisional_bounds_fit'})
    if mode == 'survey':
        preset = json.loads(Path(__file__).with_name('survey_environment_v1.json').read_text())
        for section, path in [('ocean','/scene/ocean/animation/start'),('material','/scene/ocean/material'),('environment','/scene/environment'),('underwater_cue','/scene/ocean/underwater-cue')]:
            request(path, preset[section])
    else:
        # Existing gallery preview owns 11 transforms and common depth;
        # those override the static layout while demonstration is running.
        request('/scene/cetaceans/gallery/swim/start', {'depth':-20,'activate_viewport_camera':True})
    capture = request('/debug/viewport/capture', {})
    return {'ok':True,'mode':mode,'instance_count':len(names),'placements':placements,'capture':capture,
            'limitations':['Bird support geometry and poses require individual review.',
                           'Display scales are not physical animal dimensions.',
                           'Demonstration animates the original 11; the other seven remain static.']}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['survey','demonstration'],default='survey')
    args=parser.parse_args()
    print(json.dumps(rebuild(args.mode), indent=2))
