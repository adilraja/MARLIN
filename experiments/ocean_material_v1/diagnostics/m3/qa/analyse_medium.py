"""Fixed-ROI measurements of retained M3 native HDR and display PNG outputs."""
import json
import argparse
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
TARGET = (248, 184, 264, 200)
BACKGROUNDS = ((190, 184, 206, 200), (306, 184, 322, 200))


def roi(array, box):
    x0, y0, x1, y1 = box
    return array[y0:y1, x0:x1, :3].reshape(-1, 3)


def measure(array):
    if array.shape[:2] != (384, 512) or array.ndim != 3 or array.shape[2] < 3:
        raise ValueError('Expected full 512x384 RGB(A) output')
    if not np.isfinite(array).all():
        raise ValueError('Nonfinite samples')
    target = roi(array, TARGET).mean(axis=0)
    background = np.concatenate([roi(array, b) for b in BACKGROUNDS]).mean(axis=0)
    signal = target - background
    denominator = target + background
    contrast = np.divide(signal, denominator, out=np.zeros(3), where=denominator != 0)
    return {'target_rgb': target.tolist(), 'background_rgb': background.tolist(),
            'signal_rgb': signal.tolist(), 'michelson_rgb': contrast.tolist(),
            'target_std_rgb': roi(array, TARGET).std(axis=0).tolist()}


def load_rows(pathtraced=False, final=False):
    rows = []
    for suite in ('controls', 'absorption', 'scattering', 'units', 'exposure'):
        file = ROOT / ('qa/' + ('final' if final else 'pathtraced' if pathtraced else 'controlled') + '/' + suite + '_execution.json')
        if not file.exists():
            continue
        for index, item in enumerate(json.loads(file.read_text())):
            if not item['response'].get('ok'):
                continue
            directory = Path(item['response']['directory'])
            metadata = json.loads((directory / 'metadata.json').read_text())
            hdr = np.load(directory / 'hdr.npz', allow_pickle=False)['rgba'].astype(np.float64)
            ldr = np.array(Image.open(directory / 'rgb.png').convert('RGB'), dtype=np.float64) / 255
            rows.append({'suite': suite, 'index': index, 'directory': str(directory.relative_to(ROOT)),
                         'request': metadata['request'], 'hdr': measure(hdr), 'ldr': measure(ldr),
                         'elapsed_seconds': item['elapsed_seconds']})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pathtraced', action='store_true')
    parser.add_argument('--final', action='store_true')
    args = parser.parse_args()
    rows = load_rows(args.pathtraced, args.final)
    for row in rows:
        req = row['request']
        clear = next(r for r in rows if r['request']['condition'] == 'clear'
                     and r['request']['depth_m'] == req['depth_m']
                     and r['request']['meters_per_scene_unit'] == req['meters_per_scene_unit']
                     and not r['request']['tone_map_probe'])
        for domain in ('hdr', 'ldr'):
            row[domain]['signal_relative_to_clear_rgb'] = (
                np.array(row[domain]['signal_rgb']) / np.array(clear[domain]['signal_rgb'])).tolist()
        print(req, 'relative HDR', np.round(row['hdr']['signal_relative_to_clear_rgb'], 5),
              'contrast', np.round(row['hdr']['michelson_rgb'], 5))
    record = {'target_roi_xyxy': TARGET, 'background_rois_xyxy': BACKGROUNDS,
              'indexing': 'half-open, top-left image origin',
              'hdr_domain': 'Native HdrColor float; no absolute radiometric calibration',
              'ldr_domain': 'tone-mapped display RGB PNG normalized to [0,1], not linear radiance',
              'rows': rows}
    filename = 'measurements_final.json' if args.final else 'measurements_pathtraced.json' if args.pathtraced else 'measurements.json'
    (ROOT / ('qa/' + filename)).write_text(json.dumps(record, indent=2) + '\n')


if __name__ == '__main__':
    main()
