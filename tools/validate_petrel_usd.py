"""Validate exported petrel skeleton, skin and sampled deformation in USD."""
import json
from pathlib import Path
import numpy as np
from pxr import Usd,UsdGeom,UsdSkel,UsdShade,UsdUtils,Vt

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets/birds/european_storm_petrel'


def inspect(path):
    stage=Usd.Stage.Open(str(path));assert stage and stage.GetDefaultPrim()
    meshes=sorted([UsdGeom.Mesh(p) for p in stage.Traverse() if p.IsA(UsdGeom.Mesh)],key=lambda m:str(m.GetPath()))
    skeletons=[UsdSkel.Skeleton(p) for p in stage.Traverse() if p.IsA(UsdSkel.Skeleton)]
    roots=[UsdSkel.Root(p) for p in stage.Traverse() if p.IsA(UsdSkel.Root)]
    anims=[UsdSkel.Animation(p) for p in stage.Traverse() if p.IsA(UsdSkel.Animation)]
    materials=[p for p in stage.Traverse() if p.IsA(UsdShade.Material)]
    assert meshes and len(skeletons)==1 and roots and materials
    layers,assets,missing=UsdUtils.ComputeAllDependencies(str(path));assert not missing
    assert assets,'Missing texture asset dependencies'
    cache=UsdSkel.Cache()
    for root in roots:cache.Populate(root,Usd.PrimDefaultPredicate)
    query=cache.GetSkelQuery(skeletons[0]);assert query
    joints=list(skeletons[0].GetJointsAttr().Get());assert len(joints)==11
    frames=[1,13,25,37,49]
    samples={}
    for frame in frames:
        transforms=query.ComputeSkinningTransforms(Usd.TimeCode(frame))
        chunks=[]
        for mesh in meshes:
            skin=cache.GetSkinningQuery(mesh.GetPrim());assert skin
            assert UsdSkel.BindingAPI(mesh.GetPrim()).GetInheritedSkeleton()
            points=Vt.Vec3fArray(mesh.GetPointsAttr().Get())
            assert skin.ComputeSkinnedPoints(transforms,points,Usd.TimeCode(frame))
            chunks.append(np.array(points))
        samples[frame]=np.concatenate(chunks)
        assert np.isfinite(samples[frame]).all()
    result={'path':str(path.relative_to(ROOT)), 'meshes':len(meshes),'joints':joints,
        'skeleton_path':str(skeletons[0].GetPath()),'animation_paths':[str(a.GetPath()) for a in anims],
        'texture_dependencies':assets,'up_axis':str(UsdGeom.GetStageUpAxis(stage)),
        'meters_per_unit':UsdGeom.GetStageMetersPerUnit(stage),
        'vertex_count':len(samples[1]),'frame1_min':samples[1].min(axis=0).tolist(),
        'frame1_max':samples[1].max(axis=0).tolist(),
        'frame13_delta':float(np.abs(samples[13]-samples[1]).max()),
        'frame37_delta':float(np.abs(samples[37]-samples[1]).max()),
        'loop_error':float(np.abs(samples[49]-samples[1]).max())}
    return result,samples[1]


def run():
    main,rest=inspect(OUT/'usd/european_storm_petrel_rigged.usd')
    assert main['frame13_delta']>0.1 and main['frame37_delta']>0.1
    assert main['loop_error']<1e-4
    report=json.loads((OUT/'working/rig_report.json').read_text())
    assert main['vertex_count']==report['original_vertex_count']
    assert np.allclose(main['frame1_min'],report['rest_world_min'],atol=1e-4)
    assert np.allclose(main['frame1_max'],report['rest_world_max'],atol=1e-4)
    poses={}
    for name in ['glide','wings_up','wings_down','bank_left','bank_right']:
        result,points=inspect(OUT/f'usd/{name}.usd')
        result['difference_from_glide']=float(np.abs(points-rest).max())
        poses[name]=result
    print('POSE_CHECK',json.dumps({k:{a:v[a] for a in ['difference_from_glide','frame1_min','frame1_max','animation_paths']} for k,v in poses.items()}),flush=True)
    assert poses['glide']['difference_from_glide']<1e-4
    for name in ['wings_up','wings_down','bank_left','bank_right']:
        assert poses[name]['difference_from_glide']>0.1,(name,'static pose not exported')
    (OUT/'working/usd_validation.json').write_text(json.dumps({'ok':True,'animation':main,'poses':poses},indent=2)+'\n')
    print(json.dumps({'ok':True,'animation':main,'pose_deltas':{k:v['difference_from_glide'] for k,v in poses.items()}},indent=2))


if __name__=='__main__':run()
