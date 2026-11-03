"""Reduce the already-observed flat fixture to standalone native USD scenes."""
import hashlib
import json
import os
from pathlib import Path
import shutil
from pxr import Gf,Sdf,Usd,UsdGeom,UsdShade,UsdLux

root=Path(os.environ['WATER_REPRO_ROOT'])
output=Path(os.environ['WATER_REPRO_OUTPUT'])
source=root.parent/'m4_underwater/captures/inside_133t5ycr/scene.usdc'
old=Usd.Stage.Open(str(source))
archive=root/'qa/manual_scenes_surface_only'
if archive.exists():raise RuntimeError('Extraction already performed; refusing draft overwrite')
shutil.move(str(root/'scenes'),str(archive));shutil.copyfile(root/'scene_manifest.json',root/'qa/manual_scene_manifest.json')
folder=root/'scenes';folder.mkdir()
records=[]
for view in ('inside','above'):
    for path in ((.25,.5,1,2) if view=='inside' else (1,)):
        for condition in ('clear','absorption','engineering'):
            stage=Usd.Stage.CreateInMemory()
            UsdGeom.SetStageMetersPerUnit(stage,.01);UsdGeom.SetStageUpAxis(stage,'Y')
            world=stage.DefinePrim('/World','Xform');stage.SetDefaultPrim(world)
            stage.DefinePrim('/World/Looks','Scope')
            layer=stage.GetRootLayer();src=old.GetRootLayer()
            mapping=[('/World/Ocean','/World/Water'),
                     ('/World/MarlinOceanIntegrationDiagnostic/Camera','/World/Camera'),
                     ('/World/MarlinOceanIntegrationDiagnostic/Target','/World/Target'),
                     ('/World/MarlinOceanIntegrationDiagnostic/Background','/World/Background'),
                     ('/World/Looks/OceanWaterEngineeringV1','/World/Looks/Water'),
                     ('/WaterDiagnostic/Looks/M4Fiducial','/World/Looks/White'),
                     ('/WaterDiagnostic/Looks/M4Black','/World/Looks/Black')]
            for a,b in mapping:
                if not Sdf.CopySpec(src,a,layer,b):raise RuntimeError('Copy failed: '+a)
            stage.GetPrimAtPath('/World/Water').RemoveProperty('marlin:waterMedium:config')
            for name in ('Water','Target','Background'):
                material_name={'Water':'Water','Target':'White','Background':'Black'}[name]
                material=UsdShade.Material.Get(stage,'/World/Looks/'+material_name)
                shader=UsdShade.Shader.Get(stage,material.GetPath().AppendChild('Shader'))
                material.CreateSurfaceOutput('mdl' if name=='Water' else '').ConnectToSource(shader.ConnectableAPI(),'out' if name=='Water' else 'surface')
                UsdShade.MaterialBindingAPI.Apply(stage.GetPrimAtPath('/World/'+name)).Bind(material)
            shader=UsdShade.Shader.Get(stage,'/World/Looks/Water/Shader')
            shader.GetInput('specular_transmission_color').Set(Gf.Vec3f(1) if condition=='clear' else Gf.Vec3f(.6,.8,.9))
            shader.GetInput('specular_transmission_scattering_color').Set(Gf.Vec3f(.02) if condition=='engineering' else Gf.Vec3f(0))
            camera=UsdGeom.Camera(stage.GetPrimAtPath('/World/Camera'))
            matrix=camera.GetCamera(Usd.TimeCode.Default()).transform
            matrix.SetRow(3,Gf.Vec4d(1200,-50 if view=='inside' else 300,0,1))
            camera.MakeMatrixXform().Set(matrix)
            target_y=-.5-path if view=='inside' else -1
            for name,y in [('Target',target_y),('Background',target_y-.8)]:
                mesh=UsdGeom.Mesh(stage.GetPrimAtPath('/World/'+name))
                mesh.GetPointsAttr().Set([Gf.Vec3f(p[0],y/.01,p[2]) for p in mesh.GetPointsAttr().Get()])
            # Keep the proven skirt/top topology; extend only the bottom to
            # cover every declared diagnostic target and background depth.
            water=UsdGeom.Mesh(stage.GetPrimAtPath('/World/Water'))
            points=water.GetPointsAttr().Get()
            water.GetPointsAttr().Set([Gf.Vec3f(p[0],-500 if p[1]<-200 else p[1],p[2]) for p in points])
            water.GetExtentAttr().Set([Gf.Vec3f(1000,-500,-200),Gf.Vec3f(1400,0,200)])
            dome=UsdLux.DomeLight.Define(stage,'/World/Dome');dome.CreateColorAttr(Gf.Vec3f(.03));dome.CreateIntensityAttr(10)
            name=f'{view}_{int(path*1000):04d}_{condition}'
            destination=folder/(name+'.usda');layer.Export(str(destination))
            records.append({'name':name,'file':str(destination.relative_to(root)),'view':view,'condition':condition,
                            'path_m':path,'initial':view=='above' or path==.5,
                            'sha256':hashlib.sha256(destination.read_bytes()).hexdigest()})
manifest={'schema_version':2,'scene_dependencies':['Kit standard OmniSurface.mdl'],
          'marlin_assets_or_extensions_required':False,'generation_source_scene':str(source),
          'generation_source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
          'generation_note':'Copied only explicit geometry/material/camera specs from the retained flat fixture, retargeted bindings, removed MARLIN ownership metadata, replaced environment by fixed constant dome; no original asset references retained',
          'cases':records}
(root/'scene_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
(output/'extraction.json').write_text(json.dumps({'ok':True,'cases':len(records),'source':str(source)},indent=2)+'\n')
print('Extracted standalone scenes',len(records),flush=True)
import omni.kit.app
omni.kit.app.get_app().post_quit()
