"""Reopen the standard MARLIN scene after the fresh-process capture test."""
import json
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[3]
OUT=ROOT/'qa/live_restore'


def main():
    OUT.mkdir(exist_ok=False)
    assert (ROOT/'runs/reload_process01/done.json').exists()
    p=subprocess.run(['pgrep','-af','(^|/)(kit|cris.madil.kit.sh)( |$)'],capture_output=True,text=True)
    assert p.returncode==1,p.stdout
    free=int(subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).strip())
    assert free>=2048
    work=REPO/'_build/linux-x86_64/release'
    args=[str(work/'cris.madil.kit.sh'),'--enable','cris.madil.render_service','--exec',str(ROOT/'qa/restore_live_in_kit.py'),'--/log/file='+str(OUT/'kit_process.log')]
    with (OUT/'stdout.log').open('x') as stream:
        process=subprocess.Popen(args,cwd=work,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
    (OUT/'launch.json').write_text(json.dumps(dict(pid=process.pid,command=args,gpu_free_before_mib=free),indent=2)+'\n')
    print('Restoring MARLIN, pid',process.pid,flush=True)
    deadline=time.monotonic()+150
    while time.monotonic()<deadline:
        if (OUT/'done.json').exists():
            print((OUT/'done.json').read_text(),flush=True)
            return
        if (OUT/'failure.json').exists():
            raise RuntimeError((OUT/'failure.json').read_text())
        if process.poll() is not None:
            raise RuntimeError('Restore process exited; original checkpoint remains intact')
        time.sleep(1)
    raise RuntimeError('Bounded restore timed out; MARLIN retained for inspection')


if __name__=='__main__':
    main()
