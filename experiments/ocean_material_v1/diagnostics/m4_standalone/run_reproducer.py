"""Portable entry point: a provided Kit SDK and the scene package are sufficient."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

root=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--sdk',type=Path,required=True,help='Kit SDK directory containing the kit executable')
parser.add_argument('--output',type=Path,required=True,help='New output directory; never overwritten')
parser.add_argument('--suite',choices=['initial','all'],default='initial')
parser.add_argument('--profile',type=Path,help='Private test profile, optionally reused after precache')
parser.add_argument('--precache-only',action='store_true',help='Download native dependencies without rendering')
args=parser.parse_args()
sdk=args.sdk.resolve();output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
memory=subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True)
if int(memory.splitlines()[0])<2048:raise RuntimeError('Require 2048 MiB free before renderer startup')
private=(args.profile or output/'private_profile').resolve();env=os.environ.copy()
for key,child in [('XDG_CACHE_HOME','xdg_cache'),('XDG_CONFIG_HOME','xdg_config'),('XDG_DATA_HOME','xdg_data'),('CUDA_CACHE_PATH','cuda_cache'),('__GL_SHADER_DISK_CACHE_PATH','gl_cache')]:
    p=private/child;p.mkdir(parents=True,exist_ok=True);env[key]=str(p)
env.update(WATER_REPRO_ROOT=str(root),WATER_REPRO_OUTPUT=str(output),WATER_REPRO_SUITE=args.suite,
           WATER_REPRO_SDK=str(sdk),PYTHONDONTWRITEBYTECODE='1')
command=[str(sdk/'kit'),str(root/'standalone.kit'),'--portable-root',str(private/'portable'),'--no-window',
         '--/rtx-transient/resourcemanager/localTextureCachePath='+str(private/'texture_cache'),
         '--/log/file='+str(output/'kit_process.log')]
command+=['--ext-precache-mode'] if args.precache_only else ['--exec',str(root/'capture_in_kit.py')]
(output/'command.json').write_text(json.dumps(command,indent=2)+'\n')
print('A first-start informational IOMMU notice may require acknowledgement; its text remains in the log.',flush=True)
started=time.monotonic()
result=subprocess.run(command,cwd=sdk,env=env,timeout=900 if args.precache_only else 540)
(output/'exit.json').write_text(json.dumps({'exit_code':result.returncode,'elapsed_seconds':time.monotonic()-started},indent=2)+'\n')
raise SystemExit(result.returncode)
