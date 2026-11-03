"""Author minimal readable USDA without importing MARLIN or a USD runtime."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def mesh(name, points, faces, normals, material):
    assert len(normals) == len(faces)
    flattened = [index for face in faces for index in face]
    corners = [normal for face, normal in zip(faces, normals) for _ in face]
    def tuples(values):
        return '[' + ', '.join('(' + ', '.join(str(x) for x in value) + ')' for value in values) + ']'
    return f'''    def Mesh "{name}" (prepend apiSchemas = ["MaterialBindingAPI"]) {{
        uniform token subdivisionScheme = "none"
        uniform token orientation = "rightHanded"
        bool doubleSided = false
        point3f[] points = {tuples(points)}
        int[] faceVertexCounts = {[len(face) for face in faces]}
        int[] faceVertexIndices = {flattened}
        normal3f[] normals = {tuples(corners)} (interpolation = "faceVarying")
        rel material:binding = </World/Looks/{material}>
    }}
'''


def emission(name, value):
    return f'''        def Material "{name}" {{
            token outputs:surface.connect = </World/Looks/{name}/Shader.outputs:surface>
            def Shader "Shader" {{
                uniform token info:id = "UsdPreviewSurface"
                color3f inputs:diffuseColor = (0, 0, 0)
                color3f inputs:specularColor = (0, 0, 0)
                color3f inputs:emissiveColor = ({value}, {value}, {value})
                int inputs:useSpecularWorkflow = 1
                float inputs:roughness = 1
                token outputs:surface
            }}
        }}
'''


def scene(view, condition, path):
    target_y = -.5 - path if view == 'inside' else -1
    camera_y = -.5 if view == 'inside' else 3
    points = [(-200, 0, -200), (200, 0, -200), (200, 0, 200), (-200, 0, 200),
              (-200, -500, -200), (200, -500, -200), (200, -500, 200), (-200, -500, 200)]
    faces = [[0, 3, 2, 1], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7], [0, 1, 5, 4], [4, 5, 6, 7]]
    normals = [(0, 1, 0), (1, 0, 0), (0, 0, 1), (-1, 0, 0), (0, 0, -1), (0, -1, 0)]
    water = mesh('Water', points, faces, normals, 'Water')
    y = target_y * 100
    target = mesh('Target', [(-9,y,-9),(-9,y,9),(9,y,9),(9,y,-9)], [[0,1,2,3]], [(0,1,0)], 'White')
    y = (target_y - .8) * 100
    background = mesh('Background', [(-190,y,-190),(-190,y,190),(190,y,190),(190,y,-190)], [[0,1,2,3]], [(0,1,0)], 'Black')
    color = '(1, 1, 1)' if condition == 'clear' else '(.6, .8, .9)'
    scattering = '(.02, .02, .02)' if condition == 'engineering' else '(0, 0, 0)'
    return f'''#usda 1.0
(
    defaultPrim = "World"
    metersPerUnit = .01
    upAxis = "Y"
)
def Xform "World" {{
{water}{target}{background}
    def Camera "Camera" (
        prepend apiSchemas = ["OmniRtxCameraAutoExposureAPI_1", "OmniRtxCameraExposureAPI_1"]
    ) {{
        float focalLength = 35
        float horizontalAperture = 20.48
        float verticalAperture = 15.36
        float2 clippingRange = (1, 2500)
        float exposure = 0
        float exposure:time = 1
        float exposure:fStop = 1
        float exposure:iso = 100
        float exposure:responsivity = 1
        bool omni:rtx:autoExposure:enabled = false
        matrix4d xformOp:transform = ((1,0,0,0),(0,0,-1,0),(0,1,0,0),(0,{camera_y*100},0,1))
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }}
    def DomeLight "Dome" {{
        color3f inputs:color = (.25, .35, .45)
        float inputs:intensity = 500
    }}
    def Scope "Looks" {{
        def Material "Water" {{
            token outputs:mdl:surface.connect = </World/Looks/Water/Shader.outputs:out>
            def Shader "Shader" {{
                uniform token info:implementationSource = "sourceAsset"
                uniform asset info:mdl:sourceAsset = @OmniSurface.mdl@
                uniform token info:mdl:sourceAsset:subIdentifier = "OmniSurface"
                float inputs:diffuse_reflection_weight = 0
                color3f inputs:diffuse_reflection_color = (.02,.1,.13)
                float inputs:metalness = 0
                float inputs:specular_reflection_weight = 1
                color3f inputs:specular_reflection_color = (1,1,1)
                float inputs:specular_reflection_roughness = .001
                float inputs:specular_reflection_ior = 1.333
                bool inputs:enable_specular_transmission = true
                float inputs:specular_transmission_weight = 1
                color3f inputs:specular_transmission_color = {color}
                float inputs:specular_transmission_scattering_depth = 100
                color3f inputs:specular_transmission_scattering_color = {scattering}
                float inputs:specular_transmission_scatter_anisotropy = 0
                bool inputs:thin_walled = false
                token outputs:out
            }}
        }}
{emission('White',10)}{emission('Black',0)}    }}
}}
'''


def main():
    folder = ROOT / 'scenes'
    folder.mkdir(exist_ok=True)
    records = []
    for view in ('inside', 'above'):
        for path in ((.25,.5,1,2) if view == 'inside' else (1,)):
            for condition in ('clear','absorption','engineering'):
                name = f'{view}_{int(path*1000):04d}_{condition}'
                text = scene(view, condition, path)
                destination = folder / (name + '.usda')
                if destination.exists() and destination.read_text() != text:
                    raise RuntimeError('Refusing to overwrite a changed scene: ' + name)
                destination.write_text(text)
                records.append({'name':name, 'file':str(destination.relative_to(ROOT)),
                                'view':view, 'condition':condition, 'path_m':path,
                                'initial':view=='above' or path==.5,
                                'sha256':hashlib.sha256(text.encode()).hexdigest()})
    manifest = {'schema_version':1, 'scene_dependencies':['Kit standard OmniSurface.mdl'],
                'marlin_assets_or_extensions_required':False,'cases':records}
    (ROOT/'scene_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f'Authored {len(records)} standalone scenes; six initial cases')


if __name__ == '__main__':
    main()
