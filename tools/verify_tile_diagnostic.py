#!/usr/bin/env python3
"""Verify saved diagnostic PNG dimensions and ray matrices; never certify a full image."""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import numpy as np
from PIL import Image
from verify_capture_projection import package


def verify(directory):
    meta=json.loads((directory/'metadata.json').read_text())
    if not meta.get('tile_diagnostic'):
        raise ValueError('Expected a tile-only diagnostic')
    cfg=meta['config']
    model=importlib.import_module(package.__name__+'.hidef_camera')
    camera=model.configuration(cfg['roll_deg'],cfg['downsample'],cfg['aperture_basis'])
    records=[]
    for tile in meta['native_tiling']['tiles']:
        a,b,right,bottom=tile['bounds']
        tp=tile['projection']
        matrix=np.array(tp['capture_view_matrix'])@np.array(tp['capture_projection_matrix'])
        errors=[]
        for u in np.linspace(a+.5,right-.5,5):
            for v in np.linspace(b+.5,bottom-.5,5):
                point=(np.array(camera.ray_plane(u,v))+np.array(meta['camera_translation_m']))/camera.meters_per_scene_unit
                clip=np.r_[point,1]@matrix
                ndc=clip[:3]/clip[3]
                errors.extend([abs((ndc[0]+1)*(right-a)/2-(u-a)),abs((1-ndc[1])*(bottom-b)/2-(v-b))])
        with Image.open(directory/tile['file']) as image:
            size=list(image.size)
        records.append(dict(file=tile['file'],png_dimensions=size,
            dimensions_passed=size==tile['resolution']==tp['render_product']['resolution'],
            max_ray_projection_error_px=float(max(errors)),projection_passed=bool(max(errors)<.001)))
    hashes=all(hashlib.sha256((directory/name).read_bytes()).hexdigest()==value
               for name,value in meta['output_sha256'].items())
    restored=all(meta['restoration_checks'].values())
    report=dict(diagnostic_only=True,full_image_certified=False,
        geometry_and_dimensions_passed=bool(records) and hashes and restored and all(
            r['dimensions_passed'] and r['projection_passed'] for r in records),
        hashes_passed=hashes,restoration_passed=restored,tiles=records,
        overlap_checks=meta['native_tiling']['overlap_checks'],
        actual_gpu_samples_verified=False)
    (directory/'tile_geometry_validation.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    args=parser.parse_args()
    result=verify(args.directory)
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['geometry_and_dimensions_passed'] else 1)
