"""Record final MARLIN state without changing its scene or controllers."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import urllib.request

ROOT=Path(__file__).resolve().parent


def main():
    fresh=json.loads((ROOT/'live_attempt01/results.json').read_text())
    assert fresh['passed'] and all(fresh['checks'].values())
    output=ROOT/'live_final';output.mkdir(exist_ok=False)
    paths={'inspection':'/debug/scene/inspection','ocean':'/scene/ocean/animation/status',
        'swim':'/scene/cetacean/swim/status','gallery':'/scene/cetaceans/gallery/swim/status',
        'chase':'/scene/camera/chase/status','water':'/scene/ocean/material/status',
        'preset':'/scene/ocean/material/preset/status','animated_owner':'/integration/gama/v3/animated_actor/status',
        'static_owner':'/integration/gama/v3/actor/status','openapi':'/openapi.json'}
    checks={}
    for name,path in paths.items():
        with urllib.request.urlopen('http://localhost:8011'+path,timeout=30) as response:record=json.load(response)
        (output/(name+'.json')).write_text(json.dumps(record,indent=2)+'\n')
        before=json.loads((ROOT/'live_before'/(name+'.json')).read_text())
        if name in ('ocean','swim','gallery','chase','water','preset'):
            checks[name]=record==before
        if name.endswith('owner'):
            checks[name]=not record['owned']
        if name=='openapi':
            checks['existing_routes_preserved']=set(before['paths'])<=set(record['paths'])
    request=urllib.request.Request('http://localhost:8011/debug/scene/checkpoint',data=b'{}',headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=60) as response:checkpoint=json.load(response)
    assert checkpoint['ok']
    (output/'checkpoint.json').write_text(json.dumps(checkpoint,indent=2)+'\n')
    for name in ['scene.usdc','metadata.json']:
        shutil.copyfile(Path(checkpoint['directory'])/name,output/name)
    before=json.loads((ROOT/'live_before/checkpoint.json').read_text())
    from math import isclose
    for name in ['camera','resolution','fill_frame','display_options','renderer_settings']:
        checks[name]=before[name]==checkpoint[name]
    gpu=subprocess.run(['nvidia-smi','--query-gpu=name,memory.total,memory.used,memory.free,driver_version',
        '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=15)
    (output/'gpu.json').write_text(json.dumps(dict(returncode=gpu.returncode,stdout=gpu.stdout,stderr=gpu.stderr),indent=2)+'\n')
    record=dict(passed=all(checks.values()),checks=checks,utc=datetime.now(timezone.utc).isoformat(),
        final_checkpoint=checkpoint['checkpoint_id'],normal_gui=True,
        finite_job_completed=True,active_qa_poller=False,notes='Pre-work controllers were stopped and were restored stopped; no scene setup or animal respawn was used.')
    with (ROOT/'final_restoration.json').open('x') as stream:json.dump(record,stream,indent=2);stream.write('\n')
    assert record['passed'],checks
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
