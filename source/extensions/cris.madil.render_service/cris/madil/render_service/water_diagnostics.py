"""Bounded, isolated ocean-material diagnostics; no marine scene edits."""
import asyncio
import gc
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
from typing import Literal

import carb.settings
import omni.usd
import omni.kit.app
from pydantic import BaseModel
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, UsdLux

from .api import router
from . import calibration_capture, capture_state
from .calibration_geometry import CalibrationConfig, build_camera
from .hidef_marine import gpu_preflight, settings_record, restore_settings, same_settings
from .ocean import _author_omnisurface_inputs
from .water_material import OmniSurfaceWaterParameters

ROOT = Path(__file__).resolve().parents[6] / 'experiments/ocean_material_v1/diagnostics/m2/captures'


@router.get('/scene/ocean/material/diagnostic/capabilities', summary='Inspect fixed diagnostic viewport support')
async def diagnostic_capabilities():
    import inspect
    import omni.kit.viewport.utility as utility
    import omni.kit.viewport.legacy_gizmos as gizmos
    import omni.kit.viewport.menubar.display as display
    import omni.kit.viewport.actions as actions
    manager = omni.kit.app.get_app().get_extension_manager()
    schema_stage = Usd.Stage.CreateInMemory()
    schema_controls = {}
    for name, kind in [('OmniRtxCameraAutoExposureAPI_1', 'Camera'),
                       ('OmniRtxCameraExposureAPI_1', 'Camera'),
                       ('OmniRtxSettingsCommonAdvancedAPI_1', 'RenderProduct'),
                       ('OmniRtxPostTonemapIrayReinhardAPI_1', 'RenderProduct')]:
        prim = schema_stage.DefinePrim('/' + name, kind)
        applied = prim.ApplyAPI(name)
        schema_controls[name] = {'applied': applied, 'attributes': [
            {'name': a.GetName(), 'type': str(a.GetTypeName()), 'default': str(a.Get()),
             'allowed': str(a.GetMetadata('allowedTokens'))}
            for a in prim.GetAttributes() if any(s in a.GetName().lower() for s in ('exposure', 'fog', 'tonemap', 'ocio'))]}
    return {'ok':True,
        'schema_controls': schema_controls,
        'modules': {name:{'file':module.__file__, 'public_names':[n for n in dir(module) if not n.startswith('_')]}
                    for name,module in [('gizmos',gizmos),('display',display),('actions',actions),('utility',utility)]},
        'capture_signatures': {'file':str(inspect.signature(utility.capture_viewport_to_file)),
                               'buffer':str(inspect.signature(utility.capture_viewport_to_buffer))},
        'extension_paths': {name:manager.get_extension_path(manager.get_enabled_extension_id(name))
                           for name in ['omni.kit.viewport.legacy_gizmos','omni.kit.viewport.menubar.display','omni.kit.viewport.actions']}}


class DiagnosticRequest(BaseModel):
    view: Literal['nadir', 'oblique'] = 'oblique'
    condition: Literal['dry', 'matched', 'water'] = 'water'
    probe: Literal['none', 'positive_depth', 'reflection_off'] = 'positive_depth'
    settled: bool = True

    class Config:
        extra = 'forbid'


class DiagnosticCamera(CalibrationConfig):
    def target_image_positions(self):
        return [(0.5, 0.5)]


def configuration(view):
    return DiagnosticCamera(meters_per_scene_unit=0.01, image_width_px=512,
        image_height_px=384, focal_length_mm=35, pixel_pitch_um=40,
        height_above_target_m=4, target_plane_y_m=-1,
        target_width_m=0.18, target_height_m=0.18,
        pitch_deg=40 if view == 'oblique' else 0)


def hide_fixture_overlays(viewport):
    from omni.kit.viewport.actions.actions import toggle_global_visibility
    toggle_global_visibility(viewport_api=viewport, visible=False)


def mesh(stage, path, points_m, faces, unit):
    obj = UsdGeom.Mesh.Define(stage, path)
    obj.CreatePointsAttr([Gf.Vec3f(*(v / unit for v in p)) for p in points_m])
    obj.CreateFaceVertexCountsAttr([len(face) for face in faces])
    obj.CreateFaceVertexIndicesAttr([v for face in faces for v in face])
    obj.CreateSubdivisionSchemeAttr('none')
    obj.CreateOrientationAttr('rightHanded')
    obj.CreateDoubleSidedAttr(False)
    return obj


