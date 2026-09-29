"""Build frozen pilot USD with existing MARLIN camera geometry; render only in Kit."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
import numpy as np
from pxr import Gf, Sdf, Usd, UsdGeom, UsdSkel

ROOT = Path(__file__).resolve().parents[3]
EXP = ROOT / 'experiments/gsd_pilot_v1'
OUT = EXP / 'scenes'
SOURCE = ROOT / 'source/extensions/cris.madil.render_service/cris/madil/render_service'
sys.path.insert(0, str(SOURCE))
sys.path.insert(0, str(OUT))
from calibration_geometry import CalibrationConfig, build_camera
from sampling import sample_scene, validate_manifest
CAMERA = '/World/Cameras/PilotCamera'
TARGET = '/World/Cetaceans/PilotTarget'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def canonical_sha(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def biological_record(manifest, environment_hash, stage):
    # Rendering cameras are deliberately outside the biological identity.
    biological = {key: manifest[key] for key in ('scene_id', 'species',
        'asset_instance_id', 'sequence_id', 'condition_id', 'animal',
        'calibration', 'random', 'sampling', 'coordinates', 'time')}
    biological.update(environment_sha256=environment_hash,
        target_geometry_sha256=hashlib.sha256(points(stage).astype('<f8').tobytes()).hexdigest(),
        dependencies=dependencies(stage), pose_time_code=1)
    return {'biological_manifest_sha256': canonical_sha(biological),
            'scene_manifest_sha256': manifest['manifest_sha256'],
            'biological': biological, 'camera_excluded_from_biological_hash': True}


def open_private(path):
    return Usd.Stage.Open(Sdf.Layer.OpenAsAnonymous(str(path)))


def environment_record():
    checkpoint = json.loads((OUT / 'base_checkpoint.json').read_text())
    preset_path = ROOT / 'source/extensions/cris.madil.render_service/config/survey_environment_v1.json'
    settings = checkpoint['renderer_settings'].copy()
    overrides = {'/rtx/rendermode': 'PathTracing', '/rtx/pathtracing/spp': 8,
        '/rtx/pathtracing/totalSpp': 128, '/rtx/pathtracing/adaptiveSampling/enabled': False,
        '/rtx/pathtracing/optixDenoiser/enabled': False,
        '/rtx/pathtracing/optixDenoiser/temporalMode/enabled': False,
        '/rtx/pathtracing/cached/enabled': False, '/rtx/pathtracing/lightcache/cached/enabled': False,
        '/rtx/post/histogram/enabled': False, '/rtx/post/motionblur/enabled': False,
        '/rtx/post/dof/enabled': False, '/rtx/post/aa/op': 3}
    for key, value in overrides.items():
        if key not in settings or settings[key] is None:
            raise ValueError('Renderer setting unavailable: ' + key)
        settings[key] = value
    return {'schema_version': '1.0.0', 'preset_id': 'gsd_baseline_v1',
        'source_preset': {'path': str(preset_path.relative_to(ROOT)), 'sha256': sha(preset_path),
                          'values': json.loads(preset_path.read_text())},
        'base_scene': {'path': 'scenes/environment_base.usdc', 'sha256': sha(OUT / 'environment_base.usdc')},
        'stage_units': {'meters_per_unit': .01, 'up_axis': 'Y'},
        'lighting_policy': 'Only /World/Environment/Sky and Sun; remove Kit /Environment/defaultLight; sun intensity zero',
        'renderer_settings': settings, 'renderer_overrides': overrides,
        'unset_settings': [k for k,v in settings.items() if v is None],
        'colour_policy': 'Record and restore installed numeric tonemap/exposure/color settings exactly; no hardware color calibration',
        'external_ocio': {'path': settings.get('/rtx/post/tonemap/ocio/cfgFilePath'), 'status': 'runtime_dependency_not_inspected_or_hashed'},
        'renderer_seed': {'value': None, 'status': 'no_verified_supported_seed_control; biological seed does not control RTX noise'},
        'sampling_status': '128 total spp requested; actual captured samples and RGB repeatability require M4',
        'optical_calibration_claim': False,
        'camera_exposure_attributes': json.loads((OUT / 'renderer_resolution.json').read_text())['camera_exposure_attributes'],
        'engine_managed_setting_resolution': 'scenes/renderer_resolution.json',
        'time_policy': {'pose_time_code': 1, 'authored_time_samples_after_freeze': 0,
                        'live_controllers': 'all_stopped_before_attach; asserted_before_and_after',
                        'timeline': 'all animated data baked at time code 1; timeline position cannot change scene geometry'},
        'camera_clipping_range_scene_units': [1, 100000]}


def make_scene(manifest, environment):
    validate_manifest(manifest)
    if sha(OUT / 'environment_base.usdc') != environment['base_scene']['sha256']:
        raise ValueError('Environment base hash changed')
    stage = open_private(OUT / 'environment_base.usdc')
    if UsdGeom.GetStageUpAxis(stage) != 'Y' or UsdGeom.GetStageMetersPerUnit(stage) != .01:
        raise ValueError('Unexpected scene units')
    for child in list(stage.GetPseudoRoot().GetChildren()):
        if str(child.GetPath()) != '/World':
            stage.RemovePrim(child.GetPath())
    if stage.GetPrimAtPath('/World/Cetaceans'):
        stage.RemovePrim('/World/Cetaceans')
    animal = manifest['animal']
    root = UsdGeom.Xform.Define(stage, TARGET)
    api = UsdGeom.XformCommonAPI(root)
    api.SetTranslate(Gf.Vec3d(*(x / .01 for x in animal['position_m'])))
    api.SetRotate(Gf.Vec3f(0, animal['heading_deg'], 0), UsdGeom.XformCommonAPI.RotationOrderXYZ)
    api.SetScale(Gf.Vec3f(*([animal['scale']] * 3)))
    model = UsdGeom.Xform.Define(stage, TARGET + '/Model')
    model.GetPrim().GetReferences().AddReference(str(ROOT / animal['asset_path']), '/root')
    UsdGeom.XformCommonAPI(model).SetRotate(Gf.Vec3f(*animal['model_rotation_deg']), UsdGeom.XformCommonAPI.RotationOrderXYZ)
    # Flatten before skinning, so geometry writes cannot reach original layers.
    stage = Usd.Stage.Open(stage.Flatten())
    if not UsdSkel.BakeSkinning(stage.Traverse()):
        raise ValueError('Could not bake static target pose')
    for prim in stage.TraverseAll():
        for attr in prim.GetAttributes():
            if attr.GetNumTimeSamples():
                value = attr.Get(Usd.TimeCode(animal['pose_time_code']))
                attr.Clear()
                if value is not None: attr.Set(value)
    stage.SetStartTimeCode(1); stage.SetEndTimeCode(1)
    variant = manifest['camera']['variants'][0]
    set_camera(stage, variant)
    return stage


def set_camera(stage, variant):
    c = CalibrationConfig(meters_per_scene_unit=.01, image_width_px=1024,
        image_height_px=768, focal_length_mm=50, pixel_pitch_um=5,
        height_above_target_m=variant['separation_m'], target_plane_y_m=variant['reference_plane_y_m'],
        target_width_m=2, target_height_m=1)
    # Dimensions above solely satisfy the reusable fixture config; no fixture
    # mesh is created and these dimensions are never used as animal labels.
    camera = build_camera(stage, c, CAMERA)
    camera.CreateClippingRangeAttr(Gf.Vec2f(1, 100000))
    for name,value in json.loads((EXP / 'environment.json').read_text())['camera_exposure_attributes'].items():
        camera.GetPrim().CreateAttribute(name, Sdf.ValueTypeNames.Float).Set(value)
    return c, camera


def points(stage, root=TARGET):
    chunks = []
    for prim in sorted(Usd.PrimRange(stage.GetPrimAtPath(root)), key=lambda p: str(p.GetPath())):
        if prim.IsA(UsdGeom.Mesh):
            local = np.asarray(UsdGeom.Mesh(prim).GetPointsAttr().Get(), dtype=np.float64)
            mat = np.asarray(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default()))
            chunks.append((np.column_stack([local, np.ones(len(local))]) @ mat)[:, :3] * .01)
    return np.concatenate(chunks)


def expected_points(manifest):
    data = np.load(EXP / 'wildlife' / (manifest['species'] + '_measurement_points.npz'))['points_m']
    a = np.radians(manifest['animal']['heading_deg'])
    rotation = np.array([[np.cos(a),0,-np.sin(a)],[0,1,0],[np.sin(a),0,np.cos(a)]])
    return data @ rotation + manifest['animal']['position_m']


def geometry_qa(stage, manifest):
    actual = points(stage); expected = expected_points(manifest)
    error = float(np.max(np.abs(actual-expected)))
    if error > 1e-5: raise ValueError('World geometry differs from calibration: ' + str(error))
    rows = []
    for variant in manifest['camera']['variants']:
        c,camera = set_camera(stage,variant)
        depth = variant['position_m'][1] - actual[:,1]
        u = 512 + 10000 * actual[:,0] / depth
        v = 384 + 10000 * actual[:,2] / depth
        box = [float(u.min()),float(v.min()),float(u.max()),float(v.max())]
        if min(depth)<=0 or box[0]<4 or box[1]<4 or box[2]>1020 or box[3]>764:
            raise ValueError('Geometry outside narrowest/paired footprint: '+str(box))
        rows.append({'gsd_cm_px':variant['requested_gsd_cm_px'],'projected_mesh_bounds_xyxy_px':box,
                     'reference_gsd_xy_cm_px':c.local_gsd(512,384),'passed':True})
    set_camera(stage,manifest['camera']['variants'][0])
    return {'max_world_point_error_m':error,'vertex_count':len(actual),'camera_geometry':rows,
            'passed':True,'visibility_status':'not_checked_until_M4'}


def dependencies(stage):
    result = {}
    for prim in stage.TraverseAll():
        for attr in prim.GetAttributes():
            if attr.GetTypeName() not in (Sdf.ValueTypeNames.Asset,Sdf.ValueTypeNames.AssetArray):continue
            value=attr.Get(); values=list(value) if attr.GetTypeName()==Sdf.ValueTypeNames.AssetArray and value else [value]
            for a in values:
                if not a or not a.path:continue
                path=Path(a.resolvedPath or a.path)
                forbidden=bool(set(path.parts)&{'_build','extscache','__pycache__','.cache'}) or path.suffix=='.pyc'
                hashed=not forbidden and path.is_file()
                result[str(path)]={'path':str(path),'sha256':sha(path) if hashed else None,
                                   'status':'local_hashed' if hashed else 'runtime_or_unresolved'}
    return list(result.values())


def build():
    if (OUT / 'snapshot_index.json').exists(): raise RuntimeError('Preserve completed snapshots')
    env=environment_record();save(EXP/'environment.json',env)
    env_hash=sha(EXP/'environment.json');index=[];qa=[]
    for species in ['european_storm_petrel','harbour_porpoise']:
        for i in range(25):
            manifest=sample_scene(species,i)
            save(OUT/'manifests'/(manifest['scene_id']+'.json'),manifest)
            # All 50 candidates use evaluated calibrated points for projection;
            # representative first/last scenes additionally build full USD twice.
            if i not in (0,24):
                actual=expected_points(manifest)
                boxes=[]
                for v in manifest['camera']['variants']:
                    depth=v['position_m'][1]-actual[:,1]; u=512+10000*actual[:,0]/depth; w=384+10000*actual[:,2]/depth
                    box=[float(u.min()),float(w.min()),float(u.max()),float(w.max())]
                    assert min(depth)>0 and box[0]>=4 and box[1]>=4 and box[2]<=1020 and box[3]<=764
                    boxes.append({'gsd_cm_px':v['requested_gsd_cm_px'],'projected_mesh_bounds_xyxy_px':box,'passed':True})
                qa.append({'scene_id':manifest['scene_id'],'passed':True,'scope':'calibrated_points_projection','camera_geometry':boxes})
                continue
            stage=make_scene(manifest,env);check=geometry_qa(stage,manifest)
            rebuilt=make_scene(json.loads(json.dumps(manifest)),env)
            rebuild_error=float(np.abs(points(stage)-points(rebuilt)).max());assert rebuild_error<1e-5
            directory=OUT/'snapshots'/manifest['scene_id'];directory.mkdir(parents=True)
            stage.GetRootLayer().Export(str(directory/'scene.usdc'))
            biological=biological_record(manifest,env_hash,stage)
            save(directory/'biological.json',biological)
            metadata={'schema_version':1,'scene_sha256':sha(directory/'scene.usdc'),'camera':CAMERA,
                'resolution':[1024,768],'fill_frame':False,'renderer_settings':env['renderer_settings'],
                'display_options':0,'timeline_seconds':1/24,'frozen_sampled_attributes':0,
                'limitations':'Pilot static scene; all controllers must be stopped before restore; external runtime material dependencies remain.'}
            save(directory/'metadata.json',metadata)
            # The existing bounded checkpoint loader owns attachment. Register a
            # content-addressed package; never overwrite an earlier checkpoint.
            checkpoint_id='checkpoint_m3_'+manifest['scene_id']+'_'+metadata['scene_sha256'][:12]
            dest=ROOT/'artifacts/scene_checkpoints'/checkpoint_id
            import shutil
            if dest.exists():raise RuntimeError('Checkpoint already exists')
            shutil.copytree(directory,dest)
            index.append({'scene_id':manifest['scene_id'],'checkpoint_id':checkpoint_id,
                'snapshot':str((directory/'scene.usdc').relative_to(EXP)),
                'sha256':metadata['scene_sha256'],'biological_manifest_sha256':biological['biological_manifest_sha256']})
            qa.append({'scene_id':manifest['scene_id'],**check,'independent_reconstruction_max_point_error_m':rebuild_error})
    save(OUT/'snapshot_index.json',index)
    save(EXP/'qa/m3_scene_geometry.json',{'passed':True,'candidate_count':len(qa),'full_usd_representatives':len(index),
         'records':qa,'rejected':[],'accepted_for_dataset':False,'dataset_acceptance_requires_M4_and_M5_QA':True})
    print(json.dumps({'candidate_manifests':len(qa),'full_snapshot_reconstructions':len(index),'passed':True}))


if __name__=='__main__':
    build()
