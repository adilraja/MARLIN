"""Run a fresh, bounded MARLIN process for persisted preset capture/rollback."""
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[3]
OUT=ROOT/'qa/reload_launch_01'


def write(path,data):
    path.write_text(json.dumps(data,indent=2)+'\n')


def gpu():
    row=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,memory.free,driver_version','--format=csv,noheader,nounits'],text=True,timeout=10).strip().split(',')
    return dict(used_mib=int(row[0]),free_mib=int(row[1]),driver=row[2].strip())


def main():
    OUT.mkdir(exist_ok=False)
    check=subprocess.run(['pgrep','-af','(^|/)(kit|cris.madil.kit.sh)( |$)'],capture_output=True,text=True)
    assert check.returncode==1,check.stdout
    before=gpu()
    assert before['free_mib']>=2048 and before['driver']=='595.99.02'
    script=ROOT/'qa/reload_in_kit.py'
    compile(script.read_text(),str(script),'exec')
    work=REPO/'_build/linux-x86_64/release'
    command=[str(work/'cris.madil.kit.sh'),'--enable','cris.madil.render_service','--exec',str(script),'--/log/file='+str(OUT/'kit_process.log')]
    with (OUT/'stdout.log').open('x') as stream:
        process=subprocess.Popen(command,cwd=work,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
    write(OUT/'launch.json',dict(pid=process.pid,command=command,gpu_before=before,script_sha256=hashlib.sha256(script.read_bytes()).hexdigest()))
    print(json.dumps(dict(pid=process.pid,gpu_before=before)),flush=True)
    started=time.monotonic()
    samples=[]
    while process.poll() is None and time.monotonic()-started<240:
        try:
            samples.append(dict(elapsed_seconds=time.monotonic()-started,**gpu()))
        except Exception as exc:
            samples.append(dict(elapsed_seconds=time.monotonic()-started,error=str(exc)))
        write(OUT/'gpu_samples.json',samples)
        time.sleep(1)
    if process.poll() is None:
        process.terminate()
        process.wait(timeout=30)
        raise RuntimeError('Fresh reload process exceeded 240 seconds')
    write(OUT/'exit.json',dict(returncode=process.returncode,elapsed_seconds=time.monotonic()-started,
          peak_used_mib=max(x['used_mib'] for x in samples if 'used_mib' in x),minimum_free_mib=min(x['free_mib'] for x in samples if 'free_mib' in x)))
    done=ROOT/'runs/reload_process01/done.json'
    if not done.exists():
        raise RuntimeError('Fresh reload did not complete; failure evidence preserved')
    print(done.read_text(),flush=True)


if __name__=='__main__':
    main()
