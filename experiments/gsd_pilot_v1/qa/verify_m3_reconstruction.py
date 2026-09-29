"""Verify semantic USD reconstruction and actual animation, using Blender USD."""
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
import numpy as np
from pxr import Usd, UsdGeom, UsdSkel
ROOT=Path(__file__).resolve().parents[3]
EXP=ROOT/'experiments/gsd_pilot_v1'
sys.path.insert(0,str(EXP/'scenes'))
from build_scenes import (open_private, points, sha, TARGET, CAMERA, save,
                          make_scene, set_camera, biological_record)


EXPECTED_SCENE_IDS = {
    'european_storm_petrel_0000', 'european_storm_petrel_0024',
    'harbour_porpoise_0000', 'harbour_porpoise_0024',
}
EXPECTED_PREVIEW_NAMES = {
    'Bottlenose_Carimam', 'Cuvier_Whale', 'Frasers_Dolphin',
    'Humpback_Whale', 'Manatee', 'Bottlenose_DigitalLife',
    'Spotted_Dolphin', 'Pilot_Whale', 'Pygmy_Sperm_Whale',
    'Sperm_Whale', 'Steno_Dolphin',
}


def _named_records(records, key, expected, label):
    if type(records) is not list or len(records) != len(expected):
        raise ValueError(label + ': missing or extra records')
    names = [record.get(key) if type(record) is dict else None for record in records]
    if any(type(name) is not str for name in names) or set(names) != expected or len(set(names)) != len(names):
        raise ValueError(label + ': unknown, missing, or duplicate identifiers')
    return {record[key]: record for record in records}


def validate_replay_coverage(index_records, live):
    """Require all four representatives, two independent runs, and both phases."""
    index = _named_records(index_records, 'scene_id', EXPECTED_SCENE_IDS, 'Snapshot index')
    if type(live) is not dict:
        raise ValueError('Replay evidence must be an object')
    entries = _named_records(live.get('results'), 'scene_id', EXPECTED_SCENE_IDS, 'Live replay')
    checkpoint_ids = set()
    for entry in entries.values():
        runs = entry.get('runs')
        if type(runs) is not list or len(runs) != 2 or any(type(run) is not dict for run in runs):
            raise ValueError('Each representative requires two runs')
        attempts = [run.get('attempt') for run in runs]
        if any(type(attempt) is not int for attempt in attempts) or set(attempts) != {0, 1}:
            raise ValueError('Runs must contain unique integer attempts 0 and 1')
        for run in runs:
            for phase in ('immediate', 'after_wait'):
                checkpoint = run.get(phase)
                if type(checkpoint) is not dict or checkpoint.get('ok') is not True:
                    raise ValueError('Missing or failed replay checkpoint: ' + phase)
                identifier = checkpoint.get('checkpoint_id')
                if type(identifier) is not str or not identifier.startswith('checkpoint_') or identifier in checkpoint_ids:
                    raise ValueError('Replay checkpoints must have unique recorded identifiers')
                checkpoint_ids.add(identifier)
    if len(checkpoint_ids) != 16:
        raise ValueError('Expected sixteen independent live checkpoint observations')
    return index


def validate_preview_coverage(report):
    """Require exactly the default eleven animals before and after animation."""
    if type(report) is not dict or report.get('passed') is not True or report.get('swim_started') is not True:
        raise ValueError('Animated preview did not report successful swimming')
    if type(report.get('gallery_loaded_count')) is not int or report['gallery_loaded_count'] != 11:
        raise ValueError('Animated preview must load eleven animals')
    for phase in ('before', 'after'):
        phase_record = report.get(phase)
        gallery = phase_record.get('gallery') if type(phase_record) is dict else None
        animals = gallery.get('animals') if type(gallery) is dict else None
        _named_records(animals, 'name', EXPECTED_PREVIEW_NAMES, 'Preview ' + phase)
    return True


def equal(a,b):
    if a is None or b is None:return a is b
    if isinstance(a,dict) or isinstance(b,dict):
        return isinstance(a,dict) and isinstance(b,dict) and a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
    if isinstance(a,(tuple,list)) or isinstance(b,(tuple,list)):
        return isinstance(a,(tuple,list)) and isinstance(b,(tuple,list)) and len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
    if isinstance(a,bool) or isinstance(b,bool):return type(a)==type(b) and a==b
    try:
        x,y=np.asarray(a),np.asarray(b)
        if x.dtype.kind in 'fiu' and y.dtype.kind in 'fiu':
            return x.shape==y.shape and bool(np.allclose(x,y,rtol=1e-7,atol=1e-6,equal_nan=False))
    except (TypeError,ValueError):pass
    return str(a)==str(b)


