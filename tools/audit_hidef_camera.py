"""Read-only camera audit; writes a new report, never changes Kit or inputs.

Run with Blender --background --factory-startup --python-exit-code 1 --python
tools/audit_hidef_camera.py (NumPy and USD required; no RTX allocation).
"""
import hashlib
import importlib
import json
import math
from pathlib import Path
import sys
import tempfile
import types
import numpy as np
from pxr import Usd, UsdGeom, Gf

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'source/extensions/cris.madil.render_service'
package = types.ModuleType('_hidef_audit')
package.__path__ = [str(BASE/'cris/madil/render_service')]
sys.modules[package.__name__] = package
camera = importlib.import_module('_hidef_audit.hidef_camera')
geometry = importlib.import_module('_hidef_audit.calibration_geometry')
maps = importlib.import_module('_hidef_audit.hidef_maps')
bartlett = importlib.import_module('_hidef_audit.bartlett_geometry')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ranges(config):
    inputs = maps.geometry_inputs(config)
    result = {}
    for start in range(0, config.image_height_px, 64):
        chunk = bartlett.maps_chunk(inputs, config.roll_deg, start,
                                   min(start+64,config.image_height_px))
        for key, values in chunk.items():
            old = result.setdefault(key, {'simulated_min':math.inf,'simulated_max':-math.inf})
            old['simulated_min'] = min(old['simulated_min'],float(np.nanmin(values)))
            old['simulated_max'] = max(old['simulated_max'],float(np.nanmax(values)))
    return result


def projection_error(config, matrix, translation=(0,0,0)):
    errors=[]
    # Edges, centres and interior points, including both axes together.
    for u in np.linspace(.5,config.image_width_px-.5,9):
        for v in np.linspace(.5,config.image_height_px-.5,9):
            p=config.ray_plane(u,v)
            point=Gf.Vec3d(*((a+b)/config.meters_per_scene_unit for a,b in zip(p,translation)))
            ndc=matrix.Transform(point)
            errors.append(abs((ndc[0]+1)*config.image_width_px/2-u))
            errors.append(abs((1-ndc[1])*config.image_height_px/2-v))
    return max(errors)


