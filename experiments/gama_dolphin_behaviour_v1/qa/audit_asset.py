"""Inspect existing USD/glTF and baked samples on CPU; author no scene or pose."""
import hashlib
import json
import math
from pathlib import Path
from collections import Counter

from pxr import Gf, Usd, UsdGeom, UsdShade, UsdSkel, Vt

REPO = Path(__file__).resolve().parents[3]
BASE = REPO / 'experiments/gama_dolphin_behaviour_v1'
ASSET = REPO / 'assets/cetaceans/model_61a_-_bottlenose_dolphin'
ANIMAL = '/World/Cetaceans/Dolphin_001'


def digest(value):
    return hashlib.sha256(json.dumps(value, separators=(',', ':'), sort_keys=True).encode()).hexdigest()


def plain(value):
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    try:
        return [plain(v) for v in value]
    except TypeError:
        return str(value)


def inspect(path, root_path=None):
    stage = Usd.Stage.Open(str(path))
    root = stage.GetPrimAtPath(root_path) if root_path else stage.GetDefaultPrim()
    assert root and stage
    meshes, skeletons, animations, transforms, sampled, clip_metadata = [], [], [], [], [], []
    combined = []
    for prim in Usd.PrimRange(root):
        if prim.HasMetadata('clips'):
            clip_metadata.append(str(prim.GetPath()))
        for attr in prim.GetAttributes():
            ts = attr.GetTimeSamples()
            if ts:
                sampled.append(dict(path=str(attr.GetPath()), samples=len(ts), first=ts[0], last=ts[-1]))
        if prim.IsA(UsdGeom.Xformable):
            ops = UsdGeom.Xformable(prim).GetOrderedXformOps()
            if ops:
                transforms.append(dict(path=str(prim.GetPath()), ops=[dict(name=o.GetOpName(), value=plain(o.Get())) for o in ops]))
        if prim.IsA(UsdGeom.Mesh):
            mesh = UsdGeom.Mesh(prim)
            points = mesh.GetPointsAttr().Get()
            matrix = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            world = [list(matrix.Transform(Gf.Vec3d(p))) for p in points]
            purpose = str(UsdGeom.Imageable(prim).ComputePurpose())
            visibility = str(UsdGeom.Imageable(prim).ComputeVisibility())
            if visibility != 'invisible' and purpose in ('default', 'render'):
                combined.extend(world)
            binding = UsdSkel.BindingAPI(prim)
            material = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial()[0]
            meshes.append(dict(path=str(prim.GetPath()), vertices=len(points), faces=len(mesh.GetFaceVertexCountsAttr().Get()),
                points_sha256=digest(plain(points)), topology_sha256=digest([plain(mesh.GetFaceVertexCountsAttr().Get()), plain(mesh.GetFaceVertexIndicesAttr().Get())]),
                purpose=purpose, visibility=visibility,
                bounds_min=[min(v[i] for v in world) for i in range(3)],
                bounds_max=[max(v[i] for v in world) for i in range(3)],
                skeleton_targets=plain(binding.GetSkeletonRel().GetTargets()),
                joint_indices=plain(binding.GetJointIndicesPrimvar().Get()),
                joint_indices_element_size=binding.GetJointIndicesPrimvar().GetElementSize(),
                joint_weight_count=len(binding.GetJointWeightsPrimvar().Get() or []),
                material=str(material.GetPath()) if material else None))
        if prim.IsA(UsdSkel.Skeleton):
            skeleton = UsdSkel.Skeleton(prim)
            joints = list(map(str, skeleton.GetJointsAttr().Get() or []))
            skeletons.append(dict(path=str(prim.GetPath()), joints=joints,
                rest_transform_count=len(skeleton.GetRestTransformsAttr().Get() or []),
                bind_transform_count=len(skeleton.GetBindTransformsAttr().Get() or []),
                animation_sources=plain(UsdSkel.BindingAPI(prim).GetAnimationSourceRel().GetTargets())))
        if prim.IsA(UsdSkel.Animation):
            animations.append(str(prim.GetPath()))
    # Avoid duplicating all per-vertex skin indices in the human-facing record.
    for mesh in meshes:
        indices = mesh.pop('joint_indices')
        mesh['joint_index_count'] = len(indices or [])
        mesh['joint_index_range'] = [min(indices), max(indices)] if indices else None
    # A skinned mesh's authored points and its renderer-evaluated rest pose can
    # differ. Measure both explicitly, using the existing bound skeleton only.
    cache = UsdSkel.Cache()
    for prim in Usd.PrimRange(root):
        if prim.IsA(UsdSkel.Root):
            cache.Populate(UsdSkel.Root(prim), Usd.PrimDefaultPredicate)
    evaluated = []
    skin_records = []
    diagnostic_meshes = []
    assert len(skeletons) == 1
    skeleton_prim = stage.GetPrimAtPath(skeletons[0]['path'])
    skel_query = cache.GetSkelQuery(UsdSkel.Skeleton(skeleton_prim))
    skinning_transforms = skel_query.ComputeSkinningTransforms(Usd.TimeCode.Default())
    skel_world = UsdGeom.Xformable(skeleton_prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    for record in meshes:
        prim = stage.GetPrimAtPath(record['path'])
        query = cache.GetSkinningQuery(prim)
        points = Vt.Vec3fArray(UsdGeom.Mesh(prim).GetPointsAttr().Get())
        ok = bool(query) and query.ComputeSkinnedPoints(skinning_transforms, points, Usd.TimeCode.Default())
        assert ok, record['path']
        world = [list(skel_world.Transform(Gf.Vec3d(p))) for p in points]
        if record['visibility'] != 'invisible' and record['purpose'] in ('default', 'render'):
            evaluated.extend(world)
        skin_records.append(dict(path=record['path'], computed=True, points_sha256=digest(plain(points)),
            bounds_min=[min(v[i] for v in world) for i in range(3)],
            bounds_max=[max(v[i] for v in world) for i in range(3)]))
        if path == BASE/'baseline/live_before/scene.usdc':
            diagnostic_meshes.append(dict(path=record['path'], points_world_m=[[v*UsdGeom.GetStageMetersPerUnit(stage) for v in p] for p in world]))
    joint_world = [plain(skel_world.Transform(m.ExtractTranslation()))
                   for m in skel_query.ComputeJointSkelTransforms(Usd.TimeCode.Default())]
    unit = UsdGeom.GetStageMetersPerUnit(stage)
    if diagnostic_meshes:
        (BASE/'baseline/live_before/evaluated_geometry.json').write_text(json.dumps(dict(
            scope='Read-only CPU evaluation of existing rest pose; no new animation or anatomical landmark approval',
            meshes=diagnostic_meshes,
            joints_world_m={j:[v*unit for v in p] for j,p in zip(skeletons[0]['joints'],joint_world)}),separators=(',', ':'))+'\n')
    lo = [min(v[i] for v in combined) for i in range(3)]
    hi = [max(v[i] for v in combined) for i in range(3)]
    result = dict(source=str(path.relative_to(REPO)), source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        root=str(root.GetPath()), up_axis=str(UsdGeom.GetStageUpAxis(stage)), meters_per_unit=unit,
        authored_meters_per_unit=stage.HasAuthoredMetadata('metersPerUnit'),
        time_codes_per_second=stage.GetTimeCodesPerSecond(),
        stage_start=stage.GetStartTimeCode(), stage_end=stage.GetEndTimeCode(),
        prim_types=dict(Counter(p.GetTypeName() for p in Usd.PrimRange(root))),
        meshes=meshes, skeletons=skeletons, animations=animations,
        time_sampled_attributes=sampled, clip_metadata=clip_metadata, transforms=transforms,
        render_bounds_min_scene_units=lo, render_bounds_max_scene_units=hi,
        render_dimensions_scene_units=[hi[i]-lo[i] for i in range(3)],
        authored_mesh_dimensions_m=[(hi[i]-lo[i])*unit for i in range(3)],
        evaluated_skinning=dict(meshes=skin_records,
            dimensions_m=[(max(v[i] for v in evaluated)-min(v[i] for v in evaluated))*unit for i in range(3)],
            bounds_min_scene_units=[min(v[i] for v in evaluated) for i in range(3)],
            bounds_max_scene_units=[max(v[i] for v in evaluated) for i in range(3)],
            joint_positions_world_m={j:[v*unit for v in p] for j,p in zip(skeletons[0]['joints'],joint_world)}),
        bbox_cache_dimensions_m=plain(UsdGeom.BBoxCache(Usd.TimeCode.Default(), ['default','render','proxy']).ComputeWorldBound(root).ComputeAlignedRange().GetSize()*unit),
        bounds_method='Reported authored mesh bounds, evaluated UsdSkel rest-pose vertex bounds and BBoxCache extents separately; none is an anatomical length calibration.')
    return result


def main():
    paths = {'asset_usd': (ASSET/'usd/model_61a_-_bottlenose_dolphin.usd', None),
             'live_checkpoint': (BASE/'baseline/live_before/scene.usdc', ANIMAL),
             'accepted_water_scene': (REPO/'experiments/ocean_material_v1/presets/engineering_v1/demonstration_scene.usdc', ANIMAL)}
    records = {k: inspect(*v) for k, v in paths.items()}
    gltf = json.loads((ASSET/'source/scene.gltf').read_text())
    source_animation = []
    for anim in gltf.get('animations', []):
        source_animation.append(dict(name=anim.get('name'),
            channels=[dict(node=c['target']['node'], node_name=gltf['nodes'][c['target']['node']].get('name'), path=c['target']['path']) for c in anim['channels']],
            sampler_times=[dict(accessor=s['input'], minimum=gltf['accessors'][s['input']].get('min'), maximum=gltf['accessors'][s['input']].get('max')) for s in anim['samplers']]))
    clip_path = REPO/'assets/cetaceans/bottlenose_dolphin/animation/swim_cycle.json'
    clip = json.loads(clip_path.read_text())
    skeleton = records['asset_usd']['skeletons'][0]
    normalized = [n.replace('.', '_') for n in clip['bone_names']]
    target = [n.rsplit('/', 1)[-1] for n in skeleton['joints']]
    first, last = clip['frames'][0], clip['frames'][-1]
    joints = []
    for i, name in enumerate(clip['bone_names']):
        translations = [f['translations'][i] for f in clip['frames']]
        q0, q1 = first['rotations'][i], last['rotations'][i]
        dot = abs(sum(a*b for a,b in zip(q0,q1))) / math.sqrt(sum(a*a for a in q0)*sum(a*a for a in q1))
        joints.append(dict(name=name, parent_index=(target.index(skeleton['joints'][i].rsplit('/',1)[0].rsplit('/',1)[-1]) if '/' in skeleton['joints'][i] else None),
            translation_min=[min(t[k] for t in translations) for k in range(3)],
            translation_max=[max(t[k] for t in translations) for k in range(3)],
            translation_span_norm=math.sqrt(sum((max(t[k] for t in translations)-min(t[k] for t in translations))**2 for k in range(3))),
            distinct_rotations=len({tuple(f['rotations'][i]) for f in clip['frames']}),
            end_to_start_translation_error=math.dist(first['translations'][i],last['translations'][i]),
            end_to_start_rotation_error_deg=math.degrees(2*math.acos(min(1.0,dot)))))
    identity = {}
    for key in ('live_checkpoint','accepted_water_scene'):
        def geometry(rec):
            return sorted((m['vertices'],m['points_sha256'],m['topology_sha256']) for m in rec['meshes'])
        identity[key] = dict(mesh_geometry_matches_source=geometry(records[key])==geometry(records['asset_usd']),
                             skeleton_joints_match_source=records[key]['skeletons'][0]['joints']==skeleton['joints'])
    output = dict(schema_version=1, scope='CPU read-only M1 inventory; no rig/clip was attached and no motion was started',
        usd_python_version=plain(Usd.GetVersion()), records=records,
        gltf=dict(asset=gltf['asset'], skins=[dict(name=s.get('name'),joints=len(s['joints'])) for s in gltf.get('skins',[])], animations=source_animation,
                  mesh_nodes=[dict(index=i,**n) for i,n in enumerate(gltf['nodes']) if 'mesh' in n]),
        baked_clip=dict(path=str(clip_path.relative_to(REPO)), sha256=hashlib.sha256(clip_path.read_bytes()).hexdigest(),
            name=clip['name'], transform_space=clip['transform_space'], frames=len(clip['frames']), fps=clip['fps'],
            start_frame=clip['start_frame'], end_frame=clip['end_frame'], duration_seconds=(clip['end_frame']-clip['start_frame'])/clip['fps'],
            joint_names_match_target=normalized==target, joint_sample_diagnostics=joints,
            binding_and_rendered_deformation_verified_in_this_audit=False),
        identity_checks=identity,
        biological_size_calibration_verified=False,
        root_motion_caveat='Baked local root-joint translations were measured; their evaluated skin/world effect still requires M2/M4 isolation tests.')
    (BASE/'qa/asset_inventory.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps(dict(identity_checks=identity,clip_joint_names_match=normalized==target,
        live_meshes=len(records['live_checkpoint']['meshes']), live_skeletons=len(records['live_checkpoint']['skeletons']),
        live_animations=len(records['live_checkpoint']['animations']),
        live_evaluated_dimensions_m=records['live_checkpoint']['evaluated_skinning']['dimensions_m'],
        live_bbox_cache_dimensions_m=records['live_checkpoint']['bbox_cache_dimensions_m']),indent=2))


if __name__ == '__main__':
    main()
