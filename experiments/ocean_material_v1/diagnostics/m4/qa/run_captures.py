"""Run the declared M4 integration views sequentially; preserve every attempt."""
import json
from pathlib import Path
import subprocess
import threading
import time
from urllib.request import Request,urlopen
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]


def main():
    log=ROOT/'qa/capture_execution.json'
    if log.exists():raise RuntimeError('Preserve the existing execution log')
    cases=[dict(selection=s,view=v,phase_seconds=0) for s in ('original','engineering_v1') for v in ('nadir','oblique')]
    cases += [dict(selection='engineering_v1',view='oblique',phase_seconds=p) for p in (.5,1,2,4)]
    cases += [dict(selection='engineering_v1',view=v,phase_seconds=1) for v in ('inside','exit','edge')]
    cases += [dict(selection='engineering_v1',view='oblique',phase_seconds=0,advance_live=True)]
    samples=[];rows=[];stop=threading.Event()
    def sample():
        while not stop.is_set():
            r=subprocess.run(['nvidia-smi','--query-gpu=timestamp,memory.used,memory.free','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5)
            samples.append(dict(monotonic=time.monotonic(),returncode=r.returncode,observation=r.stdout.strip(),error=r.stderr.strip()))
            stop.wait(1)
    thread=threading.Thread(target=sample);thread.start()
    try:
        for payload in cases:
            started=time.monotonic()
            req=Request('http://localhost:8011/scene/ocean/material/preset/diagnostic/capture',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
            with urlopen(req,timeout=105) as response:result=json.load(response)
            row=dict(request=payload,response=result,elapsed_seconds=time.monotonic()-started);rows.append(row)
            log.write_text(json.dumps(rows,indent=2)+'\n')
            if not result.get('ok'):raise RuntimeError(json.dumps(result))
            d=Path(result['directory']);deadline=time.monotonic()+10
            while True:
                try:
                    with Image.open(d/'rgb.png') as im:
                        assert im.size==(512,384);im.verify()
                    assert (d/'hdr.npz').stat().st_size>100
                    break
                except (FileNotFoundError,OSError):
                    if time.monotonic()>=deadline:raise
                    time.sleep(.1)
            print(json.dumps(dict(request=payload,seconds=row['elapsed_seconds'],directory=result['directory'])),flush=True)
    finally:
        stop.set();thread.join(timeout=6)
        (ROOT/'qa/capture_gpu.json').write_text(json.dumps(samples,indent=2)+'\n')


if __name__=='__main__':main()
