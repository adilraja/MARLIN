"""Resume the 280 new M5 captures through MARLIN's existing Kit HTTP API."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time
sys.dont_write_bytecode=True

ROOT=Path(__file__).resolve().parents[3]
EXP=ROOT/'experiments/gsd_pilot_v1'
OUT=EXP/'renders/milestone_5'
sys.path.insert(0,str(EXP/'qa'))
from m4_capture import request,stop_controllers,image_difference,sha,save


def settled_capture():
    """Keep probe hashes and deltas; materialize only accepted RGB in dataset."""
    previous=None;history=[]
    time.sleep(3)
    for attempt in range(1,8):
        result=request('/debug/viewport/capture',{},timeout=180)
        probe=Path('/tmp/marlin_m5_probe_%s.png'%('a' if attempt%2 else 'b'))
        shutil.copy2(result['file_path'],probe)
        difference=None if previous is None else image_difference(previous,probe)
        history.append({'attempt':attempt,'sha256':sha(probe),
                        'mean_absolute_rgb_difference_from_previous':difference})
        if difference is not None and difference<1.0 and attempt>=3:return probe,history
        previous=probe
        time.sleep(2)
    raise RuntimeError('RTX did not settle within seven captures')


def capture(limit):
    items=json.loads((OUT/'variant_index.json').read_text())
    todo=[x for x in items if x['capture_source']=='milestone_5_new']
    progress=OUT/'capture_progress.json'
    results=json.loads(progress.read_text()) if progress.exists() else []
    completed={x['checkpoint_id'] for x in results}
    if len(results)!=len(completed):raise ValueError('Duplicate captured checkpoint')
    todo=[x for x in todo if x['checkpoint_id'] not in completed]
    if limit:todo=todo[:limit]
    if not todo:
        print(json.dumps({'new_captures':len(results),'reused_m4':10,
                          'total_expected':300,'already_complete':True}),flush=True)
        return
    first=OUT/'before_capture_checkpoint.json'
    if not first.exists():save(first,request('/debug/scene/checkpoint',{}))
    stop_controllers()
    for item in todo:
        start=time.monotonic()
        key=item['checkpoint_id']
        request('/debug/scene/checkpoint/'+key+'/restore',{},timeout=180)
        for route in ('/scene/ocean/animation/status','/scene/cetaceans/gallery/swim/status'):
            if request(route).get('running') is not False:raise RuntimeError('Live controller advanced static dataset scene')
        probe,settling=settled_capture()
        folder=OUT/item['scene_id']/('gsd_'+('%.1f'%item['requested_gsd_cm_px']).replace('.','p'))/item['intervention']
        folder.mkdir(parents=True,exist_ok=True)
        image=folder/'rgb.png'
        shutil.copy2(probe,image)
        actual=request('/debug/scene/checkpoint',{},timeout=180)
        result={**item,'rgb_path':str(image.relative_to(EXP)),
                'rgb_sha256':sha(image),'actual_checkpoint':actual,
                'settling_probes':settling,'settling_threshold_mean_absolute_rgb':1.0,
                'elapsed_seconds':time.monotonic()-start}
        results.append(result);save(progress,results)
        print(item['scene_id'],item['requested_gsd_cm_px'],item['intervention'],
              'captured',len(results),'/',280,flush=True)
    if len(results)==280:
        save(OUT/'capture_complete.json',{'ok':True,'new_captures':280,'reused_m4':10,'total_images':300})
    print(json.dumps({'new_captures':len(results),'reused_m4':10,'total_expected':300}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int,default=0)
    capture(parser.parse_args().limit)
