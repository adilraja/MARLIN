"""Prepare audit evidence and proposed declarations; no renderer/scene mutation."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import shutil
import sys

import numpy as np

REPO = Path(__file__).resolve().parents[4]
BASE = REPO / 'experiments/above_water_annotation_v1'
OLD = REPO / 'experiments/gama_dolphin_behaviour_v1'
SOURCE = REPO / 'source/extensions/cris.madil.render_service/cris/madil/render_service'


def write(path, value):
    destination = BASE / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def pin(path):
    path = Path(path)
    path = path if path.is_absolute() else REPO / path
    assert not set(path.parts) & {'_build', 'extscache', '__pycache__', '.cache'}
    assert path.suffix != '.pyc'
    data = path.read_bytes()
    return dict(path=str(path.relative_to(REPO)), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def main():
    stamp = datetime.now(timezone.utc).isoformat()
    index = json.loads((OLD/'qa/m5/frozen_state_index.json').read_text())
    plan = json.loads((OLD/'qa/m5/locked_plan_v3.json').read_text())
    poses = []
    cameras = []
    # Import the existing renderer-independent camera mathematics only.
    spec = importlib.util.spec_from_file_location('_above_water_audit_camera_math', SOURCE/'calibration_geometry.py')
    camera_math = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = camera_math
    spec.loader.exec_module(camera_math)
    for name, seconds in [('A', 6.), ('B', 30.)]:
        snapshot = next(q for q in index['snapshots'] if q['simulation_time_s'] == seconds)
        state = json.loads((REPO/snapshot['state_file']['path']).read_text())
        points = np.load(REPO/snapshot['evaluated_skin_file']['path'])['points_m']
        low, high = points.min(axis=0), points.max(axis=0)
        # Conservative bound: 40 scene units * .01 m/unit * sum(.52,.25,.15,.08).
        wave_bound = .4
        offsets = dict(exposed=float(wave_bound+.25-low[1]),
                       interface=float(-(low[1]+high[1])/2),
                       submerged=float(-wave_bound-.25-high[1]))
        assert float((high[1]-low[1])/2-wave_bound) > .01
        roots = np.asarray(state['root_matrix'])
        anchor = [float(roots[3, 0]*.01), float(roots[3, 2]*.01)]
        pose = dict(id=name, simulation_time_s=seconds, source_run='m3_ref_a01',
                    phase=snapshot['phase'], weight=snapshot['weight'],
                    source_index=snapshot['source_prefix_last_index'],
                    state=pin(snapshot['state_file']['path']), scene=pin(snapshot['scene_file']['path']),
                    evaluated_skin=pin(snapshot['evaluated_skin_file']['path']), vertices=len(points),
                    root_matrix=state['root_matrix'], body_fingerprint=state['body_fingerprint'],
                    source_bounds_m=dict(minimum=low.tolist(), maximum=high.tolist()),
                    anchor_xz_m=anchor, placement_y_offsets_m=offsets,
                    guaranteed_interface_vertex_clearance_m=float((high[1]-low[1])/2-wave_bound),
                    translation_policy='Only recorded Y offset; original X/Z, root attitude, scale and evaluated body pose retained')
        poses.append(pose)
        for view, pitch in [('nadir', 0), ('oblique', 40)]:
            config = camera_math.CalibrationConfig(meters_per_scene_unit=.01,
                image_width_px=512, image_height_px=384, focal_length_mm=35,
                pixel_pitch_um=60, height_above_target_m=8,
                target_width_m=1, target_height_m=1, target_plane_y_m=0,
                pitch_deg=pitch, roll_deg=0)
            p = config.camera_position()
            cameras.append(dict(id=f'{name}_{view}', pose=name, view=view,
                position_m=[anchor[0]+p[0], p[1], anchor[1]+p[2]],
                look_at_m=[anchor[0], 0, anchor[1]], pitch_from_nadir_deg=pitch,
                roll_deg=0, focal_length_mm=35, horizontal_aperture_mm=30.72,
                vertical_aperture_mm=23.04, resolution_px=[512,384],
                fx_px=35/.06, fy_px=35/.06, cx_px=256, cy_px=192,
                near_m=.01, far_m=50, fstop=0, pixel_aspect=1,
                data_window_ndc=[0,0,1,1], zero_distortion_engineering_assumption=True,
                minimum_camera_height_over_global_wave_envelope_m=7.6))
    write('baseline/selected_poses.json', dict(created_utc=stamp, poses=poses,
        waveform_bound_source=pin(SOURCE/'ocean.py'), wave_absolute_height_bound_m=.4,
        wave_bound_reason='Existing four amplitudes sum to wave_height=40 scene units at .01 m/unit; this conservative global bound also bounds interpolated top triangles',
        clearance_note='Vertex signs are guaranteed by the envelope for these proposed placements. M2/M3 must still verify actual render-purpose triangles, enclosure and surface exposure after construction.'))
    water = [dict(id='dry', medium='none', phase_s=None),
             dict(id='clear_flat', medium='private clear clone: transmission_colour=[1,1,1], scattering=[0,0,0]', phase_s=0),
             dict(id='engineering_flat', medium='engineering_v1; private flat top and matching closed boundary', phase_s=0),
             dict(id='wave_0', medium='engineering_v1; existing wave configuration', phase_s=0),
             dict(id='wave_1p25', medium='engineering_v1; existing wave configuration', phase_s=1.25)]
    matrix = []
    for w, pose, placement, view in itertools.product(water, poses, ['exposed','interface','submerged'], ['nadir','oblique']):
        matrix.append(dict(id=f"marine_{w['id']}_{pose['id']}_{placement}_{view}",
            block='marine', water=w['id'], pose=pose['id'], placement=placement,
            view=view, camera=f"{pose['id']}_{view}", y_offset_m=pose['placement_y_offsets_m'][placement],
            family=f"pose_{pose['id']}_{placement}", status='planned_not_executed'))
    def row(w,p,x,v):
        return next(r['id'] for r in matrix if (r['water'],r['pose'],r['placement'],r['view'])==(w,p,x,v))
    replay = [row(w['id'],p,x,v) for w in water
              for p,x,v in [('A','exposed','nadir'),('B','submerged','oblique')]]
    replay += [row('wave_0','A','interface','oblique'),row('wave_1p25','B','interface','nadir')]
    review = [row(w, 'A' if (i+j+k)%2==0 else 'B', x, v)
              for i,w in enumerate(['wave_0','wave_1p25'])
              for j,x in enumerate(['exposed','interface','submerged'])
              for k,v in enumerate(['nadir','oblique'])]
    sentinel = sorted(set(replay+review))
    fixtures = ['fiducial_visible','fiducial_half_occluded','fiducial_fully_occluded',
                'fiducial_image_clipped','fiducial_out_of_frame','target_absent','animal_A','animal_B']
    dry = [dict(id=f'dry_{f}_{v}', block='dry', fixture=f, view=v,
                family=f'dry_fixture_{f}',status='planned_not_executed')
           for f,v in itertools.product(fixtures,['nadir','oblique'])]
    sync = [dict(id=f'sync_{i:02}_{v}',block='synchronisation',sample_time_s=t,
                 view=v, source_run='m3_ref_a01', water='dry',
                 frozen_ocean_reference_phase_s=[0,1.25][i%2],family='m3_ref_a01_sync',
                 status='planned_not_executed') for i,t in enumerate([6,10,16,22,30,38.25,56,64.25])
            for v in ['nadir','oblique']]
    absent = [dict(id=f'absent_{w}_{v}', block='marine_absent',water=w,view=v,
                   counterpart=row(w,'A','interface',v),status='planned_not_executed')
              for w,v in itertools.product(['engineering_flat','wave_1p25'],['nadir','oblique'])]
    repeat = [dict(id='repeat_'+q, block='repeat',primary=q,status='planned_not_executed') for q in replay]
    fresh = [dict(id='reload_'+q, block='fresh_process',primary=q,status='planned_not_executed') for q in replay]
    declaration = dict(version='above_water_capture_declaration_v1', proposed_at_gate_a=True,
        execution_authorised=False, created_utc=stamp, source_poses=poses, cameras=cameras,
        water_conditions=water, ocean_configuration=plan['ocean']['configuration'],
        dry_fixture_geometry=dict(fiducial='1 m opaque square on Y=0, plus 4 corner/centre landmarks',
            partial_occluder='Opaque rectangle in camera-facing plane at 3 m camera depth, covering left half of projected fiducial; analytic ray-plane reference',
            full_occluder='Same depth, covers fiducial plus 8 px projected margin',
            image_clipped='Fixture translated to place its centre on right image edge',
            out_of_frame='Fixture translated to put its nearest projected edge at least 16 px outside image',
            fixture_transform_rule='Record exact world corners from audited camera basis before rendering; no threshold fitted to output'),
        marine=matrix,dry=dry, repeat=repeat, fresh_process=fresh, synchronisation=sync,marine_absent=absent,
        marine_sentinel_ids=sentinel, marine_named_review_ids=review,
        planned_bundles=sum(map(len,[matrix,dry,repeat,fresh,sync,absent])),
        reserve_bundles=24,total_attempt_cap=144,m1_new_captures=0,
        reserved_diagnostics=[dict(id=f'flat_fiducial_{w}_{v}',count=1)
            for w,v in itertools.product(['dry','clear_flat','engineering_flat'],['nadir','oblique'])],
        attempt_accounting='Any started capture consumes an attempt; retained metadata failures without rendering consume no bundle. Diagnostics/retries consume reserve, including future repeated setup failures after capture starts.',
        no_split_or_training=True)
    assert declaration['planned_bundles']==120 and len(replay)==len(review)==12
    write('declarations/capture_declaration.json',declaration)
    contract=dict(schema_version='1.0.0',status='proposed_gate_a_not_implemented',
        target=dict(instance_key='Bottlenose_001',class_name='bottlenose_dolphin_model61a_engineering',
            planned_owned_root='/MarlinGamaBottlenose/Bottlenose_001', scope='Existing v3 owned namespace in a private frozen scene; one animal; unrelated wildlife excluded',
            asset=pin('assets/cetaceans/model_61a_-_bottlenose_dolphin/usd/model_61a_-_bottlenose_dolphin.usd'),
            license=pin('assets/cetaceans/model_61a_-_bottlenose_dolphin/source/license.txt'),
            source_meshes=[f'/MarlinGamaBottlenose/Bottlenose_001/Model/Sketchfab_model/root/GLTF_SceneRootNode/Armature_20/GLTF_created_0/{tail}'
                           for tail in ['Object_7/Object_0','Object_8/Object_1']],
            mesh_audit='Two skinned meshes / 21504 vertices / 40208 faces / one 20-joint skeleton; no Icosphere present in the accepted composed asset. Revalidate composition in private fixture.',
            calibration=dict(model_rotation_deg_xyz=[-90,0,0], scale_at_scene_unit_001=100,
                             biological_size_calibration=False)),
        required_products=['hdr_linear_float_array','hdr_exr','fixed_reinhard_display',
            'direct_amodal_geometry_box','native_instance_mask','mask_derived_tight_box'],
        optional_diagnostic_products=['native_tight_box'],
        image_coordinates=dict(origin='top-left pixel edge',pixel_centres='(column+.5,row+.5)',
            mask_dtype='uint32 raw IDs', mask_box='[xmin,ymin,xmax_exclusive,ymax_exclusive]',
            empty_box=None, raw_native_coordinates='Retain unchanged; inclusivity must be established with M2 fixtures before conversion'),
        direct_geometry=dict(source='Evaluated skinned render-purpose triangles with complete transforms at one simulation time',
            clipping='Homogeneous frustum/near clipping required for crossing triangles; reject unsupported cases explicitly',
            occlusion=False, refraction=False, world_aabb_box='Separate provenance/name if used as diagnostic'),
        identity=dict(native_numeric_ids_stable=False,
            required_mapping=['native_id','owned_instance_key','prim_path','semantic_labels','render_product','frame_or_locked_state_key'],
            inherited_labels='Record actual mesh mappings; union only IDs resolving to the two owned render meshes, never all objects of the same class; no segmentation provider enablement occurred in M1'),
        state_fields=['scene_present','direct_frustum_intersection','native_target_pixel_count',
            'identity_mapping_valid','reviewed_body_appearance','uncertainty_region',
            'product_qualification','failure_reason'],
        null_policy='Unavailable/unsupported results are null plus status/reason; never fake empty mask, zero visibility or physical absence',
        body_appearance='Direct and qualified transmitted/refracted body only; exclude reflections/shadows/glints/caustics/wakes',
        display='round(255*(max(rgb,0)/(1+max(rgb,0)))**(1/2.2)) with one fixed mapping; alpha excluded from RGB metrics',
        synchronisation=dict(preferred='One product, one frame and immutable stage for HDR/EXR/mask; native frame key retained where supported',
            existing_gap='capture_hdr schedules inventory, float buffer and EXR separately; frame_info is received but discarded by existing inventory helper',
            fallback='Immutable state hash plus alternating-state stale-frame test; weaker guarantee explicitly reviewed, no fabricated frame IDs',
            time_owner='Explicit accepted simulation time; no timeline, network or settling-clock advancement',
            native_ids='Per-frame mapping normalized to instance identity for comparison only'),
        bundle_required=['schema_version','declaration_sha256','source_commit','source_pins','attempt_id',
            'fixture_family','source_run_and_sample','root_joint_skin_state','ocean_phase_and_points',
            'camera_and_product','renderer_settings','hdr_domain_and_display','raw_native_outputs',
            'id_mappings','converted_boxes','presence_uncertainty_qualification','resources','files_sha256'],
        compatibility='Existing HTTP endpoint schemas and previous annotations remain unchanged; no endpoint added during M1')
    write('contracts/capture_contract.json',contract)
    accepted=json.loads((OLD/'animation/m4_acceptance_v1.json').read_text())
    criteria=dict(version='above_water_acceptance_v1',status='proposed_for_gate_a_locked_before_candidate_runs',
        reference_basis='Engineering limits selected before new candidate renders; not optical or sensor certification',
        geometry=dict(camera_fiducial_max_error_px=1, dry_wrong_core_pixels=0,
            dry_reference_boundary_band_px=1,native_box_max_edge_error_px=1,
            mask_derived_box_error_px=0,empty_control_target_pixels=0,stale_bundles=0,mapping_errors=0,
            flat_clear_oblique_transmitted_landmark_max_error_px=2),
        replay={k:accepted[k] for k in ['root_position_error_m','root_matrix_component_error',
            'joint_matrix_component_error','skinned_vertex_repeat_error_m','phase_error_cycles']},
        environment=dict(camera_matrix_component_error=1e-8,ocean_point_max_error_m=2e-6,
            normal_component_error=2e-6,wave_phase_error_s=1e-9,topology_exact=True,
            material_and_light_parameters_exact=True,allowed_volatile=['native numeric ID with valid retained mapping','render-product viewPickingId','process/frame counter values']),
        label_repeat=dict(remapped_mask_min_iou=.995,max_box_edge_error_px=1,
            wrong_pixels_outside_one_pixel_boundary_band=0,empty_mask_equality='Both empty -> equal; only one empty -> fail'),
        rgb_repeat=dict(regions=['whole RGB image','union of corresponding primary/repeat direct boxes expanded by 8 px, clipped to image'],
            display_mae_max_levels=2, display_p99_abs_error_max_levels=12,
            fraction_rgb_components_abs_error_over_32_max=.001,
            hdr_relative_mae_max=.05,hdr_p99_absolute_error_over_primary_p99_max=.10,
            denominator_floor=1e-6, maximum_error='Always report; not an equality claim',
            no_per_capture_fitting=True),
        marine_review=dict(required_rows=review,
            reviewer_marks='Confident body foreground F, definite non-body background B, uncertain U on fixed display; body reflections excluded',
            uncertainty_max_fraction_of_F_union_U=.20,
            missed_confident_body_max_fraction_of_F=.02,
            labelled_definite_background_max_fraction_of_F=.02,
            require_nonempty_F_for_positive_qualification=True,
            boundary_report_px=2, independent_clear_fiducial_uses_analytic_reference=True,
            ambiguous_or_empty_positive='Unqualified/ambiguous, not a manufactured absence or passed mask'),
        resources=dict(resolution_px=[512,384],maximum_render_products=1,
            minimum_free_gpu_before_allocation_mib=2048,minimum_free_gpu_during_capture_mib=768,
            guard_rule='Use stricter current guard if raised; the 2048 MiB admission threshold is a conservative proposal, not a measured annotator allocation',
            capture_timeout_s=90,settling_delivered_frames=64,settling_timeout_s=45,
            transaction_timeout_s=600,startup_timeout_s=120,cleanup_timeout_s=30,
            max_delivered_settle_frames=128,max_rendered_bundles_per_transaction=6,
            minimum_free_disk_bytes=10*1024**3,maximum_incremental_evidence_bytes=5*1024**3,
            baseline_capture_budget=4,attempt_cap=144,reserve=24),
        dry_reference='Analytic plane/cube ray intersection and independent triangle raster cross-check, not native-mask/native-box agreement alone',
        failures='No tolerance relaxation after seeing candidate result. Amend at review gate before new acceptance version; preserve original failure.',
        dependency_stop='If native provider is not locally available, stop before package installation or an unqualified fallback; prepare exact official dependency proposal for separate review',
        lifecycle_stop='Resolve finite startup/shutdown and clean owned-product teardown before capture; retained M1 probe timeout is not a passed lifecycle test')
    write('contracts/acceptance_plan.json',criteria)
    evidence_paths=[OLD/'SPRINT_STATUS.json',OLD/'M6_GATE_D_ACCEPTANCE.md',
        OLD/'reviews/MAR_GATE_D_2026_11_05_acceptance_manifest.json',OLD/'m4_manifest.json',OLD/'m5_manifest.json',OLD/'m6_manifest.json',
        OLD/'qa/m5/frozen_state_index.json',OLD/'qa/m5/locked_plan_v3.json',OLD/'animation/m4_acceptance_v1.json',
        REPO/'Sprints/CurrentSprint/MARLIN_ABOVE_WATER_CAPTURE_ANNOTATION_VALIDATION_SPRINT_SPECIFICATION.md',
        REPO/'Sprints/CurrentSprint/MARLIN_GAMA_BOTTLENOSE_BEHAVIOUR_ANIMATION_SPRINT_SPECIFICATION.md',
        REPO/'Sprints/PastSprints/MARLIN_GAMA_BOTTLENOSE_BEHAVIOUR_ANIMATION_SPRINT_SPECIFICATION.md',
        REPO/'experiments/ocean_material_v1/OCEAN_MATERIAL_SPRINT_CLOSEOUT.md',
        REPO/'experiments/ocean_material_v1/diagnostics/m6/manifest.json',
        REPO/'experiments/ocean_material_v1/diagnostics/m6/review_state.json',
        REPO/'experiments/ocean_material_v1/diagnostics/m6/reviews/MAR_2026_11_03.json',
        REPO/'integrations/gama/DATASET_CAPTURE_V2.md',
        OLD/'M1_ASSET_AND_CONTROLLER_AUDIT.md',OLD/'baseline/live_before/rig_Dolphin_001.json',
        REPO/'source/extensions/cris.madil.gama_bridge/config/model61a_engineering_v1.json']
    for q in json.loads((OLD/'m5_manifest.json').read_text())['asset_dependencies']:
        evidence_paths.append(REPO/q['path'])
    preset=REPO/'experiments/ocean_material_v1/presets/engineering_v1'
    evidence_paths += [p for p in preset.iterdir() if p.is_file()]
    evidence_paths += [SOURCE/'water_medium_diagnostics.py',SOURCE/'capture_projection.py',SOURCE/'hidef_marine.py',
                       SOURCE/'capture_state.py',SOURCE/'scene_diagnostics.py',SOURCE/'ocean.py',SOURCE/'ocean_medium.py']
    images=[]
    for seconds,name in [(6.,'shallow_6s'),(30.,'descent_30s'),(38.25,'submerged_38p25s')]:
        q=next(q for q in index['snapshots'] if q['simulation_time_s']==seconds)
        folder=REPO/q['directory'];image=folder/'review_reinhard.png'
        dest=BASE/'baseline/images'/f'{name}.png';dest.parent.mkdir(exist_ok=True)
        shutil.copyfile(image,dest)
        assert pin(image)['sha256']==pin(dest)['sha256']
        images.append(dict(source=pin(image),copy=pin(dest),source_state=pin(folder/'state.json'),
            scene=pin(folder/'scene.usdc'),hdr=pin(folder/'hdr.npz'),
            historical_capture=True,new_render=False,display=contract['display']))
        evidence_paths += [folder/'state.json',folder/'scene.usdc',folder/'hdr.npz',folder/'hdr.exr',image]
    write('baseline/representative_images.json',dict(images=images,new_rendered_bundles=0))
    write('baseline/evidence_pins.json',dict(recorded_utc=stamp,files=[pin(p) for p in sorted(set(evidence_paths))]))
    summary=dict(schema_version=1,status='audit_prepared_gate_a_pending',reviewer=None,gate_a_accepted=False,
        contract_version=contract['schema_version'],source_head=(BASE/'baseline/git_head.txt').read_text().strip(),
        new_rendered_bundles=0,annotations_enabled=False,production_implementation_changed=False,
        metadata_probe='Returned build/USD/224 registered extensions; no Replicator/SyntheticData entry; later hit 120 s shutdown deadline and owned group was terminated',
        unresolved=['Native segmentation provider not registered in this installation/profile',
                    'Probe process shutdown timed out; no clean lifecycle established',
                    'No same-frame HDR/EXR/annotation capture path currently verified',
                    'Marine annotation/refraction support untested'],
        proposal='After Gate A, first perform isolated native-provider feasibility and clean lifecycle checks. No package install or main runtime upgrade is included in Gate A acceptance; bring a concrete dependency proposal if required.',
        separate_ocean_material_m4='open')
    write('SPRINT_STATUS.json',dict(sprint='MARLIN — Above-Water Capture and Annotation Validation',
        recorded_utc=stamp,milestones={'M1':'audit_ready_for_gate_a','M2':'not_started','M3':'not_started','M4':'not_started','M5':'not_started','M6':'not_started'},
        sprint_closed=False,gate_a='pending',reviewer=None,implementation_authorised=False,
        separate_ocean_material_m4='open'))
    write('reviews/gate_a_review.json',dict(gate='A',status='pending',reviewer=None,accepted=False,
        acceptance_received=False,evidence_version='above_water_m1_audit_v1',limitations=summary['unresolved']))
    write('qa/m1/preparation_summary.json',summary)
    write('declarations/attempt_ledger.json',dict(planned=120,maximum=144,reserve=24,
        rendered_attempts=[],rendered_attempts_used=0,metadata_processes=1,
        note='M1 metadata launch/shutdown failure retained separately; it performed zero captures.'))
    print(json.dumps(dict(poses=[p['id'] for p in poses],planned=120,
        marine_sentinel=len(sentinel),review_rows=len(review),historical_images=3,new_captures=0)))


if __name__ == '__main__':
    main()
