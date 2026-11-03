"""One controlled restart of the verified MARLIN Kit process after GPU guard blocks."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time

ROOT=Path(__file__).resolve().parents[5]
OUT=Path(__file__).resolve().parent/'kit_restart_01'
PID=2529697


def main():
    checkpoint=json.loads((OUT.parent/'pre_restart_checkpoint.json').read_text())
    assert checkpoint['ok']
    proc=Path('/proc')/str(PID)
    command=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode()
    assert '/kit/kit ' in command and '/apps/cris.madil.kit' in command,command
    OUT.mkdir(exist_ok=False)
    before=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,memory.free','--format=csv,noheader,nounits'],text=True)
    (OUT/'shutdown.json').write_text(json.dumps(dict(pid=PID,command=command,checkpoint_id=checkpoint['checkpoint_id'],gpu_before=before,reason='Repeated 768 MiB capture guard blocks after reference collection'),indent=2)+'\n')
    os.kill(PID,signal.SIGTERM)
    deadline=time.monotonic()+60
    while proc.exists():
        if (proc/'stat').read_text().split()[2]=='Z':break
        if time.monotonic()>deadline:raise RuntimeError('Kit did not exit gracefully; no duplicate launched')
        time.sleep(1)
    probe=subprocess.run(['pgrep','-af','(^|/)kit .*apps/cris.madil.kit'],capture_output=True,text=True)
    assert probe.returncode!=0,probe.stdout
    gpu=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,memory.free','--format=csv,noheader,nounits'],text=True)
    assert int(gpu.split(',')[1])>=2048,gpu
    work=ROOT/'_build/linux-x86_64/release'
    args=[str(work/'cris.madil.kit.sh'),'--enable','cris.madil.render_service',
          '--/log/file='+str(OUT/'kit_process.log')]
    with (OUT/'launch_stdout.log').open('x') as stream:
        child=subprocess.Popen(args,cwd=work,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
    record=dict(pid=child.pid,command=args,gpu_before_launch=gpu,restoration_pending=True)
    (OUT/'launch.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2),flush=True)


if __name__=='__main__':main()
