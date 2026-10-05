"""Project all 250 frozen M5 positive views from evaluated USD mesh vertices."""
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True

ROOT=Path(__file__).resolve().parents[3]
EXP=ROOT/'experiments/gsd_pilot_v1'
OUT=EXP/'renders/milestone_5'
sys.path.insert(0,str(EXP/'qa'))
from m4_geometry import project,save


def main():
    entries=json.loads((OUT/'variant_index.json').read_text())
    output=EXP/'annotations/milestone_5_geometry.json'
    records=json.loads(output.read_text())['records'] if output.exists() else []
    completed={(x['scene_id'],x['gsd_cm_px_requested']) for x in records}
    for item in entries:
        if item['intervention']!='target_present':continue
        key=(item['scene_id'],item['requested_gsd_cm_px'])
        if key in completed:continue
        if item['capture_source']=='milestone_4_reused':
            label=EXP/'renders/milestone_4'/item['scene_id']/('gsd_'+('%.1f'%item['requested_gsd_cm_px']).replace('.','p'))/'target_present/geometry.json'
            record=json.loads(label.read_text())
        else:
            source=ROOT/'artifacts/scene_checkpoints'/item['checkpoint_id']/'scene.usdc'
            wrapped={**item,'snapshot':str(source)}
            record=project(wrapped)
        record['manifest_sha256']=item['manifest_sha256']
        record['biological_manifest_sha256']=item['biological_manifest_sha256']
        records.append(record);completed.add(key)
        save(output,{'schema_version':1,'records':records})
        print(item['scene_id'],item['requested_gsd_cm_px'],'projected',len(records),'/',250,flush=True)
    if len(records)!=250:raise ValueError('Expected 250 positive geometry labels')


if __name__=='__main__':main()
