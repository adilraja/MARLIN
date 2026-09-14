"""Capture or replay one HiDef marine snapshot. Python standard library only."""
import argparse
import json
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


def main(camera_model='hidef'):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api',default='http://localhost:8011')
    if camera_model == 'hidef':
        parser.add_argument('--roll',type=float,choices=(7.77,23.17,7.7675,23.1748),default=7.77)
    parser.add_argument('--target-x',type=float,default=0 if camera_model=='sony' else -3)
    parser.add_argument('--target-z',type=float,default=0)
    parser.add_argument('--replay',help='Capture ID returned by an earlier successful run')
    args = parser.parse_args()
    base = '/scene/camera/'+camera_model+'/marine/'
    path = base+'capture'
    body = dict(downsample=8 if camera_model=='sony' else 4,target_x_m=args.target_x,target_z_m=args.target_z)
    if camera_model == 'hidef':
        body['roll_deg'] = args.roll
    if args.replay:
        import re
        if not re.fullmatch(('sony_' if camera_model=='sony' else 'oblique_')+r'[a-z0-9_]+',args.replay):
            parser.error('Invalid capture ID')
        path = base+args.replay+'/replay'
        body = {}
    request = Request(args.api.rstrip('/')+path,data=json.dumps(body).encode(),
                      headers={'Content-Type':'application/json'},method='POST')
    try:
        with urlopen(request,timeout=240) as response:
            result = json.load(response)
    except HTTPError as exc:
        print(f'MARLIN returned HTTP {exc.code}: {exc.read().decode()}',file=sys.stderr)
        return 1
    except (URLError,TimeoutError) as exc:
        print(f'Could not complete the MARLIN request: {exc}',file=sys.stderr)
        return 1
    print(json.dumps(result,indent=2))
    return 0 if result.get('ok') else 1


if __name__=='__main__':
    sys.exit(main())
