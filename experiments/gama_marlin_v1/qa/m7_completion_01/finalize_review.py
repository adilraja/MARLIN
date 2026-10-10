"""Transfer inspected M7 notes through four immutable attempt origins.

Retained files only: no Kit calls, new rendering, original-note edits or
visibility labels. Final contact sheets must equal inspected preview bytes.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path('/home/madil/kit-app-template')
QA=ROOT/'experiments/gama_marlin_v1/qa'
CAMPAIGN=QA/'m7_capture_set'
PREVIEWS=(QA/'m7_live_02_visual_preview',QA/'m7_supplement_01_visual_preview')
OUTPUT=QA/'m7_review'
GENERATOR=QA/'build_m7_review.py'
VERIFIER=QA/'verify_m7_group.py'
CLIENT=ROOT/'tools/capture_gama_dataset_v2.py'
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import aggregate_capture_set as continuation
PINS={}
sys.path.insert(0,str(ROOT/'tools'))
import capture_gama_dataset_v2 as client
import capture_gama_dataset_pending_v2 as pending

def sha(path):
    path=client.live.safe_path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read_pinned(path):
    path=client.live.safe_path(path)
    digest=sha(path)
    if str(path) in PINS and PINS[str(path)]!=digest:
        raise ValueError('Review source changed during loading')
    PINS[str(path)]=digest
    return json.loads(path.read_text())

def write(path,value):
    with path.open('x') as stream:stream.write(json.dumps(value,indent=2,allow_nan=False)+'\n')

def pin_exact(path,digest):
    path=client.live.safe_path(path)
    if sha(path)!=digest or (str(path) in PINS and PINS[str(path)]!=digest):
        raise ValueError('A review or copied source changed: '+str(path))
    PINS[str(path)]=digest
    return path

def copy_bindings(provenance):
    source=client.live.safe_path(provenance['source_group']).parent
    target=client.live.safe_path(provenance['target_group']).parent
    if provenance.get('all_copied_files_byte_identical') is not True:
        raise ValueError('Group copy provenance did not pass')
    rows={}
    for row in provenance['copied_files']:
        relative=Path(row['relative_path'])
        if (relative.is_absolute() or '..' in relative.parts or row.get('byte_identical') is not True
                or row['source_sha256']!=row['target_sha256']):
            raise ValueError('Invalid or non-identical copy provenance')
        original=pin_exact(row['source_path'],row['source_sha256'])
        copied=pin_exact(row['target_path'],row['target_sha256'])
        if (original!=source/relative or copied!=target/relative
                or original.stat().st_size!=row['bytes'] or copied.stat().st_size!=row['bytes']
                or str(original) in rows):
            raise ValueError('Ambiguous source/target copy provenance')
        rows[str(original)]=row
    if len(rows)!=len(pending.tree_pins(source)):
        raise ValueError('Copy provenance does not cover the entire inspected step')
    if provenance['source_group_result']!=client.pin(source/'group_result.json'):
        raise ValueError('Original group-result source pin changed')
    for original,digest in ((source/'group/manifest.json',provenance['source_manifest_sha256']),
                            (target/'group/manifest.json',provenance['target_manifest_sha256'])):
        pin_exact(original,digest)
    if provenance['source_manifest_sha256']!=provenance['target_manifest_sha256']:
        raise ValueError('Copied manifest differs from inspected source')
    return rows

def main():
    if OUTPUT.exists():raise ValueError('Final review output must be fresh')
    declaration=read_pinned(CAMPAIGN/'declaration.json')
    report=read_pinned(CAMPAIGN/'results.json')
    split=read_pinned(CAMPAIGN/'trajectory_split_manifest.json')
    if (report.get('passed') is not True or report.get('kind')!='m7_accepted_capture_set_aggregate'
            or report.get('source_trees_unchanged') is not True
            or report.get('render_calls_made')!=0 or report.get('uninterrupted_successful_capture_claimed') is not False
            or report.get('capture_counts')!={'target_present':75,'target_absent':75,'groups':15}
            or split['images']!=report['traceable_images']):
        raise ValueError('Require the complete transparent accepted capture aggregate')
    if (sha(CAMPAIGN/'declaration.json')!=report['declaration']['sha256']
            or client.validate_declaration(CAMPAIGN/'declaration.json')!=declaration
            or sha(CAMPAIGN/'trajectory_split_manifest.json')!=report['trajectory_split_manifest']['sha256']):
        raise ValueError('Aggregate declaration or split manifest changed')
    attempts=report['source_attempts']
    if (len(attempts)!=4 or [item['passed'] for item in attempts]!=[False,False,True,True]
            or len(report['source_tree_pins_before'])!=4):
        raise ValueError('The exact two failed and two successful attempt statuses were not preserved')
    if [Path(item['directory']).name for item in attempts]!=list(continuation.SOURCE_NAMES):
        raise ValueError('The four source attempt origins differ from the approved continuation')
    source_reports=[]
    for attempt,tree in zip(attempts,report['source_tree_pins_before']):
        folder=client.live.safe_path(attempt['directory'])
        original=read_pinned(folder/'results.json')
        source_reports.append(original)
        if client.pin(folder/'results.json')!=attempt['result'] or original['passed'] is not attempt['passed']:
            raise ValueError('Original attempt result/status changed')
        if pending.tree_pins(folder)!=tree:
            raise ValueError('An original attempt tree changed after aggregate copying')
        for row in tree:
            if client.pin(pin_exact(ROOT/row['path'],row['sha256']))!=row:
                raise ValueError('An original source file changed')
    continuation.select_sources(declaration,source_reports)
    provenance={(row['run_id'],row['step_index']):row for row in report['group_provenance']}
    images={row['image_id']:row for row in split['images']}
    if (len(provenance)!=15 or len(report['group_provenance'])!=15
            or len(images)!=150 or len(split['images'])!=150):
        raise ValueError('Missing or duplicate group/image provenance')
    for path in (Path(__file__),GENERATOR,VERIFIER,CLIENT,ROOT/'tools/capture_gama_dataset_pending_v2.py',
                 ROOT/'tools/aggregate_gama_dataset_v2.py',HERE/'aggregate_capture_set.py'):PINS[str(path)]=sha(path)
    manual={}
    group_notes=[]
    for run in declaration['runs']:
        for state in run['selected_states']:
            stem=f"{run['run_id']}__step_{state['step_index']:03d}"
            folders=[root/stem for root in PREVIEWS if (root/stem/'visual_index.json').is_file()]
            if len(folders)!=1:raise ValueError('Exactly one inspected original preview is required per group')
            folder=folders[0]
            copied=provenance[(run['run_id'],state['step_index'])]
            target_group=CAMPAIGN/'captures'/run['run_id']/f"step_{state['step_index']:03d}"/'group'
            if client.live.safe_path(copied['target_group'])!=target_group:
                raise ValueError('Copy provenance names another target group')
            copies=copy_bindings(copied)
            preview=read_pinned(folder/'visual_index.json')
            perview_path=folder/'per_view_visibility_observations.json'
            perview=read_pinned(perview_path)
            group_path=folder/'visual_inspection.json'
            group=read_pinned(group_path)
            ids=[item['image_id'] for item in preview['images']]
            if len(ids)!=10 or ids!=group['image_ids_reviewed'] or ids!=[item['image_id'] for item in perview['observations']]:
                raise ValueError('Manual review does not cover the exact ten source views')
            if sha(folder/'visual_index.json')!=perview['visual_index_sha256']:
                raise ValueError('Per-view notes are bound to a different preview index')
            if (group['visual_index_sha256']!=PINS[str(folder/'visual_index.json')]
                    or len(preview['contact_sheets'])!=1
                    or group['contact_sheet_sha256']!=preview['contact_sheets'][0]['sha256']
                    or perview['contact_sheet_sha256']!=preview['contact_sheets'][0]['sha256']):
                raise ValueError('Manual group/per-view notes are bound to a different reviewed sheet/index')
            if (group['run_id']!=run['run_id'] or group['seed']!=run['seed']
                    or group['step_index']!=state['step_index']):
                raise ValueError('Manual group notes identify a different selected actual state')
            sheet=preview['contact_sheets'][0]
            if (client.live.safe_path(sheet['group_manifest'])!=client.live.safe_path(copied['source_group'])/'manifest.json'
                    or sheet['group_manifest_sha256']!=copied['source_manifest_sha256']):
                raise ValueError('Reviewed preview represents another copied source')
            for preview_item,observation in zip(preview['images'],perview['observations']):
                item=dict(observation)
                if item['image_id'] in manual:raise ValueError('Duplicate reviewed image ID')
                if (item['rendered_visibility']!='unknown' or item['biological_approval'] is not False
                        or item['manual_observation_is_machine_visibility_label'] is not False
                        or not isinstance(item['manual_contact_sheet_observation'],str)
                        or not item['manual_contact_sheet_observation'].strip()):
                    raise ValueError('Manual observations alter label semantics')
                final=images[item['image_id']]
                origin=final['copy_provenance']
                if (item['physically_present'] is not final['target_present']
                        or origin.get('all_output_hashes_match_source') is not True
                        or client.live.safe_path(origin['source_group'])!=client.live.safe_path(copied['source_group'])
                        or client.live.safe_path(origin['target_group'])!=target_group
                        or any(item[key]!=final[key] or item[key]!=preview_item[key]
                               for key in ('run_id','seed','step_index','gsd_cm_px','variant'))):
                    raise ValueError('Original inspection identity/presence differs from copied view')
                transfers=[]
                for field,digest in (('rgb_file','rgb_sha256'),('annotation_file','annotation_sha256'),('yolo_file','yolo_sha256')):
                    path=pin_exact(item[field],item[digest])
                    target=pin_exact(CAMPAIGN/final[field],final[digest])
                    row=copies[str(path)]
                    if (client.live.safe_path(origin['source_paths'][field])!=path
                            or client.live.safe_path(row['target_path'])!=target
                            or item[digest]!=final[digest] or item[digest]!=preview_item[digest]
                            or item[digest]!=origin['source_image_record'][digest]):
                        raise ValueError('Reviewed source image/annotation/label was substituted')
                    item['source_'+field]=str(path)
                    item[field]=str(target)
                    transfers.append(row)
                original_sheet=pin_exact(item['contact_sheet'],item['contact_sheet_sha256'])
                if original_sheet!=client.live.safe_path(sheet['file']) or item['contact_sheet_sha256']!=sheet['sha256']:
                    raise ValueError('Per-view inspection cites another preview')
                item.update(source_image=item['source_rgb_file'],source_review_note=str(perview_path),
                            source_review_note_sha256=PINS[str(perview_path)],source_group_note=str(group_path),
                            source_group_note_sha256=PINS[str(group_path)],reviewed_preview=str(original_sheet),
                            reviewed_preview_sha256=item['contact_sheet_sha256'],explicit_copy_transfer_provenance=transfers)
                manual[item['image_id']]=item
            group_notes.append({'run_id':run['run_id'],'seed':run['seed'],'step_index':state['step_index'],
                                'source_group_note':str(group_path),'source_group_note_sha256':PINS[str(group_path)],
                                'source_per_view_note':str(perview_path),'source_per_view_note_sha256':PINS[str(perview_path)],
                                'reviewer':group['reviewer'],'image_ids_reviewed':ids,
                                'engineering_observations':group['engineering_observations'],
                                'reviewed_preview':sheet['file'],'reviewed_preview_sha256':sheet['sha256'],
                                'copy_provenance':copied})
    if len(manual)!=150 or set(manual)!=set(images):raise ValueError('Expected exactly 150 manually reviewed actual image IDs')
    command=['/usr/bin/python3','-B',str(GENERATOR),'--campaign',str(CAMPAIGN),
             '--scene-verifications',str(QA/'m7_scene_validation_set'),'--output',str(OUTPUT),
             '--observation','All 150 contact-sheet views were reviewed in source-bound group/per-view notes; final sheets must match those reviewed previews before aggregation.',
             '--observation','This capture set explicitly combines 12 accepted groups from the failed original attempt, one accepted group from a failed supplement, and two successful isolated single-state continuations. All four source attempt statuses remain unchanged; an uninterrupted successful capture campaign is not claimed.',
             '--observation','Observed background shading/detail differences have an unestablished cause; bitwise/photometric equivalence and optical/biological certification are not claimed.',
             '--observation','Seed 42 step 016 positives remain physically present while the owned target is not distinguishable at contact-sheet scale due background overlap; no frames were dropped or replaced.']
    started=datetime.now(timezone.utc).isoformat()
    clock=time.monotonic()
    executed=subprocess.run(command,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=240)
    OUTPUT.mkdir(parents=True,exist_ok=True)
    with (OUTPUT/'generation.log').open('x') as stream:stream.write(executed.stdout)
    after={path:sha(Path(path)) for path in PINS}
    execution={'kind':'m7_final_contact_review_execution','command':command,
               'finalizer_command':[sys.executable,'-B',*sys.argv],'return_code':executed.returncode,
               'started_at_utc':started,'ended_at_utc':datetime.now(timezone.utc).isoformat(),
               'elapsed_seconds':time.monotonic()-clock,'source_pins_before':PINS,'source_pins_after':after,
               'source_inputs_unchanged':PINS==after,'log':str(OUTPUT/'generation.log'),'log_sha256':sha(OUTPUT/'generation.log'),
               'live_calls_made':False,'passed':executed.returncode==0 and PINS==after}
    write(OUTPUT/'generation_execution.json',execution)
    if not execution['passed']:raise ValueError('Final review generation failed; preserve its evidence')
    index=json.loads((OUTPUT/'visual_index.json').read_text())
    final_sheets={item['file']:item['sha256'] for item in index['contact_sheets']}
    observations=[]
    for view in index['images']:
        item=manual[view['image_id']]
        for key in ('run_id','seed','step_index','gsd_cm_px','variant','rgb_file','rgb_sha256','annotation_file','annotation_sha256','yolo_file','yolo_sha256'):
            if item[key]!=view[key]:raise ValueError('Manual review/source/index binding differs')
        if item['physically_present'] is not view['target_present']:
            raise ValueError('Manual review changed canonical target presence')
        if item['contact_sheet_sha256']!=final_sheets[view['contact_sheet']]:
            raise ValueError('Final contact sheet differs from its reviewed preview')
        item['contact_sheet']=view['contact_sheet']
        observations.append(item)
    if len(observations)!=150 or len({item['image_id'] for item in observations})!=150:
        raise ValueError('Final review must cover exactly 150 unique accepted image IDs')
    review={'kind':'m7_manual_per_view_presentation_observations','recorded_at_utc':datetime.now(timezone.utc).isoformat(),
            'scope':'All 150 full-frame contact-sheet views; engineering presentation observations only',
            'observations':observations,'source_group_reviews':group_notes,'source_attempts':attempts,
            'explicit_byte_copy_review_transfer_verified':True,
            'visual_index_sha256':sha(OUTPUT/'visual_index.json'),'reviewed_preview_sheets_match_final_sheets':True,
            'source_rgb_annotation_yolo_hashes_verified':True,'source_inputs_unchanged':PINS==after,
            'rendered_visibility':'unknown','manual_observations_are_machine_visibility_labels':False,
            'automatic_animal_visibility_threshold_used':False,'no_visibility_based_frame_dropping_or_reselection':True,
            'biological_approval':False,'engineering_review_metadata_binding_passed':True,
            'engineering_limitations':['Some paired background animals differ in RGB shading/detail. Cause is unestablished; bitwise or photometric background equivalence is not claimed.',
                                      'The owned target in seed 42 step 016 positives was not distinguishable at contact-sheet scale due background overlap. Presence and canonical labels were retained.',
                                      'At coarser GSDs, small targets and overlay borders limit anatomical inspection at contact-sheet scale.',
                                      'These are static upright mesh proxies with direct amodal rectangles. Biological pose, breathing, animation, exact visible/refracted outlines and water optics were not certified.'],
            'live_calls_made':False}
    write(OUTPUT/'visual_inspection.json',review)
    files=[*(Path(item['file']) for item in index['contact_sheets']),OUTPUT/'visual_index.json',OUTPUT/'index.md',
           OUTPUT/'review_artifacts.json',OUTPUT/'generation.log',OUTPUT/'generation_execution.json',OUTPUT/'visual_inspection.json']
    write(OUTPUT/'review_complete_artifacts.json',{'kind':'m7_complete_review_artifact_manifest','passed':True,
            'files':[{'path':str(path),'bytes':path.stat().st_size,'sha256':sha(path)} for path in files]})
    print(executed.stdout)
    print(json.dumps({'passed':True,'sheets':15,'observations':len(observations),
                      'independent_scene_verifications':index['independent_scene_verifications_passed'],
                      'review':str(OUTPUT/'visual_inspection.json')},indent=2))

if __name__ == '__main__':
    main()