def main():
    cases=[]
    authored=[]
    for roll in (7.7675,23.1748):
        for variant,r,basis in (('paper_precise',roll,'paper_effective'),
                                ('rounded_roll',round(roll,2),'paper_effective'),
                                ('manufacturer_roi_hypothesis',roll,'manufacturer_roi_hypothesis')):
            c=camera.configuration(r,1,basis)
            cases.append(dict(variant=variant,reference_roll_deg=roll,roll_deg=r,
                              inputs=maps.geometry_inputs(c),ranges=ranges(c)))
        for divisor in (1,2,4):
            c=camera.configuration(roll,divisor)
            stage=Usd.Stage.CreateInMemory()
            cam=geometry.build_camera(stage,c,'/Audit/Camera',(12,0,-30))
            f=cam.GetCamera(0).frustum
            error=projection_error(c,f.ComputeViewMatrix()*f.ComputeProjectionMatrix(),(12,0,-30))
            # Independent matrix-based Bartlett rays versus runtime scalar rays.
            ray_error=max(math.dist(c.ray_plane(u,v)[::2],bartlett.project(maps.geometry_inputs(c),roll,u,v))
                          for u,v in ((.5,.5),(c.image_width_px/2,c.image_height_px/2),
                                      (c.image_width_px-.5,c.image_height_px-.5)))
            authored.append(dict(roll_deg=roll,downsample=divisor,max_pixel_error=error,
                                 scalar_vs_matrix_ray_error_m=ray_error,passed=error<.001 and ray_error<1e-8))
    # Never load published targets until all independent predictions are finished.
    target_path=BASE/'config/bartlett_validation_targets_v1.json'
    targets=json.loads(target_path.read_text())
    for case in cases:
        target=next(t for t in targets['cases'] if t['roll_deg']==case['reference_roll_deg'])
        for key in ('gsd_width_cm_px','gsd_height_cm_px'):
            entry=case['ranges'][key]
            for end,published in zip(('min','max'),target[key]):
                error=entry['simulated_'+end]-published
                entry.update({f'published_{end}':published,f'signed_error_{end}':error,
                              f'absolute_error_{end}':abs(error),f'relative_error_{end}':abs(error)/published,
                              f'within_half_cent_rounding_{end}':abs(error)<=.005})
    saved=[]
    for relative in ('artifacts/calibration/oblique_zg8cz847','artifacts/calibration/oblique_s345vic1',
                     'artifacts/hidef_marine/oblique_6h25133y'):
        directory=ROOT/relative
        meta=json.loads((directory/'metadata.json').read_text())
        cfg=meta['config']
        c=camera.configuration(cfg['roll_deg'],cfg['downsample'],cfg['aperture_basis'])
        scene=directory/meta['scene_file']
        stage=Usd.Stage.Open(str(scene))
        cams=[UsdGeom.Camera(p) for p in stage.Traverse() if p.IsA(UsdGeom.Camera)]
        path='/MarlinHiDefCapture/Camera' if 'hidef_marine' in relative else '/Calibration/Camera'
        cam=next(cam for cam in cams if str(cam.GetPath())==path)
        f=cam.GetCamera(0).frustum
        trans=meta.get('camera_translation_m',(0,0,0))
        saved_matrix=Gf.Matrix4d(meta['actual_view_matrix'])*Gf.Matrix4d(meta['actual_projection_matrix'])
        record=dict(directory=relative,scene_hash_matches=sha(scene)==meta['scene_sha256'],
                    authored_usd_max_pixel_error=projection_error(c,f.ComputeViewMatrix()*f.ComputeProjectionMatrix(),trans),
                    recorded_viewport_matrix_max_pixel_error=projection_error(c,saved_matrix,trans),
                    expected_projection_y_scale=2*c.focal_length_mm/(c.image_height_px*c.pixel_pitch_um*.001),
                    recorded_projection_y_scale=meta['actual_projection_matrix'][1][1])
        validation=directory/'validation.json'
        if validation.exists():
            result=json.loads(validation.read_text())
            record['prior_rendered_target_validation']=dict(passed=result['passed'],
                max_bbox_error_px=max(e for t in result['targets'] for row in t['absolute_errors_px'] for e in row),
                min_polygon_iou=min(e for t in result['targets'] for e in t['polygon_iou']),
                evidence='Previously captured raster diagnostic, not a new live render')
        saved.append(record)
    precise=[c for c in cases if c['variant']=='paper_precise']
    inputs=precise[0]['inputs']
    footprints=[bartlett.footprint(inputs,r) for r in (-23.1748,-7.7675,7.7675,23.1748)]
    report=dict(status='numerical_and_authored_camera_verified; viewport_matrix_metadata_discrepancy_open',
        parameter_fitting=False,live_kit_modified=False,hardware_calibrated=False,
        nominal_nadir_gsd_cm_px=bartlett.nominal(inputs),cases=cases,
        authored_camera_checks=authored,saved_kit_artifact_checks=saved,
        footprints=footprints,footprint_gaps=bartlett.footprint_gaps(footprints),
        sources_sha256={str(p.relative_to(ROOT)):sha(p) for p in
            (BASE/'config/bartlett_geometry_v1.json',target_path,BASE/'cris/madil/render_service/hidef_camera.py',
             BASE/'cris/madil/render_service/bartlett_geometry.py',BASE/'cris/madil/render_service/calibration_geometry.py')},
        limits=['No new live render; saved Kit images and camera metadata inspected.',
                'Recorded viewport projection differs from authored USD and cannot be treated as image intrinsics.',
                'Prior metric raster checks support correct image geometry despite that metadata discrepancy.',
                'Exact cause of published numerical residuals remains unresolved; sensitivity cases are not fits.'])
    output=Path(tempfile.mkdtemp(prefix='hidef_audit_',dir=ROOT/'artifacts/camera_validation'))
    (output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(output)
    print(json.dumps({'authored':authored,'saved':saved},indent=2))
    if not all(a['passed'] for a in authored) or not all(s['scene_hash_matches'] and s['authored_usd_max_pixel_error']<.001 for s in saved):
        raise RuntimeError('Authored camera audit failed; inspect report')


if __name__=='__main__':
    main()
