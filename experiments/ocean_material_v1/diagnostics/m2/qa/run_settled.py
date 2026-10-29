"""Run the six predeclared existing-Kit diagnostic requests once."""
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def main():
    log = ROOT/'qa/settled_execution.json'
    if log.exists():
        raise RuntimeError('Preserve the previous execution; do not overwrite it')
    results=[]
    for view in ('nadir', 'oblique'):
        for condition in ('dry', 'matched', 'water'):
            started=time.monotonic()
            request=Request('http://localhost:8011/scene/ocean/material/diagnostic/capture',
                data=json.dumps({'view':view,'condition':condition,'probe':'positive_depth','settled':True}).encode(),
                headers={'Content-Type':'application/json'})
            with urlopen(request, timeout=100) as response:
                result=json.load(response)
            row={'view':view,'condition':condition,'response':result,
                 'elapsed_seconds':time.monotonic()-started}
            results.append(row);log.write_text(json.dumps(results,indent=2)+'\n')
            if not result.get('ok'):
                raise RuntimeError('Diagnostic failed: '+json.dumps(row))
            image=Path(result['directory'])/'rgb.png';deadline=time.monotonic()+10
            while True:
                try:
                    with Image.open(image) as im:
                        assert im.size==(512,384),im.size
                        im.verify()
                    break
                except (FileNotFoundError,OSError):
                    if time.monotonic()>=deadline:raise
                    time.sleep(.1)
            row['saved_image_verified']=True;log.write_text(json.dumps(results,indent=2)+'\n')
            print(view,condition,result['directory'],flush=True)


if __name__=='__main__':main()
