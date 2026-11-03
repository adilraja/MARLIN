"""Exercise the existing live ocean capture on the new driver, then restore."""
import json
from pathlib import Path
import shutil
import subprocess
import threading
import time
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[1]


def api(path,payload=None):
    request=Request('http://localhost:8011'+path,data=json.dumps(payload).encode() if payload is not None else None,
                    headers={'Content-Type':'application/json'})
    with urlopen(request,timeout=105) as response:
        return json.load(response)


def main():
    out=ROOT/'qa/live_animation'
    out.mkdir(exist_ok=False)
    before={path:api(path) for path in ('/scene/camera/chase/status','/scene/ocean/animation/status','/scene/cetacean/swim/status')}
    (out/'before.json').write_text(json.dumps(before,indent=2)+'\n')
    assert not before['/scene/cetacean/swim/status']['running']
    stopped=api('/scene/camera/chase/stop',{})
    (out/'chase_stopped.json').write_text(json.dumps(stopped,indent=2)+'\n')
    stop=threading.Event()
    samples=[]
    def monitor():
        while not stop.is_set():
            value=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,memory.free','--format=csv,noheader,nounits'],text=True,timeout=10)
            a,b=value.strip().split(',')
            samples.append(dict(monotonic=time.monotonic(),used_mib=int(a),free_mib=int(b)))
            stop.wait(1)
    thread=threading.Thread(target=monitor)
    thread.start()
    try:
        started=time.monotonic()
        payload=dict(selection='engineering_v1',view='oblique',phase_seconds=0,advance_live=True)
        result=api('/scene/ocean/material/preset/diagnostic/capture',payload)
        (out/'call.json').write_text(json.dumps(dict(request=payload,response=result,elapsed_seconds=time.monotonic()-started),indent=2)+'\n')
        assert result['ok'],result
        source=Path(result['directory'])
        assert source.parent.name=='captures' and source.parent.parent.name=='m4'
        target=ROOT/'runs/current_driver_animated_ocean'
        assert not target.exists()
        shutil.move(str(source),str(target))
        frames=result['metadata']['live_frames']
        assert len(frames)==10 and len({frame['elapsed'] for frame in frames})>1
        assert all('OceanWaterEngineeringV1' in frame['binding'] for frame in frames)
        restoration=json.loads((target/'restoration.json').read_text())
        assert all(restoration['ocean_root_attributes_restored'].values())
        assert all(v for k,v in restoration.items() if k!='ocean_root_attributes_restored')
        (out/'verification.json').write_text(json.dumps(dict(actual_live_updates=len(frames),
            phase_advanced=True,engineering_binding_retained=True,restoration=restoration,adopted_directory=str(target)),indent=2)+'\n')
        print('Current-driver live ocean capture and cleanup passed.',flush=True)
    finally:
        stop.set()
        thread.join(timeout=12)
        (out/'gpu_samples.json').write_text(json.dumps(samples,indent=2)+'\n')
        setup=api('/scene/marine/setup',{'start_swimming':False})
        (out/'standard_scene_restored.json').write_text(json.dumps(setup,indent=2)+'\n')
        assert setup['ok']


if __name__=='__main__':
    main()
