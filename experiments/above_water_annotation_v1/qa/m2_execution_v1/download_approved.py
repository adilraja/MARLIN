"""Download exact MAR-approved objects and seal hashes before any unpacking."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import time
import urllib.request
import zipfile

BASE=Path(__file__).resolve().parents[2]
PLAN=BASE/'diagnostics/m2_dependency_plan_v1'
OUT=BASE/'diagnostics/m2_execution_v1'
REVIEW=BASE/'reviews/MAR_M2_DEPENDENCY_APPROVAL_2026_11_10.json'


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    plan=json.loads((PLAN/'provider_lock.json').read_text())
    review=json.loads(REVIEW.read_text())
    assert review['accepted'] and review['reviewer']=='MAR' and review['installation_authorised']
    assert review['plan_manifest_sha256']==sha(PLAN/'manifest.json')
    assert review['provider_lock_sha256']==sha(PLAN/'provider_lock.json')
    assert review['approved_package_ids']==[r['package_id'] for r in plan['new_packages']]
    dest=Path(plan['destination'])
    assert dest==BASE/'dependencies/native_provider_1102_v1'
    assert not dest.exists(),'Refuse to reuse a dependency store without an explicit continuation'
    assert shutil.disk_usage(BASE).free>=plan['resources']['minimum_free_disk_bytes']
    quarantine=dest/'quarantine';quarantine.mkdir(parents=True)
    started=time.monotonic();records={};failures={}

    def download(row):
        assert time.monotonic()-started<600
        t=time.monotonic()
        partial=quarantine/(row['package_id']+'.zip.part')
        archive=quarantine/(row['package_id']+'.zip')
        req=urllib.request.Request(row['archive_url'],headers={'If-Match':row['etag'],'Accept-Encoding':'identity'})
        h=hashlib.sha256();size=0
        with urllib.request.urlopen(req,timeout=20) as response:
            assert response.status==200
            assert response.headers.get('ETag')==row['etag']
            assert response.headers.get('x-amz-version-id')==row['s3_version_id']
            assert int(response.headers['Content-Length'])==row['archive_bytes']
            with partial.open('xb') as stream:
                while True:
                    assert time.monotonic()-t<180 and time.monotonic()-started<600,'Download time cap exceeded'
                    block=response.read(1024*1024)
                    if not block:break
                    size+=len(block);assert size<=row['archive_bytes']
                    stream.write(block);h.update(block)
        assert size==row['archive_bytes']
        with partial.open('rb') as stream:
            stream.seek(row['central_directory_offset'])
            cd=stream.read(row['central_directory_bytes'])
            stream.seek(-22,2);eocd=stream.read()
        assert hashlib.sha256(cd).hexdigest()==row['central_directory_sha256']
        assert hashlib.sha256(eocd).hexdigest()==row['eocd_sha256']
        with zipfile.ZipFile(partial) as package:
            members=package.infolist()
            assert len(members)==row['entry_count']
            assert sum(m.file_size for m in members)==row['expanded_bytes']
            assert package.testzip() is None,'ZIP member CRC failure'
        partial.rename(archive)
        result=dict(package_id=row['package_id'],archive=str(archive),bytes=size,
                    sha256=h.hexdigest(),etag=row['etag'],s3_version_id=row['s3_version_id'],
                    zip_crc_passed=True,zip_directory_and_footer_match=True,
                    elapsed_seconds=time.monotonic()-t)
        print('Verified',row['package_id'],h.hexdigest(),flush=True)
        return result

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures={pool.submit(download,row):row['package_id'] for row in plan['new_packages']}
        for future in as_completed(futures):
            name=futures[future]
            try:records[name]=future.result()
            except Exception as error:failures[name]=repr(error)
            (OUT/'download_progress.json').write_text(json.dumps(dict(verified=records,failures=failures),indent=2)+'\n')
    report=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),
                approval_record=str(REVIEW),approval_sha256=sha(REVIEW),
                plan_manifest_sha256=sha(PLAN/'manifest.json'),provider_lock_sha256=sha(PLAN/'provider_lock.json'),
                packages=records,failures=failures,passed=len(records)==11 and not failures,
                bytes=sum(r['bytes'] for r in records.values()),elapsed_seconds=time.monotonic()-started,
                installation_performed=False,unpack_performed=False)
    path=OUT/'quarantine_verification.json'
    assert not path.exists();path.write_text(json.dumps(report,indent=2)+'\n')
    assert report['passed'],failures
    (OUT/'quarantine_verification.sha256').write_text(sha(path)+'\n')
    print('Quarantine verified:',report['bytes'],'bytes; no unpacking performed.',flush=True)


if __name__=='__main__':main()
