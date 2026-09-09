"""Load original/working bird pairs through the live MARLIN HTTP service.

Copies use ReviewOriginal_/ReviewCleaned_ names; existing animals are untouched.
This is a visual review, not a physical or pose calibration.
"""
import json
import shutil
import time
from pathlib import Path
from rebuild_scene import request

ROOT=Path(__file__).resolve().parents[4]
SPECIES=['guillemot','northern_gannet','european_storm_petrel','common_tern']


def compare():
    results=[]
    for index,species in enumerate(SPECIES):
        manifest=json.loads((ROOT/f'assets/survey_species/{species}/manifest.json').read_text())
        report=json.loads((ROOT/manifest['working_copy']['measurement_path']).read_text())
        scale=450/report['after']['maximum_dimension']
        names=[]
        for label,path in [('Original',manifest['usd_path']),('Cleaned',manifest['working_copy']['usd_path'])]:
            name=f'Review{label}_{species}';names.append(name)
            request('/scene/cetacean/spawn',{'name':name,'asset_path':str(ROOT/path),
                'model_rotation':[-90,0,0],'scale':scale,'position':[0,0,0]})
        records={p['path'].rsplit('/',1)[-1]:p for p in request('/debug/scene/inspection')['prims']}
        placed=[]
        for column,name in enumerate(names):
            p=records[name];low=p['bounds_min'];high=p['bounds_max']
            position=[(column-0.5)*750-(low[0]+high[0])/2,
                      -low[1], 4500+index*850-(low[2]+high[2])/2]
            request('/scene/cetacean/transform',{'name':name,'position':position})
            placed.append({'name':name,'position':position,'scale':scale})
        results.append({'species':species,'pairs':placed})
    # Frame the first pair; select other review prims in Kit to inspect closely.
    first=results[0]['pairs'][1]
    request('/scene/camera/chase/start',{'target_name':first['name'],
        'camera_name':'BirdComparisonCamera','distance':4500,'height':2200,
        'side_offset':-350,'look_ahead':0,'look_height':200,'documentary_mode':False})
    time.sleep(2)
    request('/debug/viewport/capture',{})
    time.sleep(2)
    capture=request('/debug/viewport/capture',{})
    output=ROOT/'assets/survey_species/inspection_comparison';output.mkdir(exist_ok=True)
    shutil.copy2(capture['file_path'],output/'kit_comparison.png')
    (output/'placement_report.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps({'ok':True,'new_instances':8,'comparison':str(output)},indent=2))


if __name__=='__main__':
    compare()
