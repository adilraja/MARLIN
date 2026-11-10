"""Offline independent validation; raw native products remain unmodified."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
import reference as ref

BASE = Path(__file__).resolve().parents[2]
ROOT = BASE/'diagnostics/m2_execution_v1'


def read(p): return json.loads(p.read_text())


def save(p,d): p.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')


def validate(folder):
    b = read(folder/'bundle.json'); owned = b['owned_meshes']; checks = {}; details = {}
    for name, digest in b['files_sha256'].items():
        assert hashlib.sha256((folder/name).read_bytes()).hexdigest() == digest, (folder,name)
    mask = np.load(folder/'native_instance_mask.npy')
    info = read(folder/'native_instance_info.json'); mappings = read(folder/'sdk_instance_mappings.json')
    rows = []; errors = []; ids = []
    for key, path in info['idToLabels'].items():
        value = int(key)
        if value == 0: continue
        sdk = [r for r in mappings if value in r[4] and r[1] == path]
        is_owned = path in owned
        if not path or not sdk: errors.append(dict(id=value,path=path,reason='No matching native SDK ID/path mapping'))
        if is_owned: ids.append(value)
        rows.append(dict(native_id=value,prim_path=path,owned_instance_key='Bottlenose_001' if is_owned and b['pose_id'] else ('m2_fiducial' if is_owned else None),
                         semantic_labels=[r[3] for r in sdk],render_product=b['projection']['render_product']['path'],
                         frame_or_locked_state_key=b['reference_time'],owned=is_owned))
    for value in np.unique(mask):
        if value and str(value) not in info['idToLabels']: errors.append(dict(id=int(value),reason='Visible native ID has no mapping'))
    target = np.isin(mask,ids); box = ref.tight_box(target)
    checks['identity_mapping_valid'] = not errors
    details.update(normalized_mappings=rows,mapping_errors=errors,target_ids=ids,target_pixels=int(target.sum()),mask_derived_tight_box=box)
    checks['mask_box_exact_enclosure'] = box is None if not target.any() else bool(target[box[1]:box[3],box[0]:box[2]].sum()==target.sum()
        and target[box[1],:].any() and target[box[3]-1,:].any() and target[:,box[0]].any() and target[:,box[2]-1].any())
    p = b['projection']; geom = np.load(folder/'direct_geometry.npz')
    points = geom['points_scene_units']; triangles = geom['triangles']
    amodal = ref.geometry_box(points,triangles,p['actual_view_matrix'],p['actual_projection_matrix'])
    details['direct_amodal_geometry_box'] = amodal
    details['direct_frustum_intersection'] = amodal is not None
    details['scene_present'] = b['scene_present']
    params = read(folder/'native_camera_params.json')
    checks['saved_product_camera_resolution'] = params['renderProductResolution']==[512,384] and p['render_product']['resolution']==[512,384] and p['render_product']['camera']==b['camera_path']
    checks['native_camera_intrinsics'] = (params['cameraModel']=='pinhole' and abs(params['cameraFocalLength']-35)<1e-8 and np.max(np.abs(np.array(params['cameraAperture'])-[30.72,23.04]))<1e-5
        and params['cameraNearFar']==[1,5000] and params['cameraFStop']==0 and abs(params['metersPerSceneUnit']-.01)<1e-8)
    if len(points):
        uv = ref.project(points,p['actual_view_matrix'],p['actual_projection_matrix'])
        native_uv = ref.project(points,np.array(params['cameraViewTransform']).reshape(4,4),np.array(params['cameraProjection']).reshape(4,4))
        error = float(np.max(np.abs(uv-native_uv)))
    else: error = 0.
    details['native_vs_authored_projection_max_error_px'] = error
    checks['camera_projection_at_most_1px'] = error <= 1
    native_boxes = np.load(folder/'native_tight_boxes.npy'); bi = read(folder/'native_box_info.json'); owned_boxes = []; raw_owned = []
    assert len(bi['primPaths']) == len(native_boxes)
    for row,path in zip(native_boxes,bi['primPaths']):
        if path not in owned: continue
        raw = [int(row[k]) for k in ('x_min','y_min','x_max','y_max')]; raw_owned.append(dict(prim_path=path,raw=raw))
        if raw[2]>=raw[0] and raw[3]>=raw[1]: owned_boxes.append([raw[0],raw[1],raw[2]+1,raw[3]+1])
    converted = ([min(x[0] for x in owned_boxes),min(x[1] for x in owned_boxes),max(x[2] for x in owned_boxes),max(x[3] for x in owned_boxes)] if owned_boxes else None)
    details.update(native_tight_raw_owned=raw_owned,native_tight_converted=converted,
        native_tight_convention='Inclusive integer maxima; add one to maxima. Established by both fiducial diagnostic views before acceptance captures.')
    checks['native_tight_box_at_most_1px'] = converted is None if box is None else (converted is not None and max(abs(x-y) for x,y in zip(converted,box))<=1)
    fixture = b['item']['fixture']; empty = fixture in ('target_absent','fiducial_out_of_frame','fiducial_fully_occluded')
    checks['empty_control'] = not empty or (target.sum()==0 and box is None and converted is None)
    if not b['pose_id']:
        expected = ref.plane_reference(b); band = ref.boundary_band(b)
        raster = ref.raster(points,triangles,p['actual_view_matrix'],p['actual_projection_matrix'])
        if b['occluder_corners_scene_units'] is not None:
            raster &= ~ref.raster(np.array(b['occluder_corners_scene_units']),np.array([[0,1,2],[0,2,3]]),p['actual_view_matrix'],p['actual_projection_matrix'])
        difference = (expected!=target)&~band
        cross_error = int(((expected!=raster)&~band).sum())
        details.update(analytic_pixels=int(expected.sum()),wrong_core_pixels=int(difference.sum()),
                       excluded_boundary_pixels=int(band.sum()),ray_triangle_crosscheck_core_error=cross_error,
                       reference_mask_box=ref.tight_box(expected))
        checks['analytic_core_zero_errors'] = difference.sum()==0
        checks['independent_ray_triangle_crosscheck'] = cross_error==0
        if not empty: checks['positive_control_nonempty'] = target.any().item()
        np.save(folder/'analytic_reference_mask.npy',expected)
        np.save(folder/'reference_boundary_band.npy',band)
    else:
        checks['animal_skin_replay'] = b['skin_source_max_error_m']<=2e-6
        checks['animal_owned_meshes'] = len(owned)==2 and len(points)==21504 and len(triangles)==40208
        checks['positive_control_nonempty'] = target.any().item()
        details['animal_outline_qualification'] = 'Frozen skinned geometry and identity checked; anatomical outline is not an independent biological reference'
    checks['state_lock'] = b['state_unchanged'] and b['timeline_before']==b['timeline_after']
    checks['bounded_settling'] = b['delivered_settling_frames']==64 and b['settling_seconds']<=45
    time_record = read(folder/'native_time.json')
    ft = time_record['before']; rt = time_record['reference_time']
    details['native_time_difference_seconds'] = abs(ft['fabricFrameTimeNumerator']/ft['fabricFrameTimeDenominator']-rt['referenceTimeNumerator']/rt['referenceTimeDenominator'])
    checks['native_time_consistency'] = ft==time_record['after'] and details['native_time_difference_seconds']==0
    hdr = np.load(folder/'hdr.npz')['rgba']; checks['hdr_finite'] = bool(np.isfinite(hdr).all()) and hdr.shape==(384,512,4)
    checks['exr_exact_roundtrip'] = b['exr_roundtrip_max_error']==0
    rgb = np.maximum(hdr[:,:,:3],0); expected_display = np.rint(255*(rgb/(1+rgb))**(1/2.2)).astype(np.uint8)
    checks['fixed_display_exact'] = np.array_equal(expected_display,np.array(Image.open(folder/'display.png')))
    np.save(folder/'owned_target_mask.npy',target)
    im = Image.open(folder/'display.png').convert('RGB'); overlay = np.array(im).copy()
    overlay[target] = np.rint(overlay[target]*.55+np.array([20,230,75])*.45).astype(np.uint8)
    im = Image.fromarray(overlay); draw = ImageDraw.Draw(im)
    if amodal: draw.rectangle(amodal,outline=(60,145,255),width=1)
    if box: draw.rectangle([box[0],box[1],box[2]-1,box[3]-1],outline=(255,220,20),width=1)
    im.save(folder/'overlay.png')
    details['checks'] = {k:bool(v) for k,v in checks.items()}
    details['passed'] = all(checks.values())
    details['qualification'] = 'dry_engineering_candidate_pending_Gate_B' if details['passed'] else 'failed_dry_validation'
    save(folder/'validation.json',details)
    return dict(attempt_id=folder.name,declaration_id=b['item']['id'],passed=details['passed'],failed_checks=[k for k,v in checks.items() if not v],target_pixels=details['target_pixels'])


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    ledger=read(ROOT/'attempt_ledger.json');rows=[]
    for row in ledger['attempts']:
        if row['run'].endswith('/'+a.run) and row['status'].startswith('captured'):
            rows.append(validate(BASE/row['folder']))
    assert rows
    result=dict(run=a.run,rows=rows,passed=all(r['passed'] for r in rows))
    save(ROOT/'runs'/a.run/'independent_validation.json',result)
    print(json.dumps(result,indent=2));raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