def emissive(stage, obj, name, color):
    mat = UsdShade.Material.Define(stage, '/WaterDiagnostic/Looks/' + name)
    shader = UsdShade.Shader.Define(stage, mat.GetPath().AppendChild('Shader'))
    shader.CreateIdAttr('UsdPreviewSurface')
    for key, rgb in [('diffuseColor', (0, 0, 0)), ('emissiveColor', color), ('specularColor', (0, 0, 0))]:
        shader.CreateInput(key, Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*rgb))
    shader.CreateInput('useSpecularWorkflow', Sdf.ValueTypeNames.Int).Set(1)
    shader.CreateInput('roughness', Sdf.ValueTypeNames.Float).Set(1)
    mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), 'surface')
    UsdShade.MaterialBindingAPI.Apply(obj.GetPrim()).Bind(mat)


def build_fixture(stage, c, condition, probe='none', *, target_y=-1, background_y=-1.02,
                  medium_parameters=None):
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, c.meters_per_scene_unit)
    root = UsdGeom.Xform.Define(stage, '/WaterDiagnostic')
    stage.SetDefaultPrim(root.GetPrim())
    unit = c.meters_per_scene_unit
    # Identical target and lighting geometry in every condition.
    target = mesh(stage, '/WaterDiagnostic/Target_00',
        [(-.09, target_y, -.09), (-.09, target_y, .09), (.09, target_y, .09), (.09, target_y, -.09)], [[0, 1, 2, 3]], unit)
    emissive(stage, target, 'Fiducial', (10, 10, 10))
    background = mesh(stage, '/WaterDiagnostic/Background',
        [(-4.8, background_y, -4.8), (-4.8, background_y, 4.8), (4.8, background_y, 4.8), (4.8, background_y, -4.8)], [[0, 1, 2, 3]], unit)
    emissive(stage, background, 'Black', (0, 0, 0))
    for name, x0, x1, color in [('RedMarker', -3, 0, (10, 0, 0)), ('GreenMarker', 0, 3, (0, 10, 0))]:
        marker = mesh(stage, '/WaterDiagnostic/' + name,
            [(x0, 4, -4), (x1, 4, -4), (x1, 6, -4), (x0, 6, -4)], [[0, 1, 2, 3]], unit)
        emissive(stage, marker, name, color)
    dome = UsdLux.DomeLight.Define(stage, '/WaterDiagnostic/Dome')
    dome.CreateIntensityAttr(10)
    dome.CreateColorAttr(Gf.Vec3f(.03))
    parameters = OmniSurfaceWaterParameters(ior=1.0 if condition == 'matched' else 1.333,
        roughness=0.001, base_weight=0, transmission_color=(1, 1, 1),
        transmission_depth=100 if probe == 'positive_depth' else 0,
        scattering_color=(0, 0, 0), thin_walled=False)
    if medium_parameters is not None:
        parameters = medium_parameters
    geometry = {'water_bounds_m': [[-5, -2, -5], [5, 0, 5]],
                'target_center_m': [0, target_y, 0], 'target_size_m': [.18, .18],
                'background_y_m': background_y,
                'target_inside_declared_bounds': True, 'closed': False,
                'water_omitted_for_no_water_control': condition == 'dry'}
    bounds = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                              ['default', 'render']).ComputeWorldBound(target.GetPrim()).ComputeAlignedRange()
    actual_size = [float(v)*unit for v in bounds.GetSize()]
    assert abs(actual_size[0]-.18)<1e-6 and abs(actual_size[2]-.18)<1e-6
    geometry['measured_target_world_size_m'] = actual_size
    if condition != 'dry':
        points = [(-5, -2, -5), (5, -2, -5), (5, -2, 5), (-5, -2, 5),
                  (-5, 0, -5), (5, 0, -5), (5, 0, 5), (-5, 0, 5)]
        # Outward winding: bottom -Y, top +Y, then four side boundaries.
        faces = [[0, 1, 2, 3], [4, 7, 6, 5], [0, 4, 5, 1],
                 [1, 5, 6, 2], [2, 6, 7, 3], [3, 7, 4, 0]]
        counts = Counter(tuple(sorted((a, b))) for face in faces for a, b in zip(face, face[1:]+face[:1]))
        assert all(n == 2 for n in counts.values())
        normals = []
        for face in faces:
            a, b, d = (Gf.Vec3d(*points[i]) for i in face[:3])
            normal = Gf.Cross(b-a, d-a).GetNormalized()
            centre = sum((Gf.Vec3d(*points[i]) for i in face), Gf.Vec3d(0)) / len(face)
            assert Gf.Dot(normal, centre-Gf.Vec3d(0, -1, 0)) > 0
            normals.append(list(normal))
        volume = mesh(stage, '/WaterDiagnostic/Water', points, faces, unit)
        material = UsdShade.Material.Define(stage, '/WaterDiagnostic/Looks/ClearWater')
        shader = UsdShade.Shader.Define(stage, material.GetPath().AppendChild('Shader'))
        shader.CreateImplementationSourceAttr(UsdShade.Tokens.sourceAsset)
        shader.SetSourceAsset('OmniSurface.mdl', 'mdl')
        shader.SetSourceAssetSubIdentifier('OmniSurface', 'mdl')
        shader.CreateOutput('out', Sdf.ValueTypeNames.Token)
        _author_omnisurface_inputs(shader, parameters)
        if probe == 'reflection_off':
            shader.GetInput('specular_reflection_weight').Set(0.0)
        material.CreateSurfaceOutput('mdl').ConnectToSource(shader.ConnectableAPI(), 'out')
        UsdShade.MaterialBindingAPI.Apply(volume.GetPrim()).Bind(material)
        geometry.update(closed=True, boundary_edges=0, face_normals=normals,
                        opacity_override_authored=False)
    directory = Path(stage.GetRootLayer().realPath).parent
    (directory/'fixture.json').write_text(json.dumps({'condition':condition, 'probe':probe,
        'geometry':geometry, 'parameters':asdict(parameters),
        'ior_provenance':'Air=1.0, water=1.333; engineering assumptions, not measured seawater.',
        'stage_meters_per_unit':unit, 'normal_detail':'none', 'waves':'none'},indent=2)+'\n')
    return build_camera(stage, c, '/WaterDiagnostic/Camera')


