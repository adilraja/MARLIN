"""Launch only experiment-owned SDKs with portable settings and private caches."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[3]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('version', choices=['baseline','candidate'])
    parser.add_argument('--mode', choices=['precache','render','validate','extract','emitter'], default='render')
    parser.add_argument('--suite', choices=['initial','all','dry'], default='initial')
    parser.add_argument('--attempt', default='01')
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9]{2}', args.attempt):
        raise ValueError('Use a two-digit attempt identifier')
    for entry in json.loads((ROOT/'qa/marlin_source_before.json').read_text()):
        assert hashlib.sha256((REPO/entry['path']).read_bytes()).hexdigest() == entry['sha256'], entry['path']
    sdk = ROOT/'work'/('sdk-1102' if args.version=='baseline' else 'sdk-candidate')
    assert sdk.resolve().is_relative_to((ROOT/'work').resolve())
    output = ROOT/'runs'/f'{args.version}_{args.mode}_{args.attempt}'
    output.mkdir(parents=True,exist_ok=False)
    gpu = subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,memory.used,memory.free,driver_version','--format=csv,noheader,nounits'],text=True)
    if args.mode=='render' and int(gpu.splitlines()[0].split(',')[3])<2048:
        record={'ok':False,'render_attempted':False,'reason':'2048 MiB isolated renderer startup guard','gpu':gpu}
        (output/'launch.json').write_text(json.dumps(record,indent=2)+'\n')
        print(json.dumps(record,indent=2));return
    private = ROOT/'work'/('profile_'+args.version)
    env = os.environ.copy()
    for key,child in [('XDG_CACHE_HOME','xdg_cache'),('XDG_CONFIG_HOME','xdg_config'),('XDG_DATA_HOME','xdg_data'),('CUDA_CACHE_PATH','cuda_cache'),('__GL_SHADER_DISK_CACHE_PATH','gl_cache')]:
        folder=private/child;folder.mkdir(parents=True,exist_ok=True);env[key]=str(folder)
    env.update(PYTHONDONTWRITEBYTECODE='1',WATER_REPRO_ROOT=str(ROOT),WATER_REPRO_OUTPUT=str(output),
               WATER_REPRO_SUITE=args.suite,WATER_REPRO_SDK=str(sdk.resolve()))
    app = ROOT/('validate.kit' if args.mode in ('validate','extract','emitter') else 'standalone.kit')
    command=[str(sdk/'kit'),str(app),'--portable-root',str(private/'portable'),'--no-window',
             '--/rtx-transient/resourcemanager/localTextureCachePath='+str(private/'texture_cache'),
             '--/log/file='+str(output/'kit_process.log')]
    if args.mode=='precache':command+=['--ext-precache-mode']
    else:command+=['--exec',str(ROOT/('native_emitter_in_kit.py' if args.mode=='emitter' else 'extract_reproducer_in_kit.py' if args.mode=='extract' else 'validate_in_kit.py' if args.mode=='validate' else 'capture_in_kit.py'))]
    started=time.monotonic()
    stop_monitor=threading.Event()
    def monitor():
        with (output/'gpu_samples.jsonl').open('x') as stream:
            while not stop_monitor.is_set():
                try:
                    sample=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,memory.free','--format=csv,noheader,nounits'],text=True,timeout=5).strip().split(',')
                    stream.write(json.dumps({'elapsed_seconds':time.monotonic()-started,'used_mib':int(sample[0]),'free_mib':int(sample[1])})+'\n');stream.flush()
                except (subprocess.SubprocessError,ValueError):pass
                stop_monitor.wait(1)
    monitor_thread=None
    if args.mode=='render':
        monitor_thread=threading.Thread(target=monitor,daemon=True);monitor_thread.start()
    with (output/'stdout.log').open('x') as stream:
        process=subprocess.Popen(command,cwd=sdk,env=env,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        (output/'launch.json').write_text(json.dumps({'pid':process.pid,'command':command,'gpu_before':gpu,'mode':args.mode,'suite':args.suite,'private_profile':str(private)},indent=2)+'\n')
        print(json.dumps({'pid':process.pid,'output':str(output),'mode':args.mode}),flush=True)
        try:code=process.wait(timeout=900 if args.mode=='precache' else 480)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:process.wait(timeout=30)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=10)
            code=124
    stop_monitor.set()
    if monitor_thread:monitor_thread.join(timeout=6)
    (output/'exit.json').write_text(json.dumps({'exit_code':code,'elapsed_seconds':time.monotonic()-started},indent=2)+'\n')
    print(json.dumps({'exit_code':code,'output':str(output)}),flush=True)


if __name__=='__main__':
    main()
