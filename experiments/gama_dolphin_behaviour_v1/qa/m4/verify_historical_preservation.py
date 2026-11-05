"""Verify preserved earlier evidence and its exact committed source versions."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[3]
BASE=ROOT.parents[1]


def sha(data):return hashlib.sha256(data).hexdigest()
def check(records):
    for item in records:
        p=Path(item['path'])
        assert not p.is_absolute() and '..' not in p.parts
        assert not set(p.parts)&{'_build','extscache','__pycache__','.cache'} and p.suffix!='.pyc'
        b=(REPO/p).read_bytes();assert len(b)==item['bytes'] and sha(b)==item['sha256'],str(p)
    return len(records)


def main():
    versions=[('m1',BASE/'baseline_manifest.json','09186b3'),('m2',BASE/'m2_manifest.json','ac9022d'),('m3',BASE/'m3_manifest.json','4af84ab'),
        ('water_m5',REPO/'experiments/ocean_material_v1/diagnostics/m5/manifest.json','09186b3'),('water_m6',REPO/'experiments/ocean_material_v1/diagnostics/m6/manifest.json','09186b3')]
    results={}
    for name,path,commit in versions:
        manifest=json.loads(path.read_text());counts={};changes=[]
        for key in ('files','external_inputs','asset_dependencies','checkpoint_artifacts'):
            if key in manifest:counts[key]=check(manifest[key])
        archive=subprocess.check_output(['git','archive','--format=tar',commit,'source','tools','integrations/gama'],cwd=REPO)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            for item in manifest['source_pins']:
                data=tar.extractfile(item['path']).read()
                assert len(data)==item['bytes'] and sha(data)==item['sha256'],(name,item['path'])
                if sha((REPO/item['path']).read_bytes())!=item['sha256']:changes.append(item['path'])
        counts['source_pins_verified_at_commit']=len(manifest['source_pins'])
        results[name]=dict(commit=commit,verified=counts,current_source_differences=changes)
    allowed={'source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge/extension.py','source/extensions/cris.madil.render_service/cris/madil/render_service/skeletal_animation.py'}
    assert set(results['m3']['current_source_differences'])==allowed
    review=json.loads((BASE/'reviews/MAR_GATE_B_2026_11_05_acceptance_manifest.json').read_text());acceptance_files=check(review['files'])
    record=json.loads((BASE/'reviews/MAR_GATE_B_2026_11_05.json').read_text());bindings=check(record['bindings'])
    assert record['status']=='accepted' and record['reviewer']=='MAR'
    return dict(passed=True,earlier_sealed_evidence_preserved=True,historical_source_versions_verified=results,
        gate_b_acceptance_files=acceptance_files,gate_b_bindings=bindings,
        current_source_disposition='M4 added opt-in animated routes and normalized the shared bake quaternion converter; old literal current-source verifiers correctly no longer match. Their prior evidence/source seals were preserved, not rewritten.')


if __name__=='__main__':print(json.dumps(main(),indent=2))
