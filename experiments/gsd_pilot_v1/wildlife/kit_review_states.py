"""Finish M2 framing, heading and static shallow-placement checks via Kit HTTP."""
import json
from pathlib import Path
import shutil
import time
from kit_preview import request, ROOT, OUT


def capture(name, filename, height, look_ahead=0):
    camera = request('/scene/camera/chase/start', {
        'target_name': name, 'camera_name': 'M2CalibrationCamera',
        'distance': .1, 'height': height, 'side_offset': 0,
        'look_ahead': look_ahead, 'look_height': 0, 'focal_length': 50,
        'documentary_mode': False})
    time.sleep(1)
    request('/debug/viewport/capture', {})
    result = request('/debug/viewport/capture', {})
    dest = OUT / filename
    shutil.copy2(result['file_path'], dest)
    return {'camera': camera, 'file': str(dest.relative_to(ROOT))}


def run():
    if (OUT / 'state_review.json').exists():
        raise RuntimeError('State review exists; preserve it')
    preview = json.loads((OUT / 'preview.json').read_text())
    measurement = json.loads((OUT.parent / 'measurements.json').read_text())
    report = {'scope': 'Engineering static asset/heading/placement review; not GSD or biological behaviour validation',
              'reframed': {}, 'heading_checks': {}}
    for species, height, aim in [('european_storm_petrel', 170, 6.3), ('harbour_porpoise', 1000, 0)]:
        item = preview['animals'][species]
        name = item['request']['name']
        request('/scene/cetacean/transform', {'name': name, 'position': item['request']['position'], 'rotation': [0, 0, 0]})
        report['reframed'][species] = capture(name, species + '_top_complete.png', height, aim)
        try:
            request('/scene/cetacean/transform', {'name': name, 'rotation': [0, 90, 0]})
            report['heading_checks'][species] = {
                'inspection': request('/debug/scene/inspection'),
                'capture': capture(name, species + '_heading90.png', height, 0)}
        finally:
            request('/scene/cetacean/transform', {'name': name, 'rotation': [0, 0, 0]})
    maximum_y = measurement['harbour_porpoise']['metric_world_bounds']['maximum'][1]
    clearance = .02
    y = -maximum_y - clearance
    request('/scene/cetacean/transform', {'name': 'M2CalibrationPorpoise', 'position': [200, y * 100, 0]})
    report['porpoise_shallow'] = {
        'root_y_m': y, 'top_clearance_below_flat_water_m': clearance,
        'placement_status': 'engineering_static_clearance_not_biological_depth_or_breathing_waterline',
        'capture': capture('M2CalibrationPorpoise', 'harbour_porpoise_shallow_top.png', 1000)}
    report['final_inspection'] = request('/debug/scene/inspection')
    report['final_checkpoint'] = request('/debug/scene/checkpoint', {})
    (OUT / 'state_progress.json').write_text(json.dumps(report, indent=2) + '\n')
    report['ocean_status'] = request('/scene/ocean/animation/status')
    report['swim_status'] = request('/scene/cetacean/swim/status')
    report['gallery_swim_status'] = request('/scene/cetaceans/gallery/swim/status')
    (OUT / 'state_review.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'ok': True, 'porpoise_root_y_m': y,
                      'checkpoint': report['final_checkpoint']['checkpoint_id']}))


if __name__ == '__main__':
    run()
