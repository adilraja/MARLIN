"""Read ZIP central-directory metadata by HTTP ranges; never request file payloads."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import struct
import urllib.request

BASE=Path(__file__).resolve().parents[2]
ROOT=BASE/'diagnostics/m2_dependency_plan_v1'
HEADS=ROOT/'sidecars_shared_registry01_omni_replicator_core.json'


def byte_range(url,start,end,total,etag,version):
    assert 0<=start<=end<total and end-start+1<=8*1024**2
    req=urllib.request.Request(url,headers={'Range':f'bytes={start}-{end}',
        'If-Match':etag,'Accept-Encoding':'identity'})
    with urllib.request.urlopen(req,timeout=15) as response:
        # Refuse a server that ignores Range; do not read a full archive body.
        assert response.status==206, f'Range refused: HTTP {response.status}'
        assert response.headers['Content-Range']==f'bytes {start}-{end}/{total}'
        assert response.headers.get('ETag')==etag
        assert response.headers.get('x-amz-version-id')==version
        value=response.read(end-start+2)
        assert len(value)==end-start+1
        return value


def read_package(item):
    name,entry=item
    head=entry['requests'][0];assert head['status']==200
    h={k.lower():v for k,v in head['headers'].items()}
    total=int(h['content-length']);etag=h['etag'];version=h['x-amz-version-id']
    footer=byte_range(head['url'],total-22,total-1,total,etag,version)
    sig,disk,cd_disk,entries_disk,count,size,offset,comment=struct.unpack('<4s4H2IH',footer)
    assert sig==b'PK\x05\x06' and disk==cd_disk==0 and entries_disk==count
    assert comment==0 and size<8*1024**2 and count<65535 and offset+size==total-22
    central=byte_range(head['url'],offset,offset+size-1,total,etag,version)
    pos=0;rows=[]
    for _ in range(count):
        v=struct.unpack_from('<4s6H3I5H2I',central,pos)
        assert v[0]==b'PK\x01\x02' and v[8]!=0xffffffff and v[9]!=0xffffffff
        n,e,c=v[10:13]
        raw=central[pos+46:pos+46+n]
        filename=raw.decode('utf-8' if v[3]&0x800 else 'cp437')
        assert not filename.startswith(('/','\\')) and '..' not in Path(filename).parts
        assert not v[3]&1, 'Encrypted archive not accepted by this metadata reader'
        rows.append(dict(name=filename,compressed_bytes=v[8],expanded_bytes=v[9],
                         crc32=f'{v[7]:08x}',external_attributes=v[15]))
        pos+=46+n+e+c
    assert pos==len(central)
    target=ROOT/'zip_directory_metadata';target.mkdir(exist_ok=True)
    key=entry['package_id'].replace('+','_')
    (target/(key+'.central_directory.bin')).write_bytes(central)
    (target/(key+'.eocd.bin')).write_bytes(footer)
    record=dict(package_id=entry['package_id'],url=head['url'],etag=etag,s3_version_id=version,
                archive_bytes=total,expanded_bytes=sum(r['expanded_bytes'] for r in rows),
                entry_count=count,metadata_bytes_requested=22+size,
                central_directory_offset=offset,central_directory_bytes=size,
                central_directory_sha256=hashlib.sha256(central).hexdigest(),
                eocd_sha256=hashlib.sha256(footer).hexdigest(),members=rows,
                extension_file_payload_downloaded=False,full_archive_sha256=None)
    (target/(key+'.json')).write_text(json.dumps(record,indent=2)+'\n')
    return name,{k:v for k,v in record.items() if k!='members'}


def main():
    packages=json.loads(HEADS.read_text())['packages']
    with ThreadPoolExecutor(max_workers=3) as pool:records=dict(pool.map(read_package,packages.items()))
    result=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),
                scope='HEAD plus exact EOCD/central-directory ranges only; no file payloads',
                packages=records,compressed_total_bytes=sum(p['archive_bytes'] for p in records.values()),
                expanded_total_bytes=sum(p['expanded_bytes'] for p in records.values()),
                metadata_total_bytes=sum(p['metadata_bytes_requested'] for p in records.values()))
    (ROOT/'package_size_and_object_pins.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='packages'},indent=2))


if __name__=='__main__':main()
