"""Verify M1-M3 bytes and seal the bounded M4 pilot evidence manifest."""
import ast
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True

EXP=Path(__file__).resolve().parents[1]
ROOT=EXP.parents[1]


def load(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_history():
    counts={}
    for milestone in (1,2,3):
        records=load(EXP/f'qa/milestone_{milestone}_manifest.json')['outputs']
        relocations=load(EXP/f'history/milestone_{milestone}/path_relocations.json')['path_relocations']
        for record in records:
            path=EXP/relocations.get(record['path'],record['path'])
            if sha(path)!=record['sha256']:
                raise ValueError('Historical output changed: '+str(path))
        counts[str(milestone)]=len(records)
    return counts


def main():
    final=EXP/'qa/milestone_4_manifest.json'
    if final.exists():raise RuntimeError('Preserve completed M4 manifest')
    history=verify_history()
    old=load(EXP/'history/milestone_3/specification.json')
    spec=load(EXP/'specification.json')
    if spec['schema_version']!='1.3.0':raise ValueError('M4 specification version')
    for key in ('gsd_levels_cm_px','coordinates','camera','dataset','annotations','splits','model_input','training','evaluation'):
        if spec[key]!=old[key]:raise ValueError('Frozen protocol changed: '+key)
    qa=load(EXP/'qa/m4_capture_validation.json')
    native=load(EXP/'qa/m4_native_validation.json')
    preview=load(EXP/'qa/milestone_4_animation_preview.json')
    if not (qa['passed'] and qa['positive_images']==10 and qa['negative_images']==10
            and all(x['target_detected_in_paired_rgb'] for x in qa['checks'])):
        raise ValueError('Paired image validation failed')
    if not (native['complete_image'] and native['overlaps_passed'] and native['viewport_restored']):
        raise ValueError('Bounded native technical validation failed')
    if not (preview['passed'] and preview['after']['gallery']['animal_count']==11
            and preview['after']['ocean']['elapsed']>preview['before']['ocean']['elapsed']):
        raise ValueError('Live finish preview failed')
    for path in (EXP/'qa').glob('m4_*.py'):
        ast.parse(path.read_text(),filename=str(path))
    paths=[]
    for item in ('README.md','specification.json','qa/M4_CAPTURE.md',
                 'qa/m4_capture.py','qa/m4_geometry.py','qa/m4_prepare_variants.py',
                 'qa/m4_validate_captures.py','qa/m4_package.py',
                 'qa/m4_capture_validation.json','qa/m4_native_validation.json',
                 'qa/milestone_4_animation_preview.json',
                 'history/milestone_3/README.md',
                 'history/milestone_3/specification.json',
                 'history/milestone_3/path_relocations.json'):
        paths.append(EXP/item)
    for folder in ('annotations','renders/milestone_4','qa/m4_diagnostics'):
        if (EXP/folder).exists():
            paths.extend(p for p in (EXP/folder).rglob('*') if p.is_file())
    records=[]
    for path in sorted(set(paths)):
        if not path.is_file():raise ValueError('Missing M4 output: '+str(path))
        records.append({'path':str(path.relative_to(EXP)),
                        'bytes':path.stat().st_size,'sha256':sha(path)})
    manifest={'milestone':4,'status':'complete_with_explicit_native_content_limit',
              'completed_at_utc':datetime.now(timezone.utc).isoformat(),
              'next_milestone':5,'specification_version':'1.3.0',
              'positive_images':10,'negative_images':10,
              'all_ten_positive_targets_detected_in_paired_rgb':True,
              'bbox_semantics':'direct_amodal_evaluated_mesh_projection',
              'native_technical_path':'passed',
              'native_pilot_target_content':'not_certified; generic capture selected',
              'completion_preview':'moving_water_and_11_default_animals_swimming_in_live_viewport',
              'historical_outputs_preserved':history,
              'outputs':records}
    final.write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'passed':True,'outputs':len(records),'historical_outputs_preserved':history},indent=2))


if __name__=='__main__':main()
