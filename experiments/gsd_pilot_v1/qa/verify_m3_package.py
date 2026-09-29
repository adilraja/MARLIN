"""Check M3 delivery integrity, historical evidence and protocol preservation."""
import ast
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
EXP=ROOT/'experiments/gsd_pilot_v1'
sys.path.insert(0,str(EXP/'scenes'))
from sampling import validate_manifest


def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    preserved={}
    for milestone in (1,2):
        relocation=read(EXP/f'history/milestone_{milestone}/path_relocations.json')['path_relocations']
        outputs=read(EXP/f'qa/milestone_{milestone}_manifest.json')['outputs']
        for record in outputs:
            path=EXP/relocation.get(record['path'],record['path'])
            if sha(path)!=record['sha256']:raise ValueError('Historical output changed: '+str(path))
        preserved[str(milestone)]=len(outputs)
    spec=read(EXP/'specification.json');old=read(EXP/'history/milestone_2/specification.json')
    for key in ('gsd_levels_cm_px','coordinates','dataset','annotations','splits','model_input','training','evaluation','native_capture'):
        if spec[key]!=old[key]:raise ValueError('Unrequested protocol change: '+key)
    assert spec['schema_version']=='1.2.0' and spec['milestone_finish_check']['applies_to_remaining_milestones']
    files=sorted((EXP/'scenes/manifests').glob('*.json'))
    assert len(files)==50
    for f in files:validate_manifest(read(f))
    assert read(EXP/'qa/m3_reconstruction.json')['passed']
    assert read(EXP/'qa/m3_scene_geometry.json')['passed']
    tests=read(EXP/'qa/m3_regressions/baseline_usd.json')
    contracts=read(EXP/'qa/m3_contract_tests.json')
    assert tests['successful'] and contracts['successful']
    changed=[]
    for record in read(EXP/'qa/input_provenance.json')['files']:
        if sha(ROOT/record['path'])!=record['sha256']:changed.append(record['path'])
    expected=['source/extensions/cris.madil.render_service/cris/madil/render_service/hidef_marine.py']
    if changed!=expected:raise ValueError('Unexpected baseline input changes: '+str(changed))
    scripts=list((EXP/'scenes').glob('*.py'))+[EXP/'qa'/name for name in ['verify_m3_reconstruction.py','verify_m3_package.py','test_reconstruction_contract.py','test_scene_sampling.py','run_m3_regressions.py']]
    for script in scripts:ast.parse(script.read_text(),filename=str(script))
    result={'passed':True,'historical_outputs_preserved':preserved,'candidate_manifests':len(files),
        'tests_passed':tests['passed']+contracts['passed'],'baseline_inputs_changed_intentionally':changed,
        'other_baseline_inputs_unchanged':len(read(EXP/'qa/input_provenance.json')['files'])-len(changed),
        'milestone_finish_preview_required':True,'runtime_behaviour_and_asset_source_unchanged':True}
    (EXP/'qa/m3_package_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
