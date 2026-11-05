"""Check historical evidence unchanged; resolve historical code at M1 commit."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

REPO=Path(__file__).resolve().parents[4]
ROOT=Path(__file__).resolve().parent


def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    baseline=json.loads((ROOT.parents[1]/'baseline_manifest.json').read_text())
    commit=baseline['source_commit']
    data=subprocess.check_output(['git','archive','--format=tar',commit,'source','tools'],cwd=REPO)
    counts={};mismatches={}
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for name,relative in {
            'm5':'experiments/ocean_material_v1/diagnostics/m5/manifest.json',
            'm6':'experiments/ocean_material_v1/diagnostics/m6/manifest.json',
            'driver':'experiments/ocean_material_v1/diagnostics/m4_driver_5959902/manifest.json',
            'preset':'experiments/ocean_material_v1/presets/engineering_v1/manifest.json'}.items():
            manifest=json.loads((REPO/relative).read_text())
            counts[name]={}
            for key in ('files','checkpoint_artifacts','source_inputs','local_asset_dependencies','source_pins'):
                if key not in manifest:continue
                for item in manifest[key]:
                    path=Path(item['path'])
                    assert not path.is_absolute() and '..' not in path.parts
                    assert not set(path.parts)&{'_build','extscache','__pycache__','.cache'} and path.suffix!='.pyc'
                    current=(REPO/path).read_bytes()
                    if key=='source_pins':
                        previous=archive.extractfile(str(path)).read()
                        assert len(previous)==item['bytes'] and sha(previous)==item['sha256'],str(path)
                        if sha(current)!=item['sha256']:
                            mismatches[str(path)]=dict(baseline_sha256=item['sha256'],current_sha256=sha(current))
                    else:
                        assert len(current)==item['bytes'] and sha(current)==item['sha256'],str(path)
                counts[name][key]=len(manifest[key])
    allowed={'source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge/'+p for p in ('actor.py','extension.py')}
    assert set(mismatches)==allowed,mismatches
    return dict(passed=True,counts=counts,source_commit=commit,
        historical_sources_verified_at_baseline_commit=True,all_non_source_evidence_unchanged=True,
        intentional_m2_current_source_changes=mismatches,
        literal_old_verifier='Expected failure against current actor.py/extension.py; raw output retained. Historical manifests were not rewritten.')


if __name__=='__main__':print(json.dumps(main(),indent=2))
