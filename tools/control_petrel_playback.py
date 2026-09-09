"""Control the petrel already spawned by preview_petrel_rig.py."""
import argparse
import json
from preview_petrel_rig import request


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'pause', 'resume', 'stop', 'status', 'flap', 'glide'])
    parser.add_argument('--speed', type=float, default=None, help='Playback multiplier, 0.05–4 (not calibrated wingbeat frequency)')
    parser.add_argument('--transition', type=float, default=0.5, help='Blend duration in seconds, 0–10')
    args = parser.parse_args()
    data = {'action': args.action, 'transition_seconds': args.transition}
    if args.action in ('flap', 'glide'):
        data.update(action='start', mode=args.action)
    if args.speed is not None:
        data['speed'] = args.speed
    print(json.dumps(request('/scene/birds/petrel/playback', None if args.action == 'status' else data), indent=2))
