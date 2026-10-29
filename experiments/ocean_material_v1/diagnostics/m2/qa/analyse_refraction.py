"""Independent planar-interface prediction and predeclared RGB measurement."""
from collections import deque
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def interface_point(camera, target, index_air=1.0, index_water=1.333):
    h, depth = camera[1], -target[1]
    if min(h, depth, index_air, index_water) <= 0:
        raise ValueError('Camera must be above and target below the interface; indices positive')
    dx, dz = camera[0]-target[0], camera[2]-target[2]
    length = math.hypot(dx, dz)
    if length == 0:
        return [target[0], 0, target[2]]
    low, high = 0.0, length
    for _ in range(100):
        r=(low+high)/2
        residual=index_air*(length-r)/math.hypot(h,length-r)-index_water*r/math.hypot(depth,r)
        if residual>0:low=r
        else:high=r
    r=(low+high)/2
    return [target[0]+r*dx/length,0,target[2]+r*dz/length]


def project(point, metadata):
    camera=metadata['camera_position_m'];right,up,forward=metadata['camera_basis_right_up_forward']
    delta=[a-b for a,b in zip(point,camera)]
    dot=lambda a,b:sum(x*y for x,y in zip(a,b))
    intr=metadata['intrinsics_px'];depth=dot(delta,forward)
    return [intr['cx']+intr['fx']*dot(delta,right)/depth,
            intr['cy']-intr['fy']*dot(delta,up)/depth]


def measure(path):
    image=np.asarray(Image.open(path).convert('RGB'),dtype=np.int16)
    mask=(image.min(axis=2)>128)&((image.max(axis=2)-image.min(axis=2))<40)
    roi=np.zeros(mask.shape,dtype=bool);roi[80:320,128:384]=True;mask &= roi
    seen=np.zeros(mask.shape,dtype=bool);components=[]
    for y,x in zip(*np.where(mask)):
        if seen[y,x]:continue
        queue=deque([(int(y),int(x))]);seen[y,x]=True;component=[]
        while queue:
            cy,cx=queue.popleft();component.append((cy,cx))
            for ny,nx in [(cy-1,cx),(cy+1,cx),(cy,cx-1),(cy,cx+1)]:
                if 0<=ny<mask.shape[0] and 0<=nx<mask.shape[1] and mask[ny,nx] and not seen[ny,nx]:
                    seen[ny,nx]=True;queue.append((ny,nx))
        if len(component)>=50:components.append(component)
    if not components:return {'observable':False,'reason':'No qualifying neutral component of at least 50 pixels'}
    c=max(components,key=len);yy,xx=zip(*c)
    return {'observable':True,'area_px':len(c),'centroid_px':[float(np.mean(xx)+.5),float(np.mean(yy)+.5)]}


def analyse(log_name):
    rows=json.loads((ROOT/'qa'/log_name).read_text());measurements=[]
    for row in rows:
        result=row['response']
        if not result.get('ok'):
            measurements.append({'view':row['view'],'condition':row['condition'],'capture_failed':True,'error':result.get('error')});continue
        directory=Path(result['directory']);metadata=json.loads((directory/'metadata.json').read_text())
        point=[0,-1,0]
        expected=project(point,metadata) if row['condition']=='dry' else project(interface_point(
            metadata['camera_position_m'],point,index_water=1.0 if row['condition']=='matched' else 1.333),metadata)
        observed=measure(directory/'rgb.png')
        measurements.append({'view':row['view'],'condition':row['condition'],'directory':str(directory),
                             'expected_centroid_px':expected,'measurement':observed})
    comparisons=[]
    for view in ('nadir','oblique'):
        group={r['condition']:r for r in measurements if r['view']==view}
        dry=group.get('dry',{})
        for condition in ('matched','water'):
            candidate=group.get(condition,{})
            record={'view':view,'condition':condition,'passed':False}
            if dry.get('measurement',{}).get('observable') and candidate.get('measurement',{}).get('observable'):
                expected=[a-b for a,b in zip(candidate['expected_centroid_px'],dry['expected_centroid_px'])]
                measured=[a-b for a,b in zip(candidate['measurement']['centroid_px'],dry['measurement']['centroid_px'])]
                error=math.dist(expected,measured);tolerance=max(2.0,.01*math.hypot(*expected))
                record.update(expected_displacement_px=expected,measured_displacement_px=measured,
                              error_px=error,tolerance_px=tolerance,
                              passed=error<=tolerance and (condition!='water' or view!='oblique' or math.hypot(*measured)>2))
            else:record['reason']='Required target was not observable with the predeclared procedure'
            comparisons.append(record)
    return {'source_log':log_name,'measurement_protocol':'Unchanged fixed ROI/neutral threshold/4-connected largest component',
            'measurements':measurements,'comparisons':comparisons,
            'geometric_checks_passed':len(measurements)==6 and all(r['passed'] for r in comparisons)}


def main():
    reports=[]
    for name in ['capture_execution.json','acceptance_execution.json','settled_execution.json']:
        if (ROOT/'qa'/name).exists():reports.append(analyse(name))
    result={'planar_interface':'y=0, air=1, water=1.333; engineering assumptions',
            'runs':reports,'any_complete_geometric_pass':any(r['geometric_checks_passed'] for r in reports)}
    (ROOT/'qa/refraction_measurements.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps([{'run':r['source_log'],'passed':r['geometric_checks_passed'],'comparisons':r['comparisons']} for r in reports],indent=2))


if __name__=='__main__':main()
