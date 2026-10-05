"""Seal a validated M5 dataset while preserving M1-M4 output bytes."""
import ast
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True

EXP=Path(__file__).resolve().parents[1]


def load(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def history_check():
    counts={}
    for milestone in (1,2,3,4):
        records=load(EXP/f'qa/milestone_{milestone}_manifest.json')['outputs']
        relocations=load(EXP/f'history/milestone_{milestone}/path_relocations.json')['path_relocations']
        for record in records:
            path=EXP/relocations.get(record['path'],record['path'])
            if not path.is_file() or sha(path)!=record['sha256']:
                raise ValueError('Historical output changed: '+str(path))
        counts[str(milestone)]=len(records)
    return counts


def main():
    target=EXP/'qa/milestone_5_manifest.json'
    if target.exists():raise RuntimeError('Preserve existing M5 delivery manifest')
    history=history_check()
    spec=load(EXP/'specification.json')
    old=load(EXP/'history/milestone_4/specification.json')
    if spec['schema_version']!='1.4.0':raise ValueError('Expected M5 specification revision')
    for field in ('gsd_levels_cm_px','coordinates','camera','targets','environment',
                  'scene_generation','dataset','annotations','splits','model_input',
                  'training','evaluation','native_capture'):
        if spec[field]!=old[field]:raise ValueError('Frozen protocol changed: '+field)
    qa=load(EXP/'qa/m5_dataset_validation.json')
    preview=load(EXP/'qa/milestone_5_animation_preview.json')
    if not (qa['passed'] and qa['images']==300 and qa['positive_annotations']==250
            and qa['scene_groups']==50 and qa['paired_negative_checks']==50
            and qa['all_positive_targets_detected']):
        raise ValueError('M5 dataset QA incomplete')
    if not (preview['passed'] and preview['after']['gallery']['animal_count']==11
            and preview['after']['ocean']['elapsed']>preview['before']['ocean']['elapsed']):
        raise ValueError('M5 moving preview incomplete')
    scripts=sorted((EXP/'qa').glob('m5_*.py'))
    for path in scripts:ast.parse(path.read_text(),filename=str(path))
    files=[EXP/name for name in ('README.md','specification.json','qa/M5_DATASET.md',
          'qa/m5_dataset_validation.json','qa/milestone_5_animation_preview.json',
          'history/milestone_4/README.md','history/milestone_4/specification.json',
          'history/milestone_4/path_relocations.json')]
    files.extend(scripts)
    for folder in ('renders/milestone_5','annotations'):
        files.extend(path for path in (EXP/folder).rglob('*') if path.is_file()
                     and (folder!='annotations' or path.name.startswith('milestone_5')))
    outputs=[]
    for path in sorted(set(files)):
        if not path.is_file():raise ValueError('Missing M5 output: '+str(path))
        outputs.append({'path':str(path.relative_to(EXP)),
                        'bytes':path.stat().st_size,'sha256':sha(path)})
    value={'milestone':5,'status':'complete_provisional_dataset',
           'completed_at_utc':datetime.now(timezone.utc).isoformat(),
           'next_milestone':6,'specification_version':'1.4.0',
           'images':300,'positive_annotations':250,'negative_images':50,
           'scene_groups':50,'all_positive_targets_detected':True,
           'completion_preview':'moving_water_and_11_default_animals_swimming_in_live_viewport',
           'historical_outputs_preserved':history,'outputs':outputs}
    target.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'passed':True,'outputs':len(outputs),
                      'historical_outputs_preserved':history},indent=2),flush=True)


if __name__=='__main__':main()
