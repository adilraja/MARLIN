"""Read-only verification of the M1 technical packet; never launches Kit."""
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import sys

import numpy as np

REPO = Path(__file__).resolve().parents[4]
BASE = REPO / 'experiments/above_water_annotation_v1'


def read(relative):
    return json.loads((BASE / relative).read_text())


def check(records):
    for item in records:
        relative = Path(item['path'])
        assert not relative.is_absolute() and '..' not in relative.parts
        assert not set(relative.parts) & {'_build', 'extscache', '__pycache__', '.cache'}
        assert relative.suffix != '.pyc'
        data = (REPO / relative).read_bytes()
        assert len(data) == item['bytes'], str(relative)
        assert hashlib.sha256(data).hexdigest() == item['sha256'], str(relative)
    return len(records)


def main():
    manifest = read('manifest.json')
    files = check(manifest['files'])
    source = read('baseline/source_before.json')['files']
    source_count = check(source)
    current_paths = set()
    for root in ['source/apps', 'source/extensions']:
        for p in (REPO/root).rglob('*'):
            if set(p.parts) & {'_build','extscache','__pycache__','.cache'} or p.suffix == '.pyc':
                continue
            if p.is_file():
                current_paths.add(str(p.relative_to(REPO)))
    assert current_paths == {q['path'] for q in source}
    evidence_count = check(read('baseline/evidence_pins.json')['files'])
    declaration = read('declarations/capture_declaration.json')
    blocks = ['marine','dry','repeat','fresh_process','synchronisation','marine_absent']
    counts = {key:len(declaration[key]) for key in blocks}
    assert counts == dict(marine=60,dry=16,repeat=12,fresh_process=12,synchronisation=16,marine_absent=4)
    assert sum(counts.values()) == declaration['planned_bundles'] == 120
    assert declaration['total_attempt_cap'] == 144 and declaration['reserve_bundles'] == 24
    ids = [q['id'] for key in blocks for q in declaration[key]]
    assert len(ids) == len(set(ids))
    assert all(q['status']=='planned_not_executed' for key in blocks for q in declaration[key])
    marine = {q['id']:q for q in declaration['marine']}
    sentinel = [marine[k] for k in declaration['marine_sentinel_ids']]
    assert len(sentinel) == 21
    assert {q['water'] for q in sentinel} == {q['id'] for q in declaration['water_conditions']}
    assert {q['pose'] for q in sentinel} == {'A','B'}
    assert {q['placement'] for q in sentinel} == {'exposed','interface','submerged'}
    assert {q['view'] for q in sentinel} == {'nadir','oblique'}
    reviewed = [marine[k] for k in declaration['marine_named_review_ids']]
    assert len(reviewed) == 12 and {q['pose'] for q in reviewed} == {'A','B'}
    assert {(q['water'],q['placement'],q['view']) for q in reviewed} == set(itertools.product(
        ['wave_0','wave_1p25'],['exposed','interface','submerged'],['nadir','oblique']))
    repeat_ids = {q['primary'] for q in declaration['repeat']}
    assert repeat_ids == {q['primary'] for q in declaration['fresh_process']}
    assert repeat_ids <= marine.keys() and len(repeat_ids) == 12
    assert {marine[q]['water'] for q in repeat_ids} == {q['id'] for q in declaration['water_conditions']}
    runtime = read('baseline/runtime_query.json')
    assert runtime['build_version'] == '110.2.0+feature.342835.698af100.gl'
    assert runtime['usd_version'] == [0,25,11] and runtime['passed']
    assert runtime['extension_inventory_count'] == 224
    assert not [q for q in runtime['extensions'] if q['name'].startswith(('omni.replicator','omni.syntheticdata'))]
    assert read('baseline/runtime_probe_process.json')['timed_out']
    assert runtime['captures'] == 0 and not runtime['annotators_enabled_by_probe']
    ledger = read('declarations/attempt_ledger.json')
    assert ledger['rendered_attempts_used']==0 and not ledger['rendered_attempts']
    for image in read('baseline/representative_images.json')['images']:
        check([image[k] for k in ['source','copy','source_state','scene','hdr']])
        assert image['source']['sha256'] == image['copy']['sha256']
        assert image['historical_capture'] and not image['new_render']
    module_path = REPO/'source/extensions/cris.madil.render_service/cris/madil/render_service/calibration_geometry.py'
    spec = importlib.util.spec_from_file_location('_verify_m1_camera_math',module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    proposed = read('qa/m1/proposed_framing.json')
    framing = {(q['pose'],q['placement'],q['view']):q for q in proposed['rows']}
    assert len(framing)==12
    for pose in declaration['source_poses']:
        check([pose[k] for k in ['state','scene','evaluated_skin']])
        state = json.loads((REPO/pose['state']['path']).read_text())
        assert state['simulation_time_s']==pose['simulation_time_s']
        assert abs(state['pose_controls']['phase']-pose['phase'])<=1e-12
        points = np.load(REPO/pose['evaluated_skin']['path'])['points_m']
        assert points.shape==(21504,3)
        assert (np.ptp(points[:,1])/2-.4)>.01
        for placement,offset in pose['placement_y_offsets_m'].items():
            moved = points.copy(); moved[:,1] += offset
            if placement=='exposed': assert moved[:,1].min()>=.65-1e-12
            if placement=='submerged': assert moved[:,1].max()<=-.65+1e-12
            for view,pitch in [('nadir',0),('oblique',40)]:
                camera = module.CalibrationConfig(.01,512,384,35,60,8,1,1,0,pitch,0)
                x,z = pose['anchor_xz_m']
                uv = np.asarray([camera.project((p[0]-x,p[1],p[2]-z)) for p in moved])
                lo,hi=uv.min(axis=0),uv.max(axis=0)
                actual=[*lo.tolist(),*hi.tolist()]
                assert np.max(np.abs(np.array(actual)-framing[(pose['id'],placement,view)]['box_xyxy_px']))<=1e-9
                assert min(lo[0],lo[1],512-hi[0],384-hi[1])>16
    old = read('qa/m1/bottlenose_preservation_verification.json')
    assert old['passed'] and old['status']=='accepted' and old['reviewer']=='MAR'
    ocean = read('qa/m1/ocean_preservation_verification.json')
    assert not ocean['legacy_verifier_passed'] and ocean['immutable_ocean_evidence_and_preset_verified']
    assert len(ocean['superseded_source_pins'])==3
    assert all(q['matches_later_accepted_bottlenose_pin'] for q in ocean['superseded_source_pins'])
    ocean_manifest=json.loads((REPO/'experiments/ocean_material_v1/diagnostics/m6/manifest.json').read_text())
    ocean_files=check(ocean_manifest['files'])
    ocean_checkpoints=check(ocean_manifest['checkpoint_artifacts'])
    preset=json.loads((REPO/'experiments/ocean_material_v1/presets/engineering_v1/manifest.json').read_text())
    preset_files=check(preset['files']);preset_assets=check(preset['local_asset_dependencies'])
    snapshot = read('reviews/gate_a_review_at_seal.json')
    assert snapshot['status']=='pending' and snapshot['reviewer'] is None and not snapshot['accepted']
    current = read('reviews/gate_a_review.json')
    assert current['status'] in ('pending','accepted','changes_requested')
    if current['status']=='pending':
        assert current['reviewer'] is None and not current['accepted']
    elif current['status']=='accepted':
        assert current['reviewer'] and current['acceptance_received'] and current.get('acceptance_record')
        acceptance=read(current['acceptance_record'])
        assert acceptance['reviewer']==current['reviewer'] and acceptance['accepted']
    contract = read('contracts/capture_contract.json')
    assert contract['status']=='proposed_gate_a_not_implemented'
    assert len(contract['target']['source_meshes'])==2
    assert contract['target']['planned_owned_root']=='/MarlinGamaBottlenose/Bottlenose_001'
    return dict(passed=True,scope='M1 evidence/contract audit only; no rendering or annotation validation',
        packet_files_verified=files,canonical_source_files_unchanged=source_count,
        selected_evidence_pins_verified=evidence_count,planned_bundle_counts=counts,
        planned_bundles=120,maximum_attempts=144,new_capture_attempts=0,
        metadata_query_returned=True,probe_shutdown_timed_out=True,
        native_annotation_provider_registered=False,marine_labels_qualified=False,
        framing_combinations_verified=12,minimum_direct_margin_px=proposed['minimum_margin_px'],
        historical_bottlenose_acceptance_preserved=True,
        ocean_evidence_files_verified=ocean_files,ocean_checkpoints_verified=ocean_checkpoints,
        preset_files_verified=preset_files,preset_assets_verified=preset_assets,
        historical_ocean_source_pins_superseded=3,legacy_ocean_verifier_passed=False,
        gate_a=current['status'],reviewer=current['reviewer'],implementation_started=False,
        biological_approval=False,optical_approval=False,research_capture_approval=False,
        separate_ocean_material_m4='open')


if __name__ == '__main__':
    print(json.dumps(main(),indent=2))
