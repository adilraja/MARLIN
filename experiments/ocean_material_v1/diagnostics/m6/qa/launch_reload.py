"""Run a fresh, bounded MARLIN process for persisted preset capture/rollback."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[3]


def write(path,data):
    path.write_text(json.dumps(data,indent=2)+'\n')


def gpu():
    row=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,memory.free,driver_version','--format=csv,noheader,nounits'],text=True,timeout=10).strip().split(',')
    return dict(used_mib=int(row[0]),free_mib=int(row[1]),driver=row[2].strip())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt',default='01',help='New two-digit evidence identifier; existing outputs are never overwritten')
    args=parser.parse_args()
    if len(args.attempt)!=2 or not args.attempt.isdigit():
        raise ValueError('Use a two-digit attempt identifier')
    out=ROOT/'qa'/('reload_launch_'+args.attempt)
    capture_output=ROOT/'runs'/('reload_process'+args.attempt)
    global OUT
    OUT=out
    OUT.mkdir(exist_ok=False)
    assert not capture_output.exists(),'Preserve existing captures'
    check=subprocess.run(['pgrep','-af','(^|/)(kit|cris.madil.kit.sh)( |$)'],capture_output=True,text=True)
    assert check.returncode==1,check.stdout
    before=gpu()
    assert before['free_mib']>=2048 and before['driver']=='595.99.02'
    script=ROOT/'qa/reload_in_kit.py'
    compile(script.read_text(),str(script),'exec')
    work=REPO/'_build/linux-x86_64/release'
    command=[str(work/'cris.madil.kit.sh'),'--enable','cris.madil.render_service','--exec',str(script),'--/log/file='+str(OUT/'kit_process.log')]
    with (OUT/'stdout.log').open('x') as stream:
        process=subprocess.Popen(command,cwd=work,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True,
                                 env=dict(os.environ,MARLIN_M6_REPLAY_OUTPUT=str(capture_output)))
    write(OUT/'launch.json',dict(pid=process.pid,command=command,gpu_before=before,script_sha256=hashlib.sha256(script.read_bytes()).hexdigest()))
    print(json.dumps(dict(pid=process.pid,gpu_before=before)),flush=True)
    started=time.monotonic()
    samples=[]
    finished_at=None
    done=capture_output/'done.json'
    while process.poll() is None and time.monotonic()-started<240:
        try:
            samples.append(dict(elapsed_seconds=time.monotonic()-started,**gpu()))
        except Exception as exc:
            samples.append(dict(elapsed_seconds=time.monotonic()-started,error=str(exc)))
        write(OUT/'gpu_samples.json',samples)
        if done.exists():
            if finished_at is None:
                finished_at=time.monotonic()
            elif time.monotonic()-finished_at>10:
                write(OUT/'post_result_termination.json',dict(pid=process.pid,signal='SIGTERM',
                      reason='Captures saved; posted quit did not exit within ten seconds'))
                process.terminate()
                process.wait(timeout=30)
                break
        time.sleep(1)
    if process.poll() is None:
        process.terminate()
        process.wait(timeout=30)
        raise RuntimeError('Fresh reload process exceeded 240 seconds')
    write(OUT/'exit.json',dict(returncode=process.returncode,elapsed_seconds=time.monotonic()-started,
          peak_used_mib=max(x['used_mib'] for x in samples if 'used_mib' in x),minimum_free_mib=min(x['free_mib'] for x in samples if 'free_mib' in x)))
    if not done.exists():
        raise RuntimeError('Fresh reload did not complete; failure evidence preserved')
    print(done.read_text(),flush=True)


if __name__=='__main__':
    main()
