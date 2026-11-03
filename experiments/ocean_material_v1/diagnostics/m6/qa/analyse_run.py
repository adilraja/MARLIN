"""Measure paired M6 invariants, visible differences, fresh reload and rollback."""
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/attempt01'
FRESH=ROOT/'runs/reload_process01'
M5=ROOT.parent/'m5'
sys.path.insert(0,str(M5/'qa'))
from compare_images import metrics,read
from display_images import convert
from analyse_run import settings_comparator


def load(path):
    return json.loads(path.read_text())


def matrix_difference(a,b):
    return max(float(np.max(np.abs(np.array(a['projection'][key])-np.array(b['projection'][key]))))
               for key in ('capture_view_matrix','capture_projection_matrix'))


def main():
    destination=ROOT/'analysis.json'
    if destination.exists():
        raise RuntimeError('Preserve existing analysis')
    assert load(FRESH/'done.json')['ok']
    same_settings,_=settings_comparator()
    paired=load(RUN/'capture_records.json')
    reloaded=load(FRESH/'capture_records.json')
    assert len(paired)==6 and len(reloaded)==2
    records={record['label']:record for record in paired+reloaded}
    folders={record['label']:(RUN if record in paired else FRESH)/record['label'] for record in paired+reloaded}
    original_identity=load(RUN/'preparation.json')['initial_animal']['identity_sha256']
    all_dimensions={}
    for label,record in records.items():
        folder=folders[label]
        native=read(folder/'rgb.png')
        with np.load(folder/'hdr.npz') as archive:
            hdr=archive['rgba'][...,:3].astype(float)
        assert hdr.shape==(384,512,3) and np.isfinite(hdr).all()
        primary=convert(hdr)
        review=np.rint(255*np.clip(np.log1p(np.maximum(hdr,0))/np.log1p(12000),0,1)).astype(np.uint8)
        if (folder/'hdr_display.png').exists():
            assert np.array_equal(read(folder/'hdr_display.png'),primary)
            assert np.array_equal(read(folder/'review_log.png'),review)
        else:
            Image.fromarray(primary).save(folder/'hdr_display.png')
            Image.fromarray(review).save(folder/'review_log.png')
        overlay=Image.fromarray(review)
        ImageDraw.Draw(overlay).rectangle(record['direct_geometric_bbox_xyxy_px'],outline=(255,205,75),width=1)
        if (folder/'review_geometric_box.png').exists():
            assert np.array_equal(np.asarray(Image.open(folder/'review_geometric_box.png')),np.asarray(overlay))
        else:
            overlay.save(folder/'review_geometric_box.png')
        exr=subprocess.check_output(['file',str(folder/'hdr.exr')],text=True).strip()
        assert 'dataWindow: (0 0)-(511 383)' in exr
        all_dimensions[label]=dict(png=[native.shape[1],native.shape[0]],hdr=list(hdr.shape),exr=exr,
            native_png_all_white=bool(np.all(native==255)),animal_identity_unchanged=record['animal']['identity_sha256']==original_identity)
        assert all_dimensions[label]['animal_identity_unchanged']
    pairs={}
    for pose in ('above','intersecting','below'):
        a,b=records['original_'+pose],records['engineering_'+pose]
        controls_a=load(folders['original_'+pose]/'effective_settings.json')
        controls_b=load(folders['engineering_'+pose]/'effective_settings.json')
        pa,pb=a['scene_state']['prim_hashes'],b['scene_state']['prim_hashes']
        changed=sorted(path for path in set(pa)|set(pb) if pa.get(path)!=pb.get(path))
        allowed=lambda path:path=='/World/Ocean' or path.startswith('/World/Looks/OceanWaterEngineeringV1')
        checks=dict(animal_identical=a['animal']==b['animal'],camera_matrices_within_1e_6=matrix_difference(a,b)<=1e-6,
            effective_camera_product_equal=same_settings(controls_a,controls_b),global_settings_equal=same_settings(a['global_settings'],b['global_settings']),
            top_ocean_unchanged=a['ocean_top_points_unchanged'] and b['ocean_top_points_unchanged'],
            changed_scene_prims_confined_to_water=all(allowed(path) for path in changed),
            direct_geometric_bbox_unchanged=bool(np.allclose(a['direct_geometric_bbox_xyxy_px'],b['direct_geometric_bbox_xyxy_px'],atol=1e-6,rtol=0)))
        assert all(checks.values()),(pose,checks,changed)
        old=np.asarray(Image.open(folders['original_'+pose]/'review_log.png'))
        new=np.asarray(Image.open(folders['engineering_'+pose]/'review_log.png'))
        x0,y0,x1,y1=a['direct_geometric_bbox_xyxy_px']
        x0,y0,x1,y1=max(0,int(x0)),max(0,int(y0)),min(512,int(np.ceil(x1))),min(384,int(np.ceil(y1)))
        crop=np.abs(old[y0:y1,x0:x1].astype(float)-new[y0:y1,x0:x1].astype(float))
        pairs[pose]=dict(checks=checks,changed_scene_prims=changed,direct_geometric_bbox_xyxy_px=a['direct_geometric_bbox_xyxy_px'],
            review_log_box_mean_absolute_difference_8bit=float(crop.mean()),review_log_box_p99_difference_8bit=float(np.percentile(crop,99)),
            annotation_interpretation='The direct projected geometric box is unchanged while water-dependent visible pixels differ. This is not a visible-mask, contour-displacement or annotation-validity measurement.')
    repeat={}
    for reference,candidate in (('engineering_intersecting','reload_intersecting'),('original_intersecting','rollback_intersecting')):
        a,b=records[reference],records[candidate]
        source_controls=load(folders[reference]/'effective_settings.json')
        replay_controls=load(folders[candidate]/'effective_settings.json')
        picking_id_change={label:control['render_product'].get('viewPickingId') for label,control in
                           (('reference',source_controls),('candidate',replay_controls))}
        # A fresh view has its own picking identity. Retain the raw inventory
        # and report this one non-RGB/HDR identity separately; compare all
        # physical/colour/camera/product controls without any other exclusions.
        for control in (source_controls,replay_controls):
            control['render_product'].pop('viewPickingId',None)
        controls_equal=same_settings(source_controls,replay_controls)
        checks=dict(animal_identical=a['animal']==b['animal'],camera_matrix_within_1e_6=matrix_difference(a,b)<=1e-6,
                    effective_controls_equal=controls_equal,global_settings_equal=same_settings(a['global_settings'],b['global_settings']),
                    material_binding_equal=a['bound_material']==b['bound_material'],ocean_vertex_count_equal=a['ocean_vertices']==b['ocean_vertices'],
                    scene_input_hashes_equal=a['scene_state']==b['scene_state'])
        image=metrics(read(folders[reference]/'hdr_display.png'),read(folders[candidate]/'hdr_display.png'))
        repeat[candidate]=dict(checks=checks,image=image,view_picking_identity=picking_id_change,
            comparison_scope='Only process/view picking identity excluded from RGB/HDR control equality; raw inventories retained',
            passed=all(checks.values()) and image['image_tolerance_passed'])
        assert repeat[candidate]['passed'],repeat[candidate]
    result=dict(pair_invariants=pairs,reload_and_rollback=repeat,
        independent_dimensions=all_dimensions,all_pair_invariants_passed=True,all_reload_rollback_checks_passed=True,
        material_only_claim_scope='Animal/camera/lights/top-water invariant; water material and required side/bottom enclosure differ',
        primary_display='Fixed M5 gamma mapping from native HDR, scale 12000 and gamma 2.2',
        human_review_display='Additional fixed log1p HDR mapping / log1p(12000); not native RGB',
        visible_mask_validation=False,annotation_definitions_changed=False,human_review_status='pending',reviewer='MAR',
        failed_in_process_reload_preserved=True,reload_qualification='Fresh process; original in-process attach did not complete',
        capture_directories={name:str(path.relative_to(ROOT)) for name,path in folders.items()},
        m4_complete=False,full_sprint_complete=False)
    destination.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('pair_invariants','reload_and_rollback','independent_dimensions')},indent=2))
    for key,value in pairs.items():
        print('PAIR',key,'crop MAD',value['review_log_box_mean_absolute_difference_8bit'])
    for key,value in repeat.items():
        print(key,value['image']['comparisons'])


if __name__=='__main__':
    main()
