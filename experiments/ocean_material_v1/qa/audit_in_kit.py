"""Fixed, bounded M1 audit, run inside the existing Kit app using --exec.

No shader, wave equation or production source is changed. A fresh empty app
may reconstruct the existing marine setup. An existing ocean is retained.
"""
import asyncio
from collections import Counter
import hashlib
import json
from pathlib import Path
import time
import traceback

OUT = Path(__file__).resolve().parents[1]


def value(item):
    if item is None or isinstance(item, (str, int, float, bool)):
        return item
    if hasattr(item, 'resolvedPath'):
        return {'authored': item.path, 'resolved': item.resolvedPath}
    if isinstance(item, dict):
        return {str(k): value(v) for k, v in item.items()}
    try:
        return [value(v) for v in item]
    except TypeError:
        return str(item)


def write(name, record):
    (OUT / name).write_text(json.dumps(value(record), indent=2) + '\n')


def attributes(prim):
    return [{'name': a.GetName(), 'type': str(a.GetTypeName()),
             'value': value(a.Get()), 'connections': [str(p) for p in a.GetConnections()],
             'authored': a.HasAuthoredValueOpinion(),
             'layers': [str(s.layer.identifier) for s in a.GetPropertyStack()]}
            for a in prim.GetAttributes()]


async def audit():
    import carb.settings
    import omni.kit.app
    import omni.timeline
    import omni.usd
    from pxr import Usd, UsdGeom, UsdShade
    from omni.kit.viewport.utility import get_active_viewport, capture_viewport_to_file
    from cris.madil.render_service import capture_state
    from cris.madil.render_service.scene_setup import setup_marine_scene, MarineSceneSetupDataModel
    from cris.madil.render_service.hidef_marine import settings_record, freeze_stage, gpu_preflight
    from cris.madil.render_service.capture_projection import record_projection
    app = omni.kit.app.get_app()
    for _ in range(90):
        await app.next_update_async()
    stage = omni.usd.get_context().get_stage()
    if stage is None:
        await omni.usd.get_context().new_stage_async()
        stage = omni.usd.get_context().get_stage()
    if not stage.GetPrimAtPath('/World/Ocean'):
        # Refuse to replace an unrelated nonempty scene.
        if any(p.GetName() not in ('World', 'Environment', 'OmniverseKit_Persp', 'OmniverseKit_Front',
                                   'OmniverseKit_Top', 'OmniverseKit_Right', 'Render')
               for p in stage.GetPseudoRoot().GetChildren()):
            raise RuntimeError('Nonempty stage without Ocean: refusing scene reconstruction')
        world = stage.GetPrimAtPath('/World')
        if world and list(world.GetChildren()):
            raise RuntimeError('World contains scene objects: refusing reconstruction')
        initial, _ = freeze_stage(stage, Usd.TimeCode.Default())
        initial.GetRootLayer().Export(str(OUT/'baseline/startup_template.usda'))
        write('baseline/startup_settings.json', settings_record())
        setup = await setup_marine_scene(MarineSceneSetupDataModel(start_swimming=False))
        write('baseline/setup.json', setup)
        if not setup.get('ok'):
            raise RuntimeError('Existing marine setup failed')
    for _ in range(90):
        await app.next_update_async()
    viewport = get_active_viewport()
    if viewport is None:
        raise RuntimeError('No active viewport')
    timeline = omni.timeline.get_timeline_interface()
    previous = {'paused': capture_state.paused, 'playing': timeline.is_playing(),
                'resolution': list(viewport.resolution), 'fill_frame': viewport.fill_frame}
    capture_state.paused = True
    timeline.pause()
    try:
        viewport.fill_frame = False
        viewport.resolution = (512, 384)
        for _ in range(30):
            await app.next_update_async()
        viewport.resolution = (512, 384)
        for _ in range(10):
            await app.next_update_async()
        if tuple(viewport.resolution) != (512, 384):
            raise RuntimeError('Viewport resolution did not settle at 512x384')
        stage = omni.usd.get_context().get_stage()
        ocean = stage.GetPrimAtPath('/World/Ocean')
        material, relationship = UsdShade.MaterialBindingAPI(ocean).ComputeBoundMaterial()
        if not material:
            raise RuntimeError('No effective ocean material binding')
        bindings = []
        ancestor = ocean
        while ancestor and not ancestor.IsPseudoRoot():
            bindings += [{'prim': str(ancestor.GetPath()), 'relationship': r.GetName(),
                          'targets': [str(p) for p in r.GetTargets()],
                          'metadata': value(r.GetAllMetadata())}
                         for r in ancestor.GetRelationships() if r.GetName().startswith('material:binding')]
            ancestor = ancestor.GetParent()
        geometries = []
        cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ['default', 'render', 'proxy'])
        for prim in Usd.PrimRange(ocean):
            if not prim.IsA(UsdGeom.Mesh):
                continue
            mesh = UsdGeom.Mesh(prim)
            counts = list(mesh.GetFaceVertexCountsAttr().Get())
            indices = list(mesh.GetFaceVertexIndicesAttr().Get())
            edges = Counter(); offset = 0
            for count in counts:
                face = indices[offset:offset+count]; offset += count
                for a, b in zip(face, face[1:]+face[:1]):
                    edges[tuple(sorted((a, b)))] += 1
            bounds = cache.ComputeWorldBound(prim).ComputeAlignedRange()
            normals = mesh.GetNormalsAttr().Get()
            geometries.append({'path': str(prim.GetPath()), 'points': len(mesh.GetPointsAttr().Get()),
                'faces': len(counts), 'boundary_edges': sum(v == 1 for v in edges.values()),
                'nonmanifold_edges': sum(v > 2 for v in edges.values()),
                'orientation': mesh.GetOrientationAttr().Get(), 'double_sided': mesh.GetDoubleSidedAttr().Get(),
                'normals_interpolation': mesh.GetNormalsInterpolation(),
                'normal_y_range': [min(n[1] for n in normals), max(n[1] for n in normals)] if normals else None,
                'world_transform': value(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())),
                'world_bounds_min': value(bounds.GetMin()), 'world_bounds_max': value(bounds.GetMax())})
        seconds = timeline.get_current_time()
        frozen, sampled = freeze_stage(stage, Usd.TimeCode(seconds * stage.GetTimeCodesPerSecond()))
        frozen.GetRootLayer().Export(str(OUT/'baseline/scene.usda'))
        write('baseline/material.json', {'bound_material': str(material.GetPath()),
              'effective_relationship': str(relationship.GetPath()) if relationship else None,
              'bindings_on_ocean_and_ancestors': bindings,
              'material_prims': [{'path': str(p.GetPath()), 'type': p.GetTypeName(), 'attributes': attributes(p)}
                                 for p in Usd.PrimRange(material.GetPrim())], 'geometry': geometries,
              'stage_units': {'meters_per_unit': UsdGeom.GetStageMetersPerUnit(stage),
                              'authored': stage.HasAuthoredMetadata('metersPerUnit'),
                              'up_axis': UsdGeom.GetStageUpAxis(stage)},
              'limitation': 'Authored/resolved USD values only; unauthored MDL defaults and shader distance scaling still require installed-definition checks.'})
        manager = app.get_extension_manager()
        write('baseline/runtime.json', {'kit_build': app.get_build_version(),
              'extensions': [{k: e.get(k) for k in ('id', 'name', 'version', 'enabled')}
                             for e in manager.get_extensions() if e.get('enabled')],
              'renderer_settings': settings_record(), 'projection': record_projection(stage, viewport),
              'timeline_seconds': seconds, 'frozen_attributes': sampled,
              'lights': [{'path': str(p.GetPath()), 'attributes': attributes(p)}
                         for p in stage.Traverse() if 'Light' in p.GetTypeName()],
              'capture': {'route': 'omni.kit.viewport.utility.capture_viewport_to_file', 'resolution': [512, 384],
                          'settling_updates': 40, 'completion_frames_per_capture': 5,
                          'note': 'Update counts are not measured renderer samples.'}})
        captures = []
        for name in ('warmup.png', 'baseline_01.png', 'baseline_02.png', 'baseline_03.png'):
            gpu = gpu_preflight(768)
            started = time.monotonic()
            job = capture_viewport_to_file(viewport, file_path=str(OUT/'baseline'/name))
            await asyncio.wait_for(job.wait_for_result(completion_frames=5), timeout=60)
            captures.append({'file': name, 'gpu_before': gpu, 'elapsed_seconds': time.monotonic()-started})
            write('baseline/captures.json', captures)
        write('qa/runtime_execution.json', {'status': 'executed', 'capture_count': 4,
              'note': 'Baseline evidence collected; acceptance measurements and rollback validation are separate.'})
    finally:
        viewport.fill_frame = previous['fill_frame']
        viewport.resolution = tuple(previous['resolution'])
        capture_state.paused = previous['paused']
        if previous['playing']:
            timeline.play()


async def main():
    try:
        await asyncio.wait_for(audit(), timeout=300)
    except Exception:
        write('qa/runtime_execution.json', {'status': 'failed', 'traceback': traceback.format_exc()})


TASK = asyncio.ensure_future(main())
