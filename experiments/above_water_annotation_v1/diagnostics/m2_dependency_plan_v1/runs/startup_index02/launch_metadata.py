"""Bounded metadata lookup with an unwritable installation destination."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]
REPO = BASE.parents[1]
RUNTIME = REPO/'_build/linux-x86_64/release'


def write(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n')


def run(label):
    assert label.replace('_','').isalnum() and len(label)<48
    other = subprocess.run(['ps','-C','kit','-o','pid=,args='],capture_output=True,text=True,timeout=10)
    assert other.returncode in (0,1) and not other.stdout.strip(), 'An existing Kit must remain untouched'
    assert shutil.disk_usage(REPO).free > 10*1024**3
    out = BASE/'diagnostics/m2_dependency_plan_v1/runs'/label
    out.mkdir(parents=True,exist_ok=False)
    profile = Path('/tmp')/('marlin_annotation_dependencies_'+label)
    profile.mkdir(exist_ok=False)
    forbidden = profile/'content_installation_forbidden'
    forbidden.mkdir(mode=0o500)
    assert not os.access(forbidden,os.W_OK), 'This query requires an unwritable installation destination'
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE='1',ANNOTATION_DEPENDENCY_OUTPUT=str(out),
               ANNOTATION_CONTENT_FORBIDDEN=str(forbidden))
    for key,child in [('XDG_CACHE_HOME','xdg_cache'),('XDG_CONFIG_HOME','xdg_config'),
                      ('XDG_DATA_HOME','xdg_data'),('CUDA_CACHE_PATH','cuda_cache'),
                      ('__GL_SHADER_DISK_CACHE_PATH','gl_cache')]:
        env[key] = str(profile/child)
    for filename in ('metadata.kit','query_metadata.py','launch_metadata.py'):
        shutil.copyfile(HERE/filename,out/filename)
    args=[str(RUNTIME/'kit/kit'),str(out/'metadata.kit'),
          '--ext-folder',str(RUNTIME/'exts'),'--ext-folder',str(RUNTIME/'extscache'),
          '--no-window','--portable','--portable-root='+str(profile/'portable'),
          '--/app/extensions/registryEnabled=true','--/app/extensions/syncRegistryOnStartup=false',
          '--/app/extensions/registryCache='+str(forbidden),
          '--/log/file='+str(out/'kit_process.log'),'--exec',str(out/'query_metadata.py')]
    start=time.monotonic()
    with (out/'stdout.log').open('x') as stream:
        process=subprocess.Popen(args,cwd=REPO,env=env,stdin=subprocess.DEVNULL,
                                 stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
    write(out/'launch.json',dict(recorded_utc=datetime.now(timezone.utc).isoformat(),pid=process.pid,
          command=args,profile=str(profile),installation_destination=str(forbidden),
          installation_destination_writable=False,existing_kit_before='',
          source_sha256={f:hashlib.sha256((out/f).read_bytes()).hexdigest()
                         for f in ('metadata.kit','query_metadata.py','launch_metadata.py')}))
    print('Started metadata-only probe',label,'PID',process.pid,flush=True)
    signals=[];reason=None;quit_seen=None
    while process.poll() is None:
        elapsed=time.monotonic()-start
        if (out/'query.json').exists() and quit_seen is None:quit_seen=time.monotonic()
        if elapsed>120 and quit_seen is None:reason='120-second metadata deadline exceeded'
        if quit_seen is not None and time.monotonic()-quit_seen>30:reason='30-second normal-exit deadline exceeded'
        if reason:
            os.killpg(process.pid,signal.SIGTERM);signals.append('SIGTERM owned process group')
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL);signals.append('SIGKILL owned process group');process.wait(timeout=10)
            break
        time.sleep(1)
    query=json.loads((out/'query.json').read_text()) if (out/'query.json').exists() else None
    result=dict(returncode=process.returncode,elapsed_seconds=time.monotonic()-start,
                termination_reason=reason,cleanup_signals=signals,query_returned=query is not None,
                clean_exit=bool(query and query['passed'] and process.returncode==0 and not signals),
                installation_destination_empty=not any(forbidden.iterdir()))
    write(out/'exit.json',result);print(json.dumps(result),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('label');run(parser.parse_args().label)
