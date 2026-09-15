"""Check version-2 image matrices, GSD maps and optional raster target evidence."""
import argparse
import hashlib
import importlib
import json
import math
from pathlib import Path
import sys
import types
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
package=types.ModuleType('_projection_verify')
package.__path__=[str(ROOT/'source/extensions/cris.madil.render_service/cris/madil/render_service')]
sys.modules[package.__name__]=package


def verify(directory):
    meta=json.loads((directory/'metadata.json').read_text())
    if meta.get('projection_metadata_version')!=2:
        raise ValueError('Legacy UI matrices are not verified image projection; recapture rather than relabel')
    cfg=meta['config']
    model='sony_camera' if meta['camera_model']=='Sony ILX-LR1' else 'hidef_camera'
    module=importlib.import_module('_projection_verify.'+model)
    c=(module.configuration(cfg['downsample']) if model=='sony_camera' else
       module.configuration(cfg['roll_deg'],cfg['downsample'],cfg['aperture_basis']))
    vp=np.array(meta['capture_view_matrix'])@np.array(meta['capture_projection_matrix'])
    trans=np.array(meta['camera_translation_m'])
    errors=[]
    for u in np.linspace(.5,c.image_width_px-.5,9):
        for v in np.linspace(.5,c.image_height_px-.5,9):
            p=(np.array(c.ray_plane(u,v))+trans)/c.meters_per_scene_unit
            clip=np.r_[p,1]@vp
            ndc=clip[:3]/clip[3]
            errors.extend((float(abs((ndc[0]+1)*c.image_width_px/2-u)),float(abs((1-ndc[1])*c.image_height_px/2-v))))
    map_errors=[]
    with np.load(directory/'directional_gsd.npz') as maps:
        for i,j in ((0,0),(c.image_width_px//2,c.image_height_px//2),(c.image_width_px-2,c.image_height_px-2)):
            u,v=i+.5,j+.5
            p=c.ray_plane(u,v)
            for key,q in (('gsd_width_cm_px',c.ray_plane(u+1,v)),('gsd_height_cm_px',c.ray_plane(u,v+1))):
                map_errors.append(abs(float(maps[key][j,i])-100*math.dist(p,q)))
    hashes=all(hashlib.sha256((directory/name).read_bytes()).hexdigest()==value for name,value in meta['output_sha256'].items())
    checks=dict(capture_matrix_matches_rays=max(errors)<.001,maps_match_rays=max(map_errors)<1e-7,
                capture_outputs_hash_verified=hashes,live_viewport_restored=meta['main_viewport_preserved'],
                product_resolution_matches=meta['render_product']['resolution']==[c.image_width_px,c.image_height_px])
    raster=None
    if meta.get('native_tiling'):
        checks['tile_overlaps_passed']=meta['native_tiling']['overlaps_passed']
        checks['native_assembled_dimensions']=meta['assembled_image_resolution']==[c.image_width_px,c.image_height_px]
        tile_errors=[]
        for tile in meta['native_tiling']['tiles']:
            a,b,right,bottom=tile['bounds']
            tp=tile['projection']
            tvp=np.array(tp['capture_view_matrix'])@np.array(tp['capture_projection_matrix'])
            for u,v in ((a+.5,b+.5),((a+right)/2,(b+bottom)/2),(right-.5,bottom-.5)):
                p=(np.array(c.ray_plane(u,v))+trans)/c.meters_per_scene_unit
                clip=np.r_[p,1]@tvp
                ndc=clip[:3]/clip[3]
                tile_errors.extend((float(abs((ndc[0]+1)*(right-a)/2-(u-a))),
                                    float(abs((1-ndc[1])*(bottom-b)/2-(v-b)))))
        checks['all_tile_matrices_match_native_rays']=max(tile_errors)<.001
    if meta.get('projection_probe'):
        raster=json.loads((directory/'validation.json').read_text())
        checks['raster_targets_passed']=raster['passed']
    report=dict(passed=all(checks.values()),checks=checks,max_reprojection_error_px=max(errors),
                max_tile_reprojection_error_px=max(tile_errors) if meta.get('native_tiling') else None,
                max_gsd_error_cm_px=max(map_errors),projection_metadata_version=2,
                scope='Flat reference-plane image geometry; no hardware, biological or refraction calibration',
                raster_evidence='same marine capture path, nine rendered targets' if raster else 'No targets in this image; use separately validated same-path probe',
                raster_max_bbox_error_px=max(e for t in raster['targets'] for row in t['absolute_errors_px'] for e in row) if raster else None,
                raster_min_iou=min(e for t in raster['targets'] for e in t['polygon_iou']) if raster else None)
    (directory/'projection_validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return report['passed']


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    args=parser.parse_args()
    raise SystemExit(0 if verify(args.directory) else 1)
