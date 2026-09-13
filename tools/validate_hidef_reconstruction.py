"""Full-resolution independent GSD statistics for requested rounded HiDef rolls.

No renderer and no parameter fitting. Requires numpy. Targets are read only
after predictions are calculated. Existing precise-roll report remains intact.
"""
import json
from pathlib import Path
import sys
import tempfile
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT/'source/extensions/cris.madil.render_service/config'
sys.path.insert(0,str(CONFIG.parent/'cris/madil/render_service'))
from bartlett_geometry import maps_chunk, nominal, footprint


def main():
    geometry = json.loads((CONFIG/'bartlett_geometry_v1.json').read_text())
    cases = []
    for roll in (7.77,23.17):
        stats = {}
        for start in range(0,2192,64):
            maps=maps_chunk(geometry,roll,start,min(start+64,2192))
            for key,values in maps.items():
                lo,hi=float(np.nanmin(values)),float(np.nanmax(values))
                old=stats.get(key,{'simulated_min':float('inf'),'simulated_max':-float('inf')})
                stats[key]={'simulated_min':min(lo,old['simulated_min']),
                            'simulated_max':max(hi,old['simulated_max'])}
        cases.append({'roll_deg':roll,'ranges':stats,'footprint':footprint(geometry,roll)})
    targets=json.loads((CONFIG/'bartlett_validation_targets_v1.json').read_text())
    for case,target in zip(cases,targets['cases']):
        case['published_comparison_roll_deg']=target['roll_deg']
        for direction in ('gsd_width_cm_px','gsd_height_cm_px'):
            entry=case['ranges'][direction]
            for label,expected in zip(('min','max'),target[direction]):
                error=abs(entry['simulated_'+label]-expected)
                entry['published_'+label]=expected
                entry['absolute_error_'+label]=error
                entry['relative_error_'+label]=error/expected
    output_root=ROOT/'artifacts/camera_validation'
    output_root.mkdir(parents=True,exist_ok=True)
    output=Path(tempfile.mkdtemp(prefix='hidef_rounded_',dir=output_root))
    geometry['rolls_deg']=[7.77,23.17]
    result={'geometry_inputs':geometry,'nominal_nadir_gsd_cm_px':nominal(geometry),
            'cases':cases,'parameter_fitting':False,'published_targets':targets,
            'status':'numerical_geometry_not_hardware_or_full_resolution_render_validation'}
    (output/'report.json').write_text(json.dumps(result,indent=2))
    print(output)
    for case in cases:
        print(case['roll_deg'],case['ranges'])


if __name__=='__main__':
    main()
