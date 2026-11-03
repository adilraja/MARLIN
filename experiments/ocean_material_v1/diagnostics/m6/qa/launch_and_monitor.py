"""Reopen unchanged MARLIN after the isolated retest, then monitor the M6 audit."""
import hashlib
import json
from pathlib import Path
import subprocess
import time
from urllib.error import URLError
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[3]
RUN=ROOT/'runs/attempt01'
OUT=ROOT/'qa/launch_01'


def write(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n')


def gpu():
    text=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,memory.used,memory.free,driver_version','--format=csv,noheader,nounits'],text=True,timeout=10)
    v=[x.strip() for x in text.strip().split(',')]
    return dict(name=v[0],total_mib=int(v[1]),used_mib=int(v[2]),free_mib=int(v[3]),driver=v[4])


def main():
    OUT.mkdir(exist_ok=False)
    for item in json.loads((ROOT/'qa/source_before.json').read_text()):
        assert hashlib.sha256((REPO/item['path']).read_bytes()).hexdigest()==item['sha256']
    try:
        urlopen('http://localhost:8011/docs',timeout=2).close()
        raise RuntimeError('MARLIN already running; refusing duplicate')
    except URLError:
        pass
    p=subprocess.run(['pgrep','-af','(^|/)(kit|cris.madil.kit.sh)( |$)'],capture_output=True,text=True)
    assert p.returncode==1,p.stdout
    before=gpu()
    assert before['driver']=='595.99.02' and before['free_mib']>=2048
    for path in (ROOT/'qa').glob('*.py'):
        compile(path.read_text(),str(path),'exec')
    write(OUT/'source_pins.json',{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
          for path in (ROOT/'qa').glob('*.py')})
    work=REPO/'_build/linux-x86_64/release'
    args=[str(work/'cris.madil.kit.sh'),'--enable','cris.madil.render_service','--exec',str(ROOT/'qa/audit_in_kit.py'),
          '--/log/file='+str(OUT/'kit_process.log')]
    with (OUT/'stdout.log').open('x') as stream:
        process=subprocess.Popen(args,cwd=work,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
    started=time.monotonic()
    write(OUT/'launch.json',dict(pid=process.pid,command=args,gpu_before=before,monotonic=started))
    print(json.dumps(dict(pid=process.pid,gpu_before=before)),flush=True)
    samples=[]
    while time.monotonic()-started<540:
        try:
            samples.append(dict(elapsed_seconds=time.monotonic()-started,**gpu()))
        except Exception as exc:
            samples.append(dict(elapsed_seconds=time.monotonic()-started,error=str(exc)))
        write(OUT/'gpu_samples.json',samples)
        if (RUN/'done.json').exists() or (RUN/'audit_failure.json').exists():
            break
        if process.poll() is not None:
            raise RuntimeError('MARLIN exited unexpectedly')
        time.sleep(1)
    else:
        write(OUT/'monitor_timeout.json',dict(error='540 second audit monitor bound reached; MARLIN retained for inspection'))
        return
    result=json.loads((RUN/('done.json' if (RUN/'done.json').exists() else 'audit_failure.json')).read_text())
    write(OUT/'result.json',dict(result=result,peak_observed_used_mib=max(x['used_mib'] for x in samples if 'used_mib' in x),
          minimum_observed_free_mib=min(x['free_mib'] for x in samples if 'free_mib' in x),sample_count=len(samples),
          scope='Approx. one-second samples, app startup through audit completion; not exact allocation peak'))
    print(json.dumps({k:v for k,v in result.items() if k!='traceback'},indent=2),flush=True)


if __name__=='__main__':
    main()
