"""Capture bounded on/off pilot pairs through the existing MARLIN viewport API."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import time
import urllib.request
from PIL import Image, ImageChops, ImageStat
ROOT=Path(__file__).resolve().parents[3]
EXP=ROOT/'experiments/gsd_pilot_v1'
OUT=EXP/'renders/milestone_4'


def request(path,data=None,timeout=180):
    req=urllib.request.Request('http://localhost:8011'+path,
        data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=timeout) as result: value=json.load(result)
    if value.get('ok') is False:raise RuntimeError(path+': '+str(value)[:1500])
    return value


def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def image_difference(a,b):
    with Image.open(a) as first, Image.open(b) as second:
        if first.size != (1024,768) or second.size != first.size:
            raise ValueError('Viewport capture was not the declared 1024x768 image')
        difference=ImageChops.difference(first.convert('RGB'),second.convert('RGB'))
        return sum(ImageStat.Stat(difference).mean)/3


def settled_capture(folder):
    """Wait for stage/RTX accumulation to settle; retain every probe for audit."""
    probes=folder/'settling_probes';probes.mkdir(exist_ok=True)
    history=[];previous=None
    time.sleep(3)
    for attempt in range(1,8):
        result=request('/debug/viewport/capture',{},timeout=180)
        path=probes/('capture_%02d.png'%attempt)
        shutil.copy2(result['file_path'],path)
        difference=None if previous is None else image_difference(previous,path)
        history.append({'attempt':attempt,'sha256':sha(path),
                        'mean_absolute_rgb_difference_from_previous':difference})
        if difference is not None and difference < 1.0 and attempt >= 3:
            return path,history
        previous=path
        time.sleep(2)
    raise RuntimeError('RTX did not settle within seven captures; probes retained in '+str(probes))


def stop_controllers():
    for route in ('/scene/camera/chase/stop','/scene/cetaceans/gallery/swim/stop',
                  '/scene/cetacean/swim/stop','/scene/ocean/animation/stop'):
        request(route,{})
    playback=request('/scene/birds/petrel/playback')
    for player in playback.get('players',[]):request('/scene/birds/petrel/playback',{'name':player['name'],'action':'stop'})


def main(limit):
    entries=json.loads((OUT/'variant_index.json').read_text())
    progress=OUT/'capture_progress.json'
    results=json.loads(progress.read_text()) if progress.exists() else []
    complete={x['checkpoint_id'] for x in results}
    initial=OUT/'before_capture_checkpoint.json'
    if not initial.exists():save(initial,request('/debug/scene/checkpoint',{}))
    stop_controllers()
    remaining=[x for x in entries if x['checkpoint_id'] not in complete]
    if limit:remaining=remaining[:limit]
    for item in remaining:
        start=time.monotonic()
        request('/debug/scene/checkpoint/'+item['checkpoint_id']+'/restore',{},timeout=180)
        for route in ('/scene/ocean/animation/status','/scene/cetaceans/gallery/swim/status'):
            if request(route).get('running') is not False:raise RuntimeError('Controller advanced a frozen scene: '+route)
        folder=EXP/item['snapshot'].split('/scene.usdc')[0]
        src,settling=settled_capture(folder)
        image=folder/'rgb.png'
        shutil.copy2(src,image)
        # The root stage checkpoint records actual viewport/camera/settings,
        # independently of the source variant metadata.
        actual=request('/debug/scene/checkpoint',{},timeout=180)
        record={**item,'rgb_path':str(image.relative_to(EXP)),'rgb_sha256':sha(image),
                'actual_checkpoint':actual,'elapsed_seconds':time.monotonic()-start,
                'settling_probes':settling,'settling_threshold_mean_absolute_rgb':1.0}
        results.append(record);save(progress,results)
        print(item['scene_id'],item['requested_gsd_cm_px'],item['intervention'],'captured',flush=True)
    if len(results)==len(entries):save(OUT/'capture_complete.json',{'ok':True,'count':len(results),'progress':'capture_progress.json'})
    print(json.dumps({'complete':len(results),'total':len(entries)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int,default=0);args=parser.parse_args()
    main(args.limit)
