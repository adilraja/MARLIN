"""Run declared bounded M3 conditions once; retain every response and GPU sample."""
import argparse
import json
from pathlib import Path
import subprocess
import threading
import time
from urllib.request import Request, urlopen

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEPTHS = (.25, .75, 1.25)


def cases(suite):
    if suite == 'controls':
        return [{'condition': 'clear', 'depth_m': d} for d in DEPTHS] + [
            {'condition': 'clear', 'depth_m': .75},
            {'condition': 'clear', 'depth_m': .75, 'tone_map_probe': True}]
    if suite == 'absorption':
        return [{'condition': 'absorption', 'native_distance': n, 'depth_m': d}
                for n in (50, 100, 200) for d in DEPTHS]
    if suite == 'scattering':
        return [{'condition': c, 'depth_m': d} for c in ('scattering_low', 'scattering_high') for d in DEPTHS] + [
            {'condition': 'scattering_low', 'depth_m': .75},
            {'condition': 'scattering_high', 'depth_m': .75}]
    if suite == 'units':
        return [{'condition': c, 'depth_m': .75, 'meters_per_scene_unit': 1.0,
                 'native_distance': n} for c, n in [('clear', 100), ('absorption', 1), ('absorption', 100)]]
    if suite == 'exposure':
        return [{'condition': 'clear', 'depth_m': .75, 'exposure_probe': True}]
    if suite == 'pathprobe':
        return [{'condition': c, 'depth_m': .75} for c in ('clear', 'absorption', 'scattering_high')]
    raise ValueError(suite)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('suite', choices=['controls', 'absorption', 'scattering', 'units', 'exposure', 'pathprobe'])
    parser.add_argument('--pathtraced', action='store_true')
    parser.add_argument('--unclamped', action='store_true')
    parser.add_argument('--final', action='store_true')
    args = parser.parse_args()
    qa = ROOT / ('qa/final' if args.final else 'qa/unclamped' if args.unclamped else 'qa/pathtraced' if args.pathtraced else 'qa/controlled')
    qa.mkdir(exist_ok=True)
    log = qa / (args.suite + '_execution.json')
    if log.exists():
        raise RuntimeError('Preserve the previous execution; do not overwrite it')
    samples, rows = [], []
    stop = threading.Event()

    def observe_gpu():
        while not stop.is_set():
            result = subprocess.run(['nvidia-smi', '--query-gpu=timestamp,memory.used,memory.free',
                                     '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=5)
            samples.append({'monotonic': time.monotonic(), 'returncode': result.returncode,
                            'observation': result.stdout.strip(), 'error': result.stderr.strip()})
            stop.wait(1)

    thread = threading.Thread(target=observe_gpu)
    thread.start()
    try:
        for payload in cases(args.suite):
            if args.pathtraced:
                payload['renderer'] = 'PathTracing'
            started = time.monotonic()
            req = Request('http://localhost:8011/scene/ocean/material/diagnostic/medium/capture',
                          data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
            with urlopen(req, timeout=100) as response:
                result = json.load(response)
            row = {'request': payload, 'response': result, 'elapsed_seconds': time.monotonic() - started}
            rows.append(row)
            log.write_text(json.dumps(rows, indent=2) + '\n')
            if not result.get('ok'):
                raise RuntimeError('Diagnostic failed: ' + json.dumps(result))
            directory = Path(result['directory'])
            deadline = time.monotonic() + 10
            while True:
                try:
                    with Image.open(directory / 'rgb.png') as im:
                        assert im.size == (512, 384), im.size
                        im.verify()
                    assert (directory / 'hdr.npz').stat().st_size > 100
                    assert (directory / 'hdr.exr').stat().st_size > 100
                    break
                except (FileNotFoundError, OSError):
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(.1)
            row['saved_outputs_verified'] = True
            log.write_text(json.dumps(rows, indent=2) + '\n')
            print(json.dumps({'request': payload, 'seconds': round(row['elapsed_seconds'], 2),
                              'directory': result['directory']}), flush=True)
    finally:
        stop.set()
        thread.join(timeout=6)
        (qa / (args.suite + '_gpu.json')).write_text(json.dumps(samples, indent=2) + '\n')


if __name__ == '__main__':
    main()
