"""Reopen the unchanged documented MARLIN app and restore its approved checkpoint."""
import hashlib
import json
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[3]


def post(path, payload):
    request=urllib.request.Request('http://localhost:8011'+path,data=json.dumps(payload).encode(),
                                   headers={'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(request,timeout=40) as response:return json.load(response)


def main():
    qa=ROOT/'qa'
    checkpoint=json.loads((qa/'pre_close_checkpoint.json').read_text())
    assert hashlib.sha256((Path(checkpoint['directory'])/'scene.usdc').read_bytes()).hexdigest()==checkpoint['scene_sha256']
    for entry in json.loads((qa/'marlin_source_before.json').read_text()):
        assert hashlib.sha256((REPO/entry['path']).read_bytes()).hexdigest()==entry['sha256'],entry['path']
    try:
        urllib.request.urlopen('http://localhost:8011/docs',timeout=2).close()
        raise RuntimeError('MARLIN service already running; refusing a duplicate or implicit scene overwrite')
    except urllib.error.URLError:pass
    memory=subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True)
    if int(memory.splitlines()[0])<2048:raise RuntimeError('Insufficient headroom to reopen MARLIN safely')
    output=ROOT/'runs/marlin_restore';output.mkdir(parents=True,exist_ok=False)
    work=REPO/'_build/linux-x86_64/release'
    command=[str(work/'cris.madil.kit.sh'),'--enable','cris.madil.render_service','--/log/file='+str(output/'kit_process.log')]
    with (output/'stdout.log').open('x') as stream:
        process=subprocess.Popen(command,cwd=work,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
    (output/'launch.json').write_text(json.dumps({'pid':process.pid,'command':command,'gpu_free_before_mib':int(memory.splitlines()[0])},indent=2)+'\n')
    deadline=time.monotonic()+90
    while True:
        try:
            urllib.request.urlopen('http://localhost:8011/docs',timeout=2).close();break
        except urllib.error.URLError:
            if time.monotonic()>deadline:raise RuntimeError('MARLIN did not become ready; launched process retained for inspection')
            time.sleep(1)
    restored=post('/debug/scene/checkpoint/'+checkpoint['checkpoint_id']+'/restore',{})
    (qa/'marlin_restore_checkpoint.json').write_text(json.dumps(restored,indent=2)+'\n');assert restored['ok']
    # Pre-close status recorded the existing standard marine scene: active
    # ocean/chase, inactive swimming. Rebuild those controllers with the same
    # standard setup. Checkpoint format does not serialize procedural phase.
    setup=post('/scene/marine/setup',{'start_swimming':False})
    (qa/'marlin_restore_live.json').write_text(json.dumps(setup,indent=2)+'\n');assert setup['ok']
    final=post('/debug/scene/checkpoint',{})
    (qa/'marlin_checkpoint_after.json').write_text(json.dumps(final,indent=2)+'\n');assert final['ok']
    checks={key+'_restored':checkpoint[key]==final[key] for key in ('camera','resolution','fill_frame','renderer_settings','display_options')}
    checks.update(renderer_setting_count=len(checkpoint['renderer_settings']),
                  procedural_phase='Reconstructed after the explicitly approved temporary process closure')
    (qa/'marlin_restoration_validation.json').write_text(json.dumps(checks,indent=2)+'\n')
    assert all(value for key,value in checks.items() if key.endswith('_restored'))
    print(json.dumps(checks,indent=2),flush=True)


if __name__=='__main__':main()
