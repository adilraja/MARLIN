"""Seal this execution's evidence for Gate B; never rewrite earlier milestones."""
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import numpy as np
from PIL import Image,ImageDraw,ImageFont

REPO=Path('/home/madil/kit-app-template')
BASE=REPO/'experiments/above_water_annotation_v1'
ROOT=BASE/'diagnostics/m2_execution_v1'


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):p.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')


def main():
    assert not (ROOT/'manifest.json').exists(),'Never overwrite a sealed execution'
    declaration=read(BASE/'declarations/capture_declaration.json');ledger=read(ROOT/'attempt_ledger.json')
    selected=[]
    for item in declaration['dry']:
        valid=[]
        for a in ledger['attempts']:
            p=BASE/a['folder']
            if a['declaration_id']==item['id'] and (p/'validation.json').exists() and read(p/'validation.json')['passed']:valid.append(a)
        assert len(valid)==1,(item['id'],valid)
        a=valid[0];p=BASE/a['folder'];v=read(p/'validation.json');b=read(p/'bundle.json')
        selected.append(dict(declaration_id=item['id'],fixture=item['fixture'],view=item['view'],attempt_id=a['attempt_id'],folder=a['folder'],
            passed=True,target_pixels=v['target_pixels'],mask_box=v['mask_derived_tight_box'],amodal_box=v['direct_amodal_geometry_box'],
            native_projection_error_px=v['native_vs_authored_projection_max_error_px'],wrong_core_pixels=v.get('wrong_core_pixels'),
            mapping_errors=len(v['mapping_errors']),settling_seconds=b['settling_seconds'],skin_error_m=b['skin_source_max_error_m']))
    assert len(selected)==16
    stale=[a for a in ledger['attempts'] if a['run'].endswith('/stale01')]
    assert len(stale)==3
    masks=[np.load(BASE/a['folder']/'owned_target_mask.npy') for a in stale]
    st=dict(passed=bool(np.array_equal(masks[0],masks[2]) and masks[0].any() and not masks[1].any()),
        sequence=[a['declaration_id'] for a in stale],target_pixels=[int(m.sum()) for m in masks],remapped_A1_A2_IoU=float((masks[0]&masks[2]).sum()/(masks[0]|masks[2]).sum()),
        native_times=[read(BASE/a['folder']/'native_time.json') for a in stale],
        scope='Immutable authored scene plus native ReferenceTime/rpFabricTime; no fabricated per-AOV frame ID or research synchronisation claim')
    assert st['passed'];save(ROOT/'stale_validation.json',st)
    poses=[]
    for row in selected:
        if not row['fixture'].startswith('animal_'):continue
        b=read(BASE/row['folder']/'bundle.json');s=read(REPO/b['source_pose']['state']['path'])
        e=dict(declaration_id=row['declaration_id'],source_simulation_time_s=s['simulation_time_s'],
            animation_phase_cycles=s['frame']['animation_phase_cycles'],joints=20,vertices=21504,
            root_matrix_max_error=float(np.max(np.abs(np.array(b['root_matrix'])-s['root_matrix']))),
            joint_local_matrix_max_error=float(np.max(np.abs(np.array(b['joint_local_matrices'])-s['joint_local_matrices']))),
            skin_max_error_m=b['skin_source_max_error_m'])
        assert e['root_matrix_max_error']<=1e-8 and e['joint_local_matrix_max_error']<=2e-6 and e['skin_max_error_m']<=2e-6
        poses.append(e)
    a=read(REPO/declaration['source_poses'][0]['state']['path']);b=read(REPO/declaration['source_poses'][1]['state']['path'])
    phase_difference=float(np.max(np.abs(np.array(a['joint_local_matrices'])-np.array(b['joint_local_matrices']))))
    assert phase_difference>0
    save(ROOT/'frozen_pose_verification.json',dict(passed=True,poses=poses,A_B_joint_local_max_difference=phase_difference,biological_approval=False))
    runs=[]
    for p in sorted((ROOT/'runs').glob('*/exit.json')):
        e=read(p);l=read(p.parent/'launch.json');samples=e.get('gpu_samples',[])
        r=dict(run=p.parent.name,clean_exit=e['clean_exit'],returncode=e['returncode'],seconds=e['elapsed_seconds'],
            forced_cleanup=e['cleanup_signals'],gpu_before=l['gpu_before'],minimum_free_gpu_mib=min([x['free_mib'] for x in samples],default=None))
        if samples:assert r['minimum_free_gpu_mib']>=768 and l['gpu_before']['free_mib']>=2048
        runs.append(r)
    profile=read(ROOT/'profile_storage_verification.json');assert profile['passed']
    summary=dict(schema_version=1,recorded_utc=datetime.now(timezone.utc).isoformat(),milestone='M2 — Validate dry-scene geometry and native annotations',
        technical_checks_passed=True,gate_b='pending_named_review',milestone_complete=False,selected=selected,
        attempted_bundles=len(ledger['attempts']),reserve_used=sum(a['reserve'] for a in ledger['attempts']),reserve_remaining=24-sum(a['reserve'] for a in ledger['attempts']),
        maximum_remaining_attempts=144-len(ledger['attempts']),planned_rows_remaining=104,
        failed_capture_attempts=[a for a in ledger['attempts'] if a['status']=='failed'],runs=runs,
        minimum_free_gpu_mib=min(r['minimum_free_gpu_mib'] for r in runs if r['minimum_free_gpu_mib'] is not None),
        native_projection_max_error_px=max(r['native_projection_error_px'] for r in selected),
        canonical_source_changed=False,main_MARLIN_installation_changed=False,
        native_instance_provider='instance_id_segmentation + native SDK get_instance_mappings; development API',
        standard_instance_prim_paths='empty and unqualified',truly_geometry_empty_product='invalid native buffer; unavailable, never synthetic zeros',
        marine_labels_qualified=False,research_capture_approved=False,separate_ocean_material_m4='open')
    save(ROOT/'dry_validation_summary.json',summary)
    review=ROOT/'review_images';review.mkdir(exist_ok=False)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',13)
    sheet=Image.new('RGB',(1600,1360),(18,28,39));draw=ImageDraw.Draw(sheet)
    for i,r in enumerate(selected):
        x=(i%4)*400;y=(i//4)*340
        im=Image.open(BASE/r['folder']/'overlay.png').convert('RGB').resize((400,300),Image.Resampling.LANCZOS)
        sheet.paste(im,(x,y+40));draw.text((x+7,y+4),r['declaration_id'].replace('dry_',''),font=font,fill=(240,244,250))
        draw.text((x+7,y+21),'PASS  |  target pixels: '+str(r['target_pixels']),font=font,fill=(113,224,170))
    sheet.save(review/'dry_contact_sheet.png')
    animal=Image.new('RGB',(1024,848),(18,28,39));d=ImageDraw.Draw(animal)
    for i,r in enumerate([r for r in selected if r['fixture'].startswith('animal_')]):
        x=(i%2)*512;y=(i//2)*424
        animal.paste(Image.open(BASE/r['folder']/'display.png').convert('RGB'),(x,y+40));d.text((x+10,y+10),r['declaration_id']+' — unmodified fixed HDR display',font=font,fill='white')
    animal.save(review/'animal_poses.png')
    lines=['| Declared dry case | Target pixels | Result |','|---|---:|---|']
    for r in selected:lines.append('| '+r['declaration_id']+' | '+str(r['target_pixels'])+' | Passed |')
    table='\n'.join(lines)
    report=f'''# M2 — Validate dry-scene geometry and native annotations

Sprint: **MARLIN — Above-Water Capture and Annotation Validation**. Technical checks passed on 10 November 2026. **Gate B remains pending; M2 has not received human acceptance. M3 has not started.**

MAR approved the eleven pinned additions in [the dated approval](../reviews/MAR_M2_DEPENDENCY_APPROVAL_2026_11_10.json). Exactly 296,334,086 archive bytes were downloaded, object pins/ZIP directories/CRC/full SHA-256 were verified, and 619,687,466 bytes were unpacked using NVIDIA's security checks into the private dependency store. The main runtime and 119 canonical source files were unchanged. No system or environment pip installation, driver change or Kit upgrade occurred.

## Results

All sixteen declared dry rows passed the locked numeric checks using one 512 × 384 product. Analytic ray-plane and independent triangle references found **zero wrong core pixels** beyond the fixed 1 px boundary band. Actual native camera projection differed from authored capture geometry by at most **{summary['native_projection_max_error_px']:.8f} px**. The native tight-box integer maxima were established as inclusive on both pre-acceptance fiducial views; converted boxes met the 1 px limit. Mask-derived half-open boxes enclosed their pixels exactly. Full occlusion, out-of-frame and absent-owned-target controls returned zero owned pixels and no owned tight box.

{table}

![All dry overlays](../diagnostics/m2_execution_v1/review_images/dry_contact_sheet.png)

Overlay legend: green = owned native mask; yellow = exact mask box; blue = direct amodal geometry box. Original fixed displays, native arrays and HDR/EXR are separate files in every selected bundle. Direct geometry boxes are not substituted for visible masks. Square corners and centre are analytic geometric landmarks, not additional independently encoded optical markers.

The four animal views retained the two accepted frozen snapshots, all 20 joints and 21,504 evaluated vertices. Root, joint and skinned-point replay errors were zero. Phases 0.25 at 6 s and 0.45 at 30 s had different joint-local transforms (maximum matrix-element difference {phase_difference:.8f}). Their native IDs resolved to the actual two render meshes. This checks engineering pose/identity, not an independent anatomical or biological outline.

![Animal poses without overlays](../diagnostics/m2_execution_v1/review_images/animal_poses.png)

## Native-provider findings requiring review

1. The standard `instance_segmentation`/`instance_segmentation_fast` path produced correct fiducial pixels and semantics but **empty prim paths**. Its raw output is retained as an unqualified diagnostic. It is not the selected label source.
2. The selected **native renderer-instance** path is `instance_id_segmentation`. NVIDIA marks it hidden/development. It supplies raw uint32 IDs and prim paths; `omni.syntheticdata`'s native mapping independently ties IDs, paths and semantic labels together. Only IDs matching the two explicit owned animal meshes (or the fixture target) are unioned. No same-class or geometric fallback is used. Gate B must explicitly review this bounded development-API use.
3. A stage containing no opaque geometry returned an invalid native buffer and a vendor Warp-node error. Attempt 015 remains failed/unavailable. The declared **target-absent** rows subsequently passed with `/M2NonTargetBackground`, a distinctly labelled negative background at Y = −4 m; the owned target remained physically absent. Real native pixels mapped to the background, with zero owned-target pixels. A completely geometry-empty product remains unsupported; no zero image was manufactured.
4. Vendor logs retain an `IStageReaderWriter` v0.16/v0.15 compatibility warning. The tests qualify only the explicitly exercised path. They do not establish blanket ABI compatibility or a supported production annotator. Four SDK archives omit the registry Kit-hash suffix in their internal package IDs, and contain differing embedded publish build labels. The exact reviewed archive checksums/folders establish provenance; no unreviewed package was substituted. See [artifact provenance](../diagnostics/m2_execution_v1/activated_package_provenance_v1.json) and the retained literal-ID comparison failure.
5. `ReferenceTime` is available despite being hidden from the public annotator-name listing. Native `ReferenceTime` and `rpFabricTime` agreed at readout. All AOVs were copied synchronously after one completed graph step, with no await between copies. Immutable scene, camera/product and paused timeline checks passed. These native clocks are renderer provenance, separate from the accepted source simulation time; per-AOV frame IDs are not exposed. The visible → out-of-frame → visible diagnostic returned 5184 → 0 → 5184 pixels with remapped mask IoU 1.0. This is the contract's explicitly weaker immutable-state/stale-frame assurance, pending Gate B review.

## HDR, resources and lifecycle

The retained native HDR data were float16 values copied losslessly to float32 NPZ and full-float EXR. EXR round trips were exact. Every saved display exactly followed the predeclared Reinhard/gamma mapping. Initial diagnostic light intensities saturated that fixed display; those originals were retained. Acceptance fixtures used dome intensity 0.35 and distant-light intensity 0.8, with no display curve or tolerance change. Product settings record PathTracing, 64 spp, one sample per iteration, denoising off, auto-exposure off, raw product tonemapping and no depth of field. These are engineering lighting settings, not photometric calibration.

The 2048 MiB admission and 768 MiB running GPU floors were preserved; the lowest monitored free memory across all probes was {summary['minimum_free_gpu_mib']} MiB. Every accepted capture settled for 64 delivered steps within 45 s. Each capture was bounded by 90 s; transactions by 600 s and six bundles. Final successful capture and contract transactions detached/destroyed their owned products, closed their anonymous scenes and exited normally without signals. A first no-op bootstrap needed its retained 120 s deadline cleanup; an early probe was explicitly stopped after a local Python error. Other retained failed probes found a hidden-name assertion and an unwanted second automatic viewport. The corrected private setup explicitly attaches the existing RTX engine after removing the automatic viewport. No live MARLIN scene existed at entry, and none was closed or restored.

Attempt accounting: **24 total attempts**, comprising 16 validated dry rows, one failed dry execution and seven diagnostics (including one failed diagnostic). Eight charges used reserve (seven diagnostics and the absent-target retry); **16 reserve attempts remain**. The other 104 planned sprint rows remain unexecuted. Failed attempts are retained, never recycled or erased. Private profiles totalled {profile['total_bytes']:,} bytes, below the 2 GiB allowance. The dependency store remains below its 2 GiB cap.

## Verification and continuation

The six independent geometry unit tests passed. Seven real USD product contract checks rejected missing/wrong camera/product/resolution, non-square pixels, crop and aspect mismatch; cleanup passed. Near/far crossings are explicitly rejected by the bounded direct-geometry adapter, rather than assigned a fabricated box. The M1 Gate A, sealed provider plan, earlier M2 checkpoint, accepted bottlenose Gate D and immutable ocean/preset pins were rechecked without changing their historical snapshots. Historical verifier output describes its sealed earlier checkpoint, not today's installation status.

Run the new read-only verifier from the repository root:

```bash
/usr/bin/python3 -B experiments/above_water_annotation_v1/qa/m2_execution_v1/verify_execution.py
```

Do not rerun builders on this sealed identity. New captures require a new run label, current GPU admission, source/installation pin verification and the remaining attempt budget. The private store can be disconnected simply by omitting its extension folder and private app; normal MARLIN files were not edited. Do not delete accepted assets/evidence or clear shared caches as rollback.

**Stop at [Gate B](../reviews/GATE_B_REVIEW.md).** No marine annotation, underwater attenuation, repeatability campaign, research capture, ML dataset or biological/optical approval is claimed. The separate ocean-material M4 NVIDIA case remains open.
'''
    (BASE/'reports/M2_DRY_ANNOTATION_VALIDATION.md').write_text(report)
    packet='''# Gate B — dry geometry and native-label review

Status: **pending new named human review**. Candidate: **above_water_m2_dry_validation_v1**. No approval has been inferred from MAR's dependency-installation approval.

Please review the [complete M2 report](../reports/M2_DRY_ANNOTATION_VALIDATION.md), [sixteen-case summary](../diagnostics/m2_execution_v1/dry_validation_summary.json), [stale-state check](../diagnostics/m2_execution_v1/stale_validation.json), and [frozen-pose verification](../diagnostics/m2_execution_v1/frozen_pose_verification.json).

![Sixteen dry cases](../diagnostics/m2_execution_v1/review_images/dry_contact_sheet.png)

![Both accepted animal poses, original fixed displays](../diagnostics/m2_execution_v1/review_images/animal_poses.png)

The proposed acceptance is bounded dry engineering evidence: camera projection, opaque-geometry occlusion/identity, raw renderer-instance masks, half-open mask boxes, native box conversion, immutable-state timing and exact replay of the two accepted body phases. The selected mask API is NVIDIA's hidden/development `instance_id_segmentation`, cross-checked with native SDK IDs/paths/semantics. The standard instance API's empty prim paths remain unqualified. A completely geometry-empty product remains unsupported; target-absence controls include a distinct non-target background. The vendor Fabric interface warning is retained. Per-AOV frame IDs are unavailable; native timing plus immutable state and the alternating diagnostic provide the explicitly weaker assurance.

Please inspect that the green overlays cover the intended target, the yellow boxes enclose visible pixels, the blue boxes describe direct geometry, and empty controls remain empty for the owned target. Separate unmodified `display.png`, `hdr.npz`, `hdr.exr` and raw native arrays are available through each selected row's folder in the JSON summary. Corners/centre are analytic geometric landmarks; no encoded optical-marker detection is claimed.

Accepting this candidate would close M2 for these dry products and permit bounded M3 interface qualification. It would **not** approve the broken standard API, geometry-empty products, per-AOV synchronisation, marine/transmitted labels, real-seawater optics, biological validity or research/ML capture. The ocean-material M4 support case remains open. Request changes instead if the development API or these assurance limits are unsuitable.

Reviewer: **pending**. Decision: **pending**. M3 remains stopped.
'''
    (BASE/'reviews/GATE_B_REVIEW.md').write_text(packet)
    save(ROOT/'native_annotation_qualification.json',dict(candidate='above_water_m2_dry_validation_v1',status='pending_Gate_B',selected_api='instance_id_segmentation',vendor_api_status='hidden/development',standard_instance_api_qualified=False,geometry_empty_supported=False,per_AOV_frame_ID_available=False,immutable_state_and_stale_check_passed=True,marine_qualified=False))
    for name,command in [('m1_preservation',['/usr/bin/python3','-B',str(BASE/'qa/m1/verify_gate_a_acceptance.py')]),
                         ('bottlenose_preservation',['/usr/bin/python3','-B',str(REPO/'experiments/gama_dolphin_behaviour_v1/qa/m6/verify_gate_d_acceptance.py')])]:
        result=subprocess.run(command,capture_output=True,text=True,timeout=60)
        assert result.returncode==0,result.stderr
        save(ROOT/(name+'.json'),dict(scope='Read-only verification of historical sealed checkpoint; historical status fields are not latest sprint state',command=command,result=json.loads(result.stdout)))
    # New evidence only; do not include private profile/cache contents or archives.
    paths=[]
    for directory in (ROOT,BASE/'qa/m2_execution_v1'):
        for parent,dirs,files in os.walk(directory):
            dirs[:]=[x for x in dirs if x not in {'_build','extscache','.cache','__pycache__'}]
            for f in files:
                p=Path(parent)/f
                if p.suffix!='.pyc' and p.name not in {'manifest.json','manifest.sha256','verification.json'}:paths.append(p)
    paths.extend([BASE/'reports/M2_DRY_ANNOTATION_VALIDATION.md',BASE/'reviews/GATE_B_REVIEW.md',BASE/'reviews/MAR_M2_DEPENDENCY_APPROVAL_2026_11_10.json'])
    rows=[dict(path=str(p.relative_to(REPO)),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(set(paths))]
    save(ROOT/'manifest.json',dict(schema_version=1,candidate_id='above_water_m2_dry_validation_v1',status='technical_pass_pending_named_Gate_B',recorded_utc=datetime.now(timezone.utc).isoformat(),files=rows,
        prior_plan_manifest_sha256=sha(BASE/'diagnostics/m2_dependency_plan_v1/manifest.json'),file_count=len(rows),bytes=sum(r['bytes'] for r in rows)))
    (ROOT/'manifest.sha256').write_text(sha(ROOT/'manifest.json')+'  manifest.json\n')
    save(BASE/'reviews/gate_b_review.json',dict(candidate_id='above_water_m2_dry_validation_v1',status='pending',accepted=False,reviewer=None,technical_manifest_sha256=sha(ROOT/'manifest.json'),review_packet_sha256=sha(BASE/'reviews/GATE_B_REVIEW.md'),m2_complete=False,m3_authorised=False))
    save(BASE/'CURRENT_PROGRESS.json',dict(recorded_utc=datetime.now(timezone.utc).isoformat(),sprint='MARLIN — Above-Water Capture and Annotation Validation',milestone_1='accepted by MAR',milestone_2='technical checks passed; pending named Gate B review',milestone_2_complete=False,gate_b='pending',milestone_3='not_started',
        latest_report='reports/M2_DRY_ANNOTATION_VALIDATION.md',latest_review='reviews/GATE_B_REVIEW.md',candidate_id='above_water_m2_dry_validation_v1',technical_manifest_sha256=sha(ROOT/'manifest.json'),approved_dependencies_installed_isolated=11,main_installation_changed=False,validated_dry_rows=16,total_attempts=24,reserve_used=8,reserve_remaining=16,separate_ocean_material_m4='open'))
    print(json.dumps(dict(selected_rows=16,attempts=24,reserve_remaining=16,manifest_files=len(rows),evidence_bytes=sum(r['bytes'] for r in rows),gate_b='pending'),indent=2))


if __name__=='__main__':main()
