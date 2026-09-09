"""Create a lit USD-compatible working variant; preserve source and v3."""
import bpy
import shutil
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
parent=root/'assets/avians/common_guillemot/working'
source=parent/'support_cleanup_v3'
output=parent/'support_cleanup_v4'
if output.exists():
    raise RuntimeError('Output already exists')
output.mkdir()
bpy.ops.wm.open_mainfile(filepath=str(source/'common_guillemot_working.blend'))
for material in bpy.data.materials:
    if not material.node_tree:
        continue
    nodes=material.node_tree.nodes
    textures=[n for n in nodes if n.type=='TEX_IMAGE' and n.image]
    if not textures:
        continue
    texture=textures[0]
    shader=nodes.new('ShaderNodeBsdfPrincipled')
    shader.inputs['Roughness'].default_value=0.65
    material.node_tree.links.new(texture.outputs['Color'],shader.inputs['Base Color'])
    out=next(n for n in nodes if n.type=='OUTPUT_MATERIAL')
    material.node_tree.links.new(shader.outputs['BSDF'],out.inputs['Surface'])
bpy.ops.wm.save_as_mainfile(filepath=str(output/'common_guillemot_working.blend'))
(output/'usd').mkdir()
bpy.ops.wm.usd_export(filepath=str(output/'usd/common_guillemot_cleaned.usd'))
for name in ['license.txt','measurements.json']:
    shutil.copy2(source/name,output/name)
(output/'material_change.json').write_text(json.dumps({'source_version':'support_cleanup_v3',
    'geometry_changed':False,'change':'Unlit emission network replaced with Principled BSDF using original base-colour image.',
    'roughness':0.65,'status':'appearance approximation requiring Kit QA'},indent=2))
from pxr import Usd,UsdShade,UsdUtils
stage=Usd.Stage.Open(str(output/'usd/common_guillemot_cleaned.usd'))
assert any(p.IsA(UsdShade.Shader) for p in stage.Traverse())
assert not UsdUtils.ComputeAllDependencies(str(output/'usd/common_guillemot_cleaned.usd'))[2]
print('Material and dependencies verified')