def validate_scene(expected, actual):
    if UsdGeom.GetStageMetersPerUnit(actual)!=.01 or UsdGeom.GetStageUpAxis(actual)!='Y':raise ValueError('Units differ')
    expected_prims={str(p.GetPath()):p for p in expected.Traverse() if str(p.GetPath()).startswith('/World')}
    actual_prims={str(p.GetPath()):p for p in actual.Traverse() if str(p.GetPath()).startswith('/World')}
    if expected_prims.keys()!=actual_prims.keys():raise ValueError('Prim structure changed: '+str(expected_prims.keys()^actual_prims.keys()))
    checked=0
    for path,p in expected_prims.items():
        q=actual_prims[path]
        if p.GetTypeName()!=q.GetTypeName():raise ValueError('Prim type changed: '+path)
        if {a.GetName() for a in p.GetAuthoredAttributes()}!={a.GetName() for a in q.GetAuthoredAttributes()}:
            raise ValueError('Authored attribute set changed: '+path)
        if {r.GetName() for r in p.GetAuthoredRelationships()}!={r.GetName() for r in q.GetAuthoredRelationships()}:
            raise ValueError('Authored relationship set changed: '+path)
        for attr in p.GetAuthoredAttributes():
            other=q.GetAttribute(attr.GetName())
            if not other or not equal(attr.Get(),other.Get()):
                raise ValueError('Attribute changed: '+str(attr.GetPath()))
            if attr.GetConnections()!=other.GetConnections():raise ValueError('Connections changed')
            checked+=1
        for rel in p.GetRelationships():
            other=q.GetRelationship(rel.GetName())
            if rel.GetTargets()!=(other.GetTargets() if other else []):raise ValueError('Relationship changed: '+str(rel.GetPath()))
    if any(a.GetNumTimeSamples() for p in actual.Traverse() for a in p.GetAttributes()):raise ValueError('Snapshot retains time samples')
    error=float(np.max(np.abs(points(expected)-points(actual))))
    if error>1e-5:raise ValueError('World mesh replay error: '+str(error))
    ocean=UsdGeom.Mesh(actual.GetPrimAtPath('/World/Ocean'))
    if np.max(np.abs(np.asarray(ocean.GetPointsAttr().Get())[:,1]))>1e-7:raise ValueError('Ocean is not flat')
    lights=[str(p.GetPath()) for p in actual.Traverse() if p.GetTypeName().endswith('Light')]
    if set(lights)!={'/World/Environment/Sky','/World/Environment/Sun'}:raise ValueError('Undeclared lights')
    if actual.GetPrimAtPath('/World/Environment/Sun').GetAttribute('inputs:intensity').Get()!=0:raise ValueError('Sun is active')
    return {'passed':True,'world_geometry_max_error_m':error,'authored_attributes_checked':checked,
            'time_samples':0,'declared_lights_only':True,'flat_ocean':True}


def checkpoint_stage(record):
    path=Path(record['directory'])/'scene.usdc'
    if sha(path)!=record['scene_sha256']:raise ValueError('Live checkpoint hash mismatch')
    return open_private(path)


def pose_points(stage,name):
    root=stage.GetPrimAtPath('/World/Cetaceans/'+name)
    inverse=UsdGeom.Xformable(root).ComputeLocalToWorldTransform(Usd.TimeCode.Default()).GetInverse()
    result=[]
    for p in sorted(Usd.PrimRange(root),key=lambda p:str(p.GetPath())):
        if p.IsA(UsdGeom.Mesh):
            local=np.asarray(UsdGeom.Mesh(p).GetPointsAttr().Get(),dtype=float)
            matrix=np.asarray(UsdGeom.Xformable(p).ComputeLocalToWorldTransform(Usd.TimeCode.Default())*inverse)
            result.append((np.column_stack([local,np.ones(len(local))])@matrix)[:,:3])
    return np.concatenate(result)


def preview_validation():
    report=json.loads((EXP/'qa/milestone_3_animation_preview.json').read_text())
    validate_preview_coverage(report)
    a=checkpoint_stage(report['before_checkpoint']);b=checkpoint_stage(report['after_checkpoint'])
    # Skin on private stages to include the skeletal dolphin's changing pose.
    if not UsdSkel.BakeSkinning(a.Traverse()) or not UsdSkel.BakeSkinning(b.Traverse()):raise ValueError('Preview skin evaluation failed')
    checks=[]
    for animal in report['after']['gallery']['animals']:
        name=animal['name'];pa,pb=pose_points(a,name),pose_points(b,name)
        delta=float(np.max(np.abs(pa-pb)))
        if delta<=1e-7:raise ValueError('Body geometry did not advance: '+name)
        checks.append({'name':name,'max_local_pose_change_native_units':delta,'body_animation_verified':True})
    oa=np.asarray(UsdGeom.Mesh(a.GetPrimAtPath('/World/Ocean')).GetPointsAttr().Get())
    ob=np.asarray(UsdGeom.Mesh(b.GetPrimAtPath('/World/Ocean')).GetPointsAttr().Get())
    wave_change=float(np.max(np.abs(oa-ob)))
    if wave_change<=1e-6:raise ValueError('Ocean mesh did not advance')
    return {'passed':True,'animals':checks,'max_ocean_point_change_scene_units':wave_change,
            'translation_and_clock_checks':'qa/milestone_3_animation_preview.json'}


