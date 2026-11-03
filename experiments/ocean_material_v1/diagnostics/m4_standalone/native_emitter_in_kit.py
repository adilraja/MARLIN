"""Make an explicit native MDL emitter control, identical across all media."""
import hashlib,json,os,shutil
from pathlib import Path
from pxr import Gf,Sdf,Usd,UsdShade
root=Path(os.environ['WATER_REPRO_ROOT']);output=Path(os.environ['WATER_REPRO_OUTPUT'])
manifest=json.loads((root/'scene_manifest.json').read_text())
archive=root/'qa/extracted_preview_scenes';shutil.copytree(root/'scenes',archive)
shutil.copyfile(root/'scene_manifest.json',root/'qa/extracted_preview_manifest.json')
for case in manifest['cases']:
    path=root/case['file'];stage=Usd.Stage.Open(str(path))
    material=UsdShade.Material.Get(stage,'/World/Looks/White')
    stage.RemovePrim('/World/Looks/White/Shader')
    material.GetPrim().RemoveProperty('outputs:surface')
    shader=UsdShade.Shader.Define(stage,'/World/Looks/White/Shader')
    shader.CreateImplementationSourceAttr(UsdShade.Tokens.sourceAsset)
    shader.SetSourceAsset('OmniEmissive.mdl','mdl');shader.SetSourceAssetSubIdentifier('OmniEmissive','mdl')
    shader.CreateInput('emissive_color',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(1))
    shader.CreateInput('emission_intensity',Sdf.ValueTypeNames.Float).Set(10)
    shader.CreateInput('compensate_camera_exposure',Sdf.ValueTypeNames.Bool).Set(True)
    shader.CreateInput('backface_emission',Sdf.ValueTypeNames.Bool).Set(False)
    shader.CreateOutput('out',Sdf.ValueTypeNames.Token)
    material.CreateSurfaceOutput('mdl').ConnectToSource(shader.ConnectableAPI(),'out')
    stage.GetRootLayer().Save();case['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
manifest.update(scene_dependencies=['Kit standard OmniSurface.mdl','Kit standard OmniEmissive.mdl'],
                target_emitter='Native white OmniEmissive, intensity10, front-face only, fixed for every condition')
(root/'scene_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
(output/'emitter_preparation.json').write_text(json.dumps({'ok':True,'cases':len(manifest['cases'])},indent=2)+'\n')
import omni.kit.app
omni.kit.app.get_app().post_quit()
