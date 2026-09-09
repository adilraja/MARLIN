"""Minimal HTTP preview of validated petrel skeletal assets in running Kit.

--pose animation starts independent skeletal playback. This tool does not change
the shared timeline or existing animal controllers. Static poses are exported
skeletal snapshots, available independently of timeline playback.
"""
import argparse
import json
import math
import shutil
import time
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ASSET=ROOT/'assets/birds/european_storm_petrel'


def request(path,data=None):
    req=urllib.request.Request('http://localhost:8011'+path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=60) as response:result=json.load(response)
    if result.get('ok') is False:raise RuntimeError(result)
    return result


def preview(pose):
    validation=json.loads((ASSET/'working/usd_validation.json').read_text())
    if not validation['ok']:raise RuntimeError('Run validate_petrel_usd.py first')
    # Release the temporary binding before replacing a referenced pose asset.
    request('/scene/birds/petrel/playback', {'action':'stop','name':'PetrelRigTest'})
    filename='european_storm_petrel_rigged.usd' if pose=='animation' else pose+'.usd'
    result=request('/scene/cetacean/spawn',{'name':'PetrelRigTest',
        'asset_path':str(ASSET/'usd'/filename),'position':[0,1400,0],
        'model_rotation':[-90,0,0],'rotation':[0,-math.degrees(math.atan2(11.5,21)),0],
        'scale':8})
    if pose=='animation':
        result['playback']=request('/scene/birds/petrel/playback',
            {'action':'start','mode':'flap','speed':1.0,'transition_seconds':0})
    rig=request('/scene/cetacean/rig/status?name=PetrelRigTest')
    print(json.dumps({'spawn':result,'rig':rig},indent=2),flush=True)
    request('/scene/camera/chase/start',{'target_name':'PetrelRigTest',
        'camera_name':'PetrelRigTestCamera','distance':1600,'height':300,
        'side_offset':200,'look_ahead':100,'look_height':80,
        'focal_length':24,'documentary_mode':False})
    request('/debug/viewport/capture',{})
    time.sleep(2)
    capture=request('/debug/viewport/capture',{})
    shutil.copy2(capture['file_path'],ASSET/f'working/kit_{pose}.png')
    print('Saved Kit capture for',pose,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pose',choices=['animation','glide','wings_up','wings_down','bank_left','bank_right'],default='animation')
    preview(parser.parse_args().pose)
