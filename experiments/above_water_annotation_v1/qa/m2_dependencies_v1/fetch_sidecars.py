"""Read official JSON sidecars and archive HEAD headers, never archive payloads."""
import ast
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE=Path(__file__).resolve().parents[2]
ROOT=BASE/'diagnostics/m2_dependency_plan_v1'
REGISTRIES={
 'kit/prod/sdk':'https://ovextensionsprod.blob.core.windows.net/exts/kit/prod/sdk/110.2/698af100',
 'kit/prod/default':'https://ovextensionsprod.blob.core.windows.net/exts/kit/prod/110.2/shared',
 'kit/prod/110shared-metadata':'https://ovextensionsprod.blob.core.windows.net/exts/kit/prod/110/shared'}


def request(url, method):
    assert urllib.parse.urlparse(url).hostname in (
        'ovextensionsprod.blob.core.windows.net','d4i3qtqj3r0z5.cloudfront.net')
    assert method=='HEAD' or urllib.parse.urlparse(url).path.endswith('.json')
    record=dict(url=url,method=method)
    try:
        req=urllib.request.Request(urllib.parse.quote(url,safe=':/?=&%'),method=method)
        with urllib.request.urlopen(req,timeout=12) as response:
            record.update(status=response.status,headers=dict(response.headers))
            if method=='GET':
                raw=response.read(1024*1024+1)
                assert len(raw)<=1024*1024,'Metadata sidecar exceeds cap'
                record.update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),json=json.loads(raw))
    except urllib.error.HTTPError as error:record.update(status=error.code,error=str(error))
    except Exception as error:record['error']=str(error)
    return record


HEADS_ONLY = '--heads-only' in sys.argv


def package_info(item):
    name,meta=item
    p=meta['package'];reg=REGISTRIES[meta['registryProviderName']]
    requests=[request(p['archivePath'],'HEAD')]
    if HEADS_ONLY:return name,dict(package_id=p['packageId'],requests=requests)
    # Use the metadata URL forms from NVIDIA's checked-in
    # tools/repoman/scripts/kit_precache_airgap.py; never call its installer.
    basename=Path(urllib.parse.urlparse(p['archivePath']).path).name[:-4]+'.json'
    urls=[f"{reg}/archives/{p['name']}/{p['packageId']}.json",
          f"{reg}/archives/{p['packageId']}.json",
          f"{reg}/archives/{p['name']}/{basename}",f"{reg}/archives/{basename}"]
    for url in dict.fromkeys(urls):
        record=request(url,'GET');requests.append(record)
        if record.get('status')==200 and 'json' in record:break
    return name,dict(package_id=p['packageId'],requests=requests)


def main(run,provider):
    source=ROOT/'runs'/run
    solution=json.loads((source/'solutions.json').read_text())[provider]
    assert solution['result'][0]
    installed={e['package_id'] for e in json.loads((source/'installed_before.json').read_text())}
    metadata={k:ast.literal_eval(v) if isinstance(v,str) else v for k,v in solution['metadata'].items()}
    wanted={row['id']:metadata[row['id']] for row in solution['result'][1]
            if row['package_id'] not in installed}
    with ThreadPoolExecutor(max_workers=3) as pool:results=dict(pool.map(package_info,wanted.items()))
    target=ROOT/('sidecars_'+run+'_'+provider.replace('.','_')+'.json')
    target.write_text(json.dumps(dict(recorded_utc=datetime.now(timezone.utc).isoformat(),
                      scope='JSON metadata and archive headers only; no extension payload',
                      source_run=run,provider=provider,packages=results),indent=2)+'\n')
    print(json.dumps({k:[dict(status=r.get('status'),method=r['method'],
                             length=r.get('headers',{}).get('Content-Length'),json_keys=list(r.get('json',{})))
                        for r in v['requests']] for k,v in results.items()},indent=2))


if __name__=='__main__':main(*[arg for arg in sys.argv[1:] if arg!='--heads-only'])
