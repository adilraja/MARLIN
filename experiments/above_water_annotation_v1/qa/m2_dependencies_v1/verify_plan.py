"""Independently verify the sealed metadata review; never install or activate."""
import ast
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tomllib
import zipfile

BASE=Path(__file__).resolve().parents[2]
REPO=BASE.parents[1]
ROOT=BASE/'diagnostics/m2_dependency_plan_v1'


def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest=read(ROOT/'manifest.json')
    for row in manifest['files']:
        p=Path(row['path'])
        assert not p.is_absolute() and '..' not in p.parts
        assert not set(p.parts)&{'_build','extscache','.cache','__pycache__'} and p.suffix!='.pyc'
        data=(REPO/p).read_bytes()
        assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256'],p
    plan=read(ROOT/'provider_lock.json')
    assert plan['runtime']['build']=='110.2.0+feature.342835.698af100.gl'
    assert plan['provider']=='omni.replicator.core-1.13.27+110.1.1.lx64.r.cp312'
    assert plan['native_backend']=='omni.syntheticdata-0.6.15+698af100.lx64.r.cp312'
    assert plan['total_selected']==127 and plan['reuse_existing']==116 and plan['additions']==11
    assert not plan['replacements'] and not plan['installation_performed']
    assert not plan['provider_activated'] and not plan['archive_file_payloads_downloaded']
    source=ROOT/'runs/capture_profile_solve01'
    solution=read(source/'solutions.json')['proposed_isolated_capture']
    assert solution['result'][0] and not solution['add_enabled']
    assert sha(source/'solutions.json')==plan['resolver']['raw_solutions_sha256']
    actual={r['package_id'] for r in solution['result'][1]}
    assert actual=={r['package_id'] for r in plan['nodes']}
    installed=read(source/'installed_before.json')
    installed_ids={r['package_id'] for r in installed}
    installed_names={r['name'] for r in installed}
    assert len(actual&installed_ids)==116
    assert actual-installed_ids=={r['package_id'] for r in plan['new_packages']}
    graph=read(ROOT/'dependency_graph.json')
    assert {r['id'] for r in graph['nodes']}=={r['id'] for r in plan['nodes']}
    node_ids={r['id'] for r in graph['nodes']}
    assert all(e['source'] in node_ids and e['target'] in node_ids for e in graph['edges'])
    assert all(e['constraint'].get('optional') for e in graph['omitted_optional'])
    metadata=read(ROOT/'selected_extension_metadata.json')
    archive_total=expanded_total=0;native_hashes=0
    for row in plan['new_packages']:
        assert row['name'] not in installed_names
        p=metadata[row['id']]['package']
        assert p['packageId']==row['package_id'] and p['archivePath']==row['archive_url']
        target=row['target']
        assert 'linux-x86_64' in target.get('platform',['linux-x86_64'])
        assert 'cp312' in target.get('python',['cp312'])
        assert 'release' in target.get('config',['release'])
        for minimum in target.get('kit',[]):
            assert tuple(map(int,minimum.split('.')))<=(110,2,0)
        if target.get('kitHash'):
            assert target['kitHash']==['698af100'];native_hashes+=1
        assert row['etag'] and row['s3_version_id'] and row['full_archive_sha256'] is None
        key=row['package_id'].replace('+','_')
        cd=ROOT/'zip_directory_metadata'/(key+'.central_directory.bin')
        footer=ROOT/'zip_directory_metadata'/(key+'.eocd.bin')
        assert sha(cd)==row['central_directory_sha256'] and sha(footer)==row['eocd_sha256']
        # Parse with independent stdlib ZIP metadata code. It adjusts the omitted
        # payload offset automatically; no member content is present or opened.
        with zipfile.ZipFile(io.BytesIO(cd.read_bytes()+footer.read_bytes())) as archive:
            info=archive.infolist()
            assert len(info)==row['entry_count']
            assert sum(i.file_size for i in info)==row['expanded_bytes']
        archive_total+=row['archive_bytes'];expanded_total+=row['expanded_bytes']
    assert native_hashes==4
    assert archive_total==plan['resources']['archive_bytes']==296334086
    assert expanded_total==plan['resources']['expanded_bytes']==619687466
    assert archive_total+2*expanded_total+64*1024**2<plan['resources']['dependency_store_cap_bytes']
    assert plan['resources']['gpu_admission_free_mib']==2048 and plan['resources']['gpu_floor_free_mib']==768
    runs=['startup_index01','startup_index02','shared_registry01','capture_profile_solve01']
    for name in runs:
        r=ROOT/'runs'/name
        query,exit_record,launch=read(r/'query.json'),read(r/'exit.json'),read(r/'launch.json')
        assert query['installed_package_ids_unchanged'] and query['enabled_ids_unchanged']
        assert query['content_destination_empty'] and exit_record['installation_destination_empty']
        assert query['content_pull_calls']==query['captures']==0
        assert not launch['installation_destination_writable']
        assert query['sync_result'] is True
        for f,h in launch['source_sha256'].items():assert sha(r/f)==h
        if name=='startup_index01':
            assert not query['passed'] and 'TypeError' in query['traceback']
        else:
            assert query['passed'] and exit_record['clean_exit'] and not exit_record['cleanup_signals']
    actions=read(ROOT/'planned_actions.json')
    assert actions['approval_required'] and len(actions['actions'])==11
    assert actions['destination']==plan['destination']
    review=read(ROOT/'review_record_template.json')
    assert review['status']=='pending' and review['reviewer'] is None
    assert not review['accepted'] and not review['installation_authorised']
    final=read(ROOT/'preparation_final.json')
    assert not final['proposed_dependency_destination_exists'] and not final['kit_processes']['stdout']
    assert final['service']['returncode']==7 and '595.99.02' in final['gpu']['stdout']
    assert not list(ROOT.rglob('*.zip'))
    for p in (BASE/'qa/m2_dependencies_v1').iterdir():
        if p.suffix=='.py':ast.parse(p.read_text())
        if p.suffix=='.kit':tomllib.loads(p.read_text())
    tomllib.loads((ROOT/'candidate_capture.kit').read_text())
    previous=subprocess.run(['/usr/bin/python3','-B',str(BASE/'qa/m2/verify_feasibility.py')],
                            cwd=REPO,capture_output=True,text=True,check=True)
    prior=json.loads(previous.stdout);assert prior['evidence_verification_passed']
    return dict(evidence_verification_passed=True,candidate_metadata_compatible=True,
        full_capture_dependency_solve_passed=True,selected_extensions=127,reused_installed=116,
        new_packages_planned=11,replacements=0,archive_bytes=archive_total,expanded_bytes=expanded_total,
        independent_zip_directory_verification=True,full_archive_sha256_pending=True,
        archive_file_payloads_downloaded=False,new_dependencies_installed=False,provider_activated=False,
        previous_m2_checkpoint_preserved=True,canonical_source_files_unchanged=prior['canonical_source_files_verified'],
        manifest_files_verified=len(manifest['files']),named_review='pending',milestone_2_complete=False,gate_b='not_ready')


if __name__=='__main__':print(json.dumps(main(),indent=2))