def main():
    env=json.loads((EXP/'environment.json').read_text())
    index_records=json.loads((EXP/'scenes/snapshot_index.json').read_text())
    live=json.loads((EXP/'scenes/live_replay.json').read_text())
    index=validate_replay_coverage(index_records,live)
    checks=[]
    reconstruction=[]
    for entry in live['results']:
        source=EXP/index[entry['scene_id']]['snapshot']
        if sha(source)!=index[entry['scene_id']]['sha256']:raise ValueError('Expected snapshot hash mismatch')
        expected=open_private(source)
        manifest=json.loads((EXP/'scenes/manifests'/(entry['scene_id']+'.json')).read_text())
        rebuilt=make_scene(manifest,env)
        fresh=validate_scene(expected,rebuilt)
        identity=biological_record(manifest,sha(EXP/'environment.json'),rebuilt)
        saved_identity=json.loads((source.parent/'biological.json').read_text())
        if identity!=saved_identity or identity['biological_manifest_sha256']!=index[entry['scene_id']]['biological_manifest_sha256']:
            raise ValueError('Biological identity mismatch')
        initial_camera={a.GetName():a.Get() for a in rebuilt.GetPrimAtPath(CAMERA).GetAuthoredAttributes()}
        initial_matrix=np.asarray(UsdGeom.Xformable(rebuilt.GetPrimAtPath(CAMERA)).GetLocalTransformation()).copy()
        for variant in manifest['camera']['variants']:
            set_camera(rebuilt,variant)
            camera=rebuilt.GetPrimAtPath(CAMERA)
            for attr in camera.GetAuthoredAttributes():
                if attr.GetName()!='xformOp:transform' and not equal(attr.Get(),initial_camera[attr.GetName()]):
                    raise ValueError('Paired camera parameter changed: '+attr.GetName())
            matrix=np.asarray(UsdGeom.Xformable(camera).GetLocalTransformation()).copy()
            if abs(matrix[3,1]*.01-variant['position_m'][1])>1e-5:raise ValueError('Camera Y mismatch')
            matrix[3,1]=initial_matrix[3,1]
            if not np.array_equal(matrix,initial_matrix):raise ValueError('Camera changed beyond Y translation')
            if biological_record(manifest,sha(EXP/'environment.json'),rebuilt)['biological_manifest_sha256']!=identity['biological_manifest_sha256']:
                raise ValueError('Camera change affected biological identity')
        reconstruction.append({'scene_id':entry['scene_id'],**fresh,
            'fresh_manifest_reconstruction':True,'all_five_cameras_only_y_changes':True,
            'biological_hash_camera_invariant':True})
        for run in entry['runs']:
            for phase in ['immediate','after_wait']:
                checkpoint=run[phase];actual=checkpoint_stage(checkpoint)
                if checkpoint['camera']!=CAMERA or checkpoint['resolution']!=[1024,768] or checkpoint['fill_frame'] is not False:raise ValueError('Viewport setup changed')
                if not equal(env['renderer_settings'],checkpoint['renderer_settings']):
                    differences={k:[v,checkpoint['renderer_settings'].get(k)] for k,v in env['renderer_settings'].items() if not equal(v,checkpoint['renderer_settings'].get(k))}
                    raise ValueError('Renderer settings changed: '+str(differences))
                checks.append({'scene_id':entry['scene_id'],'attempt':run['attempt'],'phase':phase,**validate_scene(expected,actual),'renderer_settings_preserved':True,'viewport_camera_and_resolution_preserved':True})
    report={'passed':True,'live_snapshot_checks':len(checks),'tolerances':{'world_points_m':1e-5,'attribute_abs':1e-6,'attribute_rel':1e-7},
            'records':checks,'fresh_reconstruction':reconstruction,'animation_preview':preview_validation(),
            'scope':'Geometry, static pose, material/light values, camera and declared renderer state; not RGB repeatability or GSD capture certification'}
    save(EXP/'qa/m3_reconstruction.json',report)
    print(json.dumps({'passed':True,'live_snapshot_checks':len(checks),'actual_animated_bodies':len(report['animation_preview']['animals']),'ocean_mesh_changes':True}))


if __name__=='__main__':main()
