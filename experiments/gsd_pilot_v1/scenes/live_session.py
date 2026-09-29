"""Bounded Kit HTTP orchestration; no arbitrary code execution or new server.

Stop live controllers before attaching frozen USD. The user-requested finish
state is the existing 11-animal animated demonstration, not a frozen snapshot.
"""
import argparse
import json
from pathlib import Path
import shutil
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
EXP = ROOT / 'experiments/gsd_pilot_v1'
OUT = EXP / 'scenes'


def request(path, data=None):
    req = urllib.request.Request('http://localhost:8011' + path,
        data=None if data is None else json.dumps(data).encode(),
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=180) as response:
        result = json.load(response)
    if result.get('ok') is False:
        raise RuntimeError(path + ': ' + str(result)[:2000])
    return result


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def stop_controllers():
    for path in ['/scene/camera/chase/stop', '/scene/cetaceans/gallery/swim/stop',
                 '/scene/cetacean/swim/stop', '/scene/ocean/animation/stop']:
        request(path, {})
    players = request('/scene/birds/petrel/playback')['players']
    for player in players:
        request('/scene/birds/petrel/playback', {'name': player['name'], 'action': 'stop'})
    return statuses()


def statuses():
    result = {name: request(path) for name, path in {
        'ocean': '/scene/ocean/animation/status',
        'gallery': '/scene/cetaceans/gallery/swim/status',
        'swimmer': '/scene/cetacean/swim/status',
        'camera': '/scene/camera/chase/status',
        'petrel': '/scene/birds/petrel/playback'}.items()}
    return result


def assert_stopped(state):
    for name in ('ocean', 'gallery', 'swimmer', 'camera'):
        if state[name].get('running') is not False:
            raise RuntimeError('Controller still active: ' + name)
    if state['petrel']['players']:
        raise RuntimeError('Petrel controller still active')


def restore(checkpoint):
    return request('/debug/scene/checkpoint/' + checkpoint + '/restore', {})


def empty_checkpoint():
    # M2 retained the initially empty Kit stage, including stage units and camera.
    return json.loads((EXP / 'wildlife/kit_review/before_checkpoint.json').read_text())['checkpoint_id']


def prepare():
    target = OUT / 'base_checkpoint.json'
    if target.exists():
        raise RuntimeError('Base already recorded; preserve evidence')
    try:
        stopped = stop_controllers()
        assert_stopped(stopped)
        restore(empty_checkpoint())
        environment = request('/scene/survey/environment', {})
        request('/scene/ocean/animation/stop', {})
        stopped = statuses(); assert_stopped(stopped)
        checkpoint = request('/debug/scene/checkpoint', {})
        save(target, checkpoint)
        save(OUT / 'base_setup.json', {'environment': environment, 'controllers': stopped})
        shutil.copy2(Path(checkpoint['directory']) / 'scene.usdc', OUT / 'environment_base.usdc')
        print(json.dumps({'base': checkpoint['checkpoint_id'], 'recorded_renderer_keys': len(checkpoint['renderer_settings'])}), flush=True)
    except Exception:
        preview()
        raise


def replay():
    index = json.loads((OUT / 'snapshot_index.json').read_text())
    result_path = OUT / 'live_replay.json'
    if result_path.exists():
        raise RuntimeError('Replay evidence already exists')
    results = []
    try:
        assert_stopped(stop_controllers())
        for item in index:
            runs = []
            for attempt in range(2):
                restore(item['checkpoint_id'])
                assert_stopped(statuses())
                first = request('/debug/scene/checkpoint', {})
                time.sleep(2)
                second = request('/debug/scene/checkpoint', {})
                assert_stopped(statuses())
                runs.append({'attempt': attempt, 'immediate': first, 'after_wait': second})
            results.append({'scene_id': item['scene_id'], 'runs': runs})
            save(OUT / 'live_replay_progress.json', results)
            print('Replayed ' + item['scene_id'], flush=True)
        save(result_path, {'scope': 'Two live attachments and delayed snapshots per scene; RGB testing belongs to M4', 'results': results})
    finally:
        preview()


def preview(milestone=3):
    assert_stopped(stop_controllers())
    # Old empty snapshots predate expanded renderer recording. Restore the
    # observed pre-experiment settings too, so M3 AA/sampling choices do not
    # leak into the user's interactive demonstration.
    import tempfile
    checkpoint_root = ROOT / 'artifacts/scene_checkpoints'
    original = checkpoint_root / empty_checkpoint()
    target = Path(tempfile.mkdtemp(prefix='checkpoint_', dir=checkpoint_root))
    shutil.copy2(original / 'scene.usdc', target / 'scene.usdc')
    metadata = json.loads((original / 'metadata.json').read_text())
    if (OUT / 'base_checkpoint.json').exists():
        metadata['renderer_settings'] = json.loads((OUT / 'base_checkpoint.json').read_text())['renderer_settings']
    save(target / 'metadata.json', metadata)
    restore(target.name)
    environment = request('/scene/demonstration/environment', {})
    gallery = request('/scene/cetaceans/gallery', {'activate_viewport_camera': False})
    swim = request('/scene/cetaceans/gallery/swim/start', {})
    before = statuses()
    before_checkpoint = request('/debug/scene/checkpoint', {})
    time.sleep(3)
    after = statuses()
    after_checkpoint = request('/debug/scene/checkpoint', {})
    assert after['gallery']['running'] and after['gallery']['animal_count'] == 11
    a = {x['name']: x for x in before['gallery']['animals']}
    assert all(x['body_animation'] and x['z'] != a[x['name']]['z'] for x in after['gallery']['animals'])
    assert after['ocean']['running'] and after['ocean']['elapsed'] > before['ocean']['elapsed']
    assert after['ocean']['speed'] > 0
    record = {'passed': True, 'requested_finish_state': 'moving_water_and_11_default_animals_swimming',
              'environment': environment, 'gallery_loaded_count': gallery['loaded_count'],
              'swim_started': swim['running'], 'before': before, 'after': after,
              'before_checkpoint': before_checkpoint, 'after_checkpoint': after_checkpoint,
              'human_visual_validation': 'viewport_left_running_for_user'}
    record['milestone'] = milestone
    report_path = EXP / ('qa/milestone_%d_animation_preview.json' % milestone)
    if report_path.exists() and (EXP / ('qa/milestone_%d_manifest.json' % milestone)).exists():
        # Later manual previews must not invalidate a completed milestone.
        from datetime import datetime, timezone
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        report_path = EXP / ('qa/animation_previews/milestone_%d_%s.json' % (milestone, stamp))
    save(report_path, record)
    print('Verified animated water and all 11 moving, body-animated default animals.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'replay', 'preview'])
    parser.add_argument('--milestone', type=int, choices=range(3, 9), default=3,
                        help='Label a completion preview without overwriting earlier milestone evidence')
    args = parser.parse_args()
    if args.action == 'preview':
        preview(args.milestone)
    else:
        globals()[args.action]()
