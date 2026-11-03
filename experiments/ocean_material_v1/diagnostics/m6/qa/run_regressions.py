"""Run the existing relevant offline regressions in independent Python processes."""
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[3]
TESTS=REPO/'source/extensions/cris.madil.render_service/cris/madil/render_service/tests'
NAMES=('camera_math','calibration_geometry','hidef_camera','camera_evidence','renderer_snapshot',
       'cetacean_motion','movement','baked_animation','cetacean_gallery','ocean_enclosure',
       'water_material','underwater_cue','gentle_environment')


def main():
    destination=ROOT/'qa/offline_regressions.json'
    if destination.exists():
        raise RuntimeError('Preserve existing regression evidence')
    rows=[]
    for name in NAMES:
        command=['/usr/bin/python3','-B','-m','unittest','discover','-s',str(TESTS),'-p','test_'+name+'.py','-v']
        result=subprocess.run(command,capture_output=True,text=True,timeout=60)
        rows.append(dict(module=name,command=command,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))
        destination.write_text(json.dumps(rows,indent=2)+'\n')
        print(name,result.returncode,(result.stdout+result.stderr).splitlines()[-1],flush=True)
    if any(row['returncode'] for row in rows):
        raise RuntimeError('Some existing regression modules failed; inspect retained outputs')


if __name__=='__main__':
    main()
