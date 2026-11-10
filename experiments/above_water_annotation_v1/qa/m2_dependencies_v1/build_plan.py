"""Normalize retained vendor metadata and prepare an installation review lock."""
import ast
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

BASE=Path(__file__).resolve().parents[2]
ROOT=BASE/'diagnostics/m2_dependency_plan_v1'
SOURCE=ROOT/'runs/capture_profile_solve01'


def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    result=json.loads((SOURCE/'solutions.json').read_text())['proposed_isolated_capture']
    assert result['result'][0] and not result['add_enabled']
    rows=result['result'][1]
    metadata={k:ast.literal_eval(v) if isinstance(v,str) else v for k,v in result['metadata'].items()}
    installed=json.loads((SOURCE/'installed_before.json').read_text())
    installed_ids={r['package_id'] for r in installed}
    installed_names={r['name'] for r in installed}
    sizes=json.loads((ROOT/'package_size_and_object_pins.json').read_text())
    by_name={r['name']:r for r in rows}
    nodes=[];edges=[];omitted_optional=[];additions=[]
    for row in rows:
        m=metadata[row['id']];p=m['package']
        assert p['packageId']==row['package_id']
        present=row['package_id'] in installed_ids
        node=dict(id=row['id'],name=row['name'],package_id=row['package_id'],
                  version=p['version'],already_installed=present,
                  registry=m.get('registryProviderName'),target=p.get('target',{}))
        nodes.append(node)
        if not present:
            assert row['name'] not in installed_names, 'Existing package replacement is outside scope'
            size=sizes['packages'][row['id']]
            assert size['package_id']==row['package_id'] and size['url']==p['archivePath']
            additions.append(dict(**node,archive_url=p['archivePath'],
                archive_bytes=size['archive_bytes'],expanded_bytes=size['expanded_bytes'],
                etag=size['etag'],s3_version_id=size['s3_version_id'],
                central_directory_sha256=size['central_directory_sha256'],
                central_directory_offset=size['central_directory_offset'],
                central_directory_bytes=size['central_directory_bytes'],
                eocd_sha256=size['eocd_sha256'],entry_count=size['entry_count'],
                full_archive_sha256=None))
        for name,constraint in m.get('dependencies',{}).items():
            target=by_name.get(name)
            alias=False
            if target is None:
                tagged=[v for n,v in by_name.items() if n.startswith(name+'-')]
                if len(tagged)==1:target=tagged[0];alias=True
            if target is None:
                assert constraint.get('optional'),(row['id'],name)
                omitted_optional.append(dict(source=row['id'],dependency=name,constraint=constraint))
            else:edges.append(dict(source=row['id'],target=target['id'],
                                   dependency_name=name,tagged_provider=alias,constraint=constraint))
    assert len(nodes)==127 and len(additions)==11
    plan=dict(schema_version=1,candidate_id='above_water_annotation_provider_1102_v1',
        recorded_utc=datetime.now(timezone.utc).isoformat(),
        scope='Metadata-compatible isolated provider candidate; not installed or runtime-qualified',
        runtime=dict(version='110.2.0',build='110.2.0+feature.342835.698af100.gl',
                     kit_hash='698af100',platform='linux-x86_64',python='cp312',config='release'),
        resolver=dict(source_run='capture_profile_solve01',success=True,add_enabled=False,input=result['input'],
                      raw_solutions_sha256=sha(SOURCE/'solutions.json')),
        provider='omni.replicator.core-1.13.27+110.1.1.lx64.r.cp312',
        native_backend='omni.syntheticdata-0.6.15+698af100.lx64.r.cp312',
        nodes=nodes,new_packages=additions,total_selected=127,reuse_existing=116,
        additions=11,replacements=[],
        resources=dict(archive_bytes=sum(v['archive_bytes'] for v in additions),
                       expanded_bytes=sum(v['expanded_bytes'] for v in additions),
                       dependency_store_cap_bytes=2*1024**3,private_profile_allowance_bytes=2*1024**3,
                       minimum_free_disk_bytes=10*1024**3,gpu_admission_free_mib=2048,gpu_floor_free_mib=768),
        destination=str((BASE/'dependencies/native_provider_1102_v1').resolve()),
        installation_performed=False,provider_activated=False,archive_file_payloads_downloaded=False,
        archive_checksums=dict(full_archive_sha256='Pending approved quarantine download; must be recorded before unpacking',
            object_identity='Official archive URL, opaque ETag, S3 version ID and ZIP directory/EOCD SHA256 are pinned',
            independent_vendor_whole_archive_sha256_available=False),
        gates=dict(named_dependency_review='pending',installation_authorised=False,
                   dry_validation='not_started',gate_b='not_ready'))
    write(ROOT/'provider_lock.json',plan)
    write(ROOT/'selected_extension_metadata.json',metadata)
    write(ROOT/'dependency_graph.json',dict(nodes=nodes,edges=edges,omitted_optional=omitted_optional))
    write(ROOT/'status.json',dict(recorded_utc=plan['recorded_utc'],
        compatible_provider_metadata_resolved=True,dependency_plan_ready_for_review=True,
        new_dependencies_installed=False,provider_activated=False,milestone_2_complete=False,
        gate_b='not_ready',named_dependency_review='pending',separate_ocean_material_m4='open'))
    # These exact dependency constraints describe a future private capture app.
    # This file is prepared only and is never launched during plan preparation.
    roots={row['id']:row for row in rows if row['id'] in result['input']}
    roots.update({r['id']:r for r in rows if r['package_id'] not in installed_ids})
    lines=['[package]','title = "Reviewed isolated annotation capture candidate"','version = "1.0.0"','', '[dependencies]']
    for eid,row in sorted(roots.items()):lines.append(f'"{row["name"]}" = {{ version = "={metadata[eid]["package"]["version"]}" }}')
    lines+=['','[settings]','app.extensions.registryEnabled = false',
            'app.extensions.syncRegistryOnStartup = false','app.settings.persistent = false',
            'app.settings.loadUserConfig = false','app.settings.saveUserConfig = false',
            'app.file.ignoreUnsavedOnExit = true','app.window.enabled = false',
            'renderer.multiGpu.enabled = false','renderer.gpuEnumeration.glInterop.enabled = false',
            'app.viewport.defaults.width = 512','app.viewport.defaults.height = 384']
    (ROOT/'candidate_capture.kit').write_text('\n'.join(lines)+'\n')
    print('Prepared provider lock: 127 nodes, 116 existing, 11 additions, no replacements.')


if __name__=='__main__':main()