@router.post('/scene/ocean/material/diagnostic/capture', summary='Capture one fixed isolated water-refraction fixture')
async def capture_diagnostic(data: DiagnosticRequest):
    if calibration_capture._busy:
        return {'ok':False, 'error':'Another camera capture is running'}
    gc.collect()
    try:
        gpu = gpu_preflight(768)
    except Exception as exc:
        return {'ok':False, 'error':str(exc) or type(exc).__name__, 'render_attempted':False}
    calibration_capture._busy = True
    previous_paused = capture_state.paused
    before = settings_record()
    display_path = '/persistent/app/viewport/displayOptions'
    previous_display = carb.settings.get_settings().get(display_path)
    capture_state.paused = True
    try:
        # Isolate actual surface/medium response from the pre-existing height cue.
        settings = carb.settings.get_settings()
        settings.set('/rtx/fog/enabled', False)
        settings.set('/exts/cris.madil.render_service/underwaterCue/enabled', False)
        settings.set('/rtx/post/histogram/enabled', False)
        settings.set(display_path, 0)
        c = configuration(data.view)
        active = settings_record()
        result = await asyncio.wait_for(calibration_capture._capture(c,
            stage_builder=lambda stage, config: build_fixture(stage, config, data.condition, data.probe),
            output_root=ROOT, viewport_setup=hide_fixture_overlays,
            rendered_frames=64 if data.settled else 0), timeout=90)
        metadata = result['metadata']
        metadata.update(test_kind='ocean_material_transmission_refraction_engineering',
            view=data.view, condition=data.condition, probe=data.probe, renderer_settings=active,
            diagnostic_display_options=0,
            completed_rendered_frame_wait=64 if data.settled else 0,
            viewport_overlays_disabled_via='Installed toggle_global_visibility(viewport_api, visible=False)',
            gpu_before=gpu, scientific_water_calibrated=False,
            geometric_projection_note='Direct pinhole projection; observed refracted target measured separately.')
        (Path(result['directory'])/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
        return result
    except Exception as exc:
        return {'ok':False, 'error':str(exc) or type(exc).__name__}
    finally:
        restore_settings(before)
        restore_settings({display_path:previous_display})
        capture_state.paused = previous_paused
        calibration_capture._busy = False
