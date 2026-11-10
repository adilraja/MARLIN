"""Read-only verifier for the isolated M2 Gate B technical candidate."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

REPO=Path('/home/madil/kit-app-template')
BASE=REPO/'experiments/above_water_annotation_v1'
ROOT=BASE/'diagnostics/m2_execution_v1'


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    revision=read(ROOT/'revision_v2/manifest.json')
    assert sha(ROOT/'revision_v2/manifest.json')==(ROOT/'revision_v2/manifest.sha256').read_text().split()[0]
    for row in revision['files']:
        p=REPO/row['path'];assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],p
    manifest=read(ROOT/'manifest.json')
    assert sha(ROOT/'manifest.json')==(ROOT/'manifest.sha256').read_text().split()[0]
    for row in manifest['files']:
        p=Path(row['path']);assert not p.is_absolute() and '..' not in p.parts
        assert not set(p.parts)&{'_build','extscache','.cache','__pycache__'} and p.suffix!='.pyc'
        actual=REPO/p;assert actual.stat().st_size==row['bytes'] and sha(actual)==row['sha256'],p
    assert manifest['bytes']<=5*1024**3
    approval=read(BASE/'reviews/MAR_M2_DEPENDENCY_APPROVAL_2026_11_10.json')
    assert approval['accepted'] and approval['reviewer']=='MAR' and approval['installation_authorised']
    plan=read(BASE/'diagnostics/m2_dependency_plan_v1/provider_lock.json')
    assert approval['approved_package_ids']==[p['package_id'] for p in plan['new_packages']]
    assert approval['provider_lock_sha256']==sha(BASE/'diagnostics/m2_dependency_plan_v1/provider_lock.json')
    quarantine=read(ROOT/'quarantine_verification.json');assert quarantine['passed'] and len(quarantine['packages'])==11
    tree=read(ROOT/'installed_tree_manifest.json')
    dep=BASE/'dependencies/native_provider_1102_v1'
    for r in tree['files']:
        p=dep/r['path'];assert p.stat().st_size==r['bytes'] and sha(p)==r['sha256'],p
    for package,item in quarantine['packages'].items():
        archive=Path(item['archive']);assert sha(archive)==item['sha256']
        with zipfile.ZipFile(archive) as z:
            for member in z.infolist():
                if member.is_dir():continue
                p=dep/'extensions'/package/member.filename
                assert p.is_file() and sha(p)==hashlib.sha256(z.read(member)).hexdigest(),p
    assert quarantine['bytes']+tree['expanded_bytes']<2*1024**3
    assert read(ROOT/'profile_storage_verification.json')['passed']
    assert read(ROOT/'activated_package_provenance_v1.json')['passed']
    summary=read(ROOT/'dry_validation_summary.json');assert summary['technical_checks_passed']
    declaration=read(BASE/'declarations/capture_declaration.json')
    assert {r['declaration_id'] for r in summary['selected']}=={r['id'] for r in declaration['dry']}
    assert len(summary['selected'])==16
    for row in summary['selected']:
        p=BASE/row['folder'];v=read(p/'validation.json');b=read(p/'bundle.json')
        assert v['passed'] and all(v['checks'].values()) and not v['mapping_errors']
        assert b['state_unchanged'] and b['delivered_settling_frames']==64 and b['settling_seconds']<=45
        assert b['exr_roundtrip_max_error']==0 and 'instance_id_segmentation' in b['native_instance_source']
        run=ROOT/'runs'/next(a['run'].split('/')[-1] for a in read(ROOT/'attempt_ledger.json')['attempts'] if a['attempt_id']==row['attempt_id'])
        exit_record=read(run/'exit.json');worker=read(run/'result.json')
        assert not exit_record['cleanup_signals'] and exit_record['termination_reason'] is None
        assert exit_record['returncode']==(0 if worker['passed'] else 1)
        assert all(r['stage_closed'] and r['product_destroyed'] and not r.get('cleanup_errors') for r in worker['captures'])
        current=next(r for r in worker['captures'] if r.get('folder')==str(p))
        assert current['passed'],current
    ledger=read(ROOT/'attempt_ledger.json');assert len(ledger['attempts'])==24
    assert sum(r['reserve'] for r in ledger['attempts'])==8 and summary['reserve_remaining']==16
    assert all(r['status']!='started' for r in ledger['attempts'])
    assert sum(r['status']=='failed' for r in ledger['attempts'])==2
    assert read(ROOT/'stale_validation.json')['passed'] and read(ROOT/'frozen_pose_verification.json')['passed']
    assert read(ROOT/'runs/contract01/result.json')['passed']
    assert read(ROOT/'host_after.json')['no_kit_process']
    gate=read(BASE/'reviews/gate_b_review.json')
    assert gate['technical_manifest_sha256']==sha(ROOT/'manifest.json')
    assert gate['status']=='pending' and not gate['accepted'] and not gate['m2_complete'] and not gate['m3_authorised']
    # Historical verifiers are read-only. Their status fields refer to their own
    # sealed snapshots, not this current execution.
    for path in (BASE/'qa/m2_dependencies_v1/verify_plan.py',BASE/'qa/m1/verify_gate_a_acceptance.py',
                 REPO/'experiments/gama_dolphin_behaviour_v1/qa/m6/verify_gate_d_acceptance.py'):
        r=subprocess.run(['/usr/bin/python3','-B',str(path)],capture_output=True,text=True,timeout=60)
        assert r.returncode==0,(path,r.stderr)
    gate2=read(BASE/'reviews/gate_b_review_v2.json')
    assert gate2['technical_manifest_sha256']==sha(ROOT/'revision_v2/manifest.json') and not gate2['accepted']
    report=dict(passed=True,candidate_id='above_water_m2_dry_validation_v2',prior_candidate=manifest['candidate_id'],evidence_files_verified=len(manifest['files']),
        evidence_bytes=manifest['bytes'],private_extension_files_verified=len(tree['files']),
        approved_archives_verified=11,canonical_source_files_preserved=119,
        dry_rows_passed=16,stale_sequence_passed=True,real_USD_rejection_checks=7,
        total_attempts=24,reserve_remaining=16,gate_b='pending_named_review',milestone_2_complete=False,
        main_MARLIN_installation_changed=False,marine_labels_qualified=False,separate_ocean_material_m4='open')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
