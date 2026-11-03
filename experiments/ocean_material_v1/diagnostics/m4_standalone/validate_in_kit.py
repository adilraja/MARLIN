"""Parse every standalone stage and validate its physical geometry on CPU."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path

from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade

root=Path(os.environ['WATER_REPRO_ROOT'])
output=Path(os.environ['WATER_REPRO_OUTPUT'])
rows=[]
try:
    manifest=json.loads((root/'scene_manifest.json').read_text())
    for case in manifest['cases']:
        path=root/case['file']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==case['sha256']
        stage=Usd.Stage.Open(str(path))
        assert stage and UsdGeom.GetStageMetersPerUnit(stage)==.01
        assert UsdGeom.GetStageUpAxis(stage)=='Y'
        mesh=UsdGeom.Mesh(stage.GetPrimAtPath('/World/Water'))
        p=mesh.GetPointsAttr().Get()
        indices=list(mesh.GetFaceVertexIndicesAttr().Get());counts=mesh.GetFaceVertexCountsAttr().Get()
        faces=[];offset=0
        for count in counts:
            faces.append(indices[offset:offset+count]);offset+=count
        directed=Counter((a,b) for face in faces for a,b in zip(face,face[1:]+face[:1]))
        assert len(p)>=8 and len(faces)>=6 and all(directed[(b,a)]==1 for a,b in directed)
        box_centre=Gf.Vec3f(*((min(v[i] for v in p)+max(v[i] for v in p))/2 for i in range(3)))
        for face in faces:
            normal=Gf.Cross(p[face[1]]-p[face[0]],p[face[2]]-p[face[0]])
            centre=sum((p[i] for i in face),Gf.Vec3f(0))/len(face)
            assert Gf.Dot(normal,centre-box_centre)>0
        camera=UsdGeom.Camera(stage.GetPrimAtPath('/World/Camera'))
        matrix=camera.GetCamera(Usd.TimeCode.Default()).transform
        position=matrix.ExtractTranslation()*.01
        expected_y=-.5 if case['view']=='inside' else 3
        assert abs(position[1]-expected_y)<1e-8
        np=UsdGeom.Mesh(stage.GetPrimAtPath('/World/Target')).GetPointsAttr().Get()
        target_y=float(np[0][1])*.01
        expected_target_y=-.5-case['path_m'] if case['view']=='inside' else -1
        assert abs(target_y-expected_target_y)<1e-8
        assert -5<target_y<0 and abs(float(np[2][0]-np[0][0])*.01-.18)<1e-8
        assets=[]
        for prim in stage.Traverse():
            assert not prim.HasAuthoredReferences() and not prim.HasAuthoredPayloads()
            for attr in prim.GetAttributes():
                value=attr.Get()
                if isinstance(value,Sdf.AssetPath) and value.path:assets.append(value.path)
        assert set(assets)==set(manifest['scene_dependencies'][i].removeprefix('Kit standard ') for i in range(len(manifest['scene_dependencies']))),assets
        bound=UsdShade.MaterialBindingAPI(mesh.GetPrim()).ComputeBoundMaterial()[0]
        assert str(bound.GetPath())=='/World/Looks/Water'
        rows.append({'case':case['name'],'scene_sha256':case['sha256'],'closed_outward_box':True,
                     'camera_position_m':list(position),'target_y_m':target_y,'assets':assets})
    result={'ok':True,'cases':rows,'marlin_assets_required':False,'rendering_performed':False}
except Exception as exc:
    import traceback
    result={'ok':False,'error':str(exc),'traceback':traceback.format_exc(),'cases_checked':rows}
(output/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('cases','cases_checked')},indent=2),flush=True)
import omni.kit.app
omni.kit.app.get_app().post_quit(0 if result['ok'] else 1)
