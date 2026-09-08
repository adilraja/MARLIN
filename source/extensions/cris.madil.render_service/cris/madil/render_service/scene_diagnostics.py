"""Read-only diagnostics for differences between authored and visible scenes."""
import omni.usd
from pxr import Usd, UsdGeom
from .api import router
from .camera import _active_viewport


@router.get('/debug/scene/inspection', summary='Inspect live layers, ocean and animal transforms')
async def inspect_scene():
    stage = omni.usd.get_context().get_stage()
    if stage is None:
        return {'ok': False, 'error': 'No stage'}
    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ['default', 'render', 'proxy'])
    paths = ['/World', '/World/Ocean', '/World/Environment', '/Environment']
    animals = stage.GetPrimAtPath('/World/Cetaceans')
    if animals:
        paths.extend(str(p.GetPath()) for p in animals.GetChildren())
    records = []
    for path in paths:
        prim = stage.GetPrimAtPath(path)
        if not prim:
            continue
        record = {'path': path, 'type': prim.GetTypeName(),
                  'prim_stack': [str(s.layer.identifier) for s in prim.GetPrimStack()]}
        if prim.IsA(UsdGeom.Imageable):
            record['visibility'] = str(UsdGeom.Imageable(prim).ComputeVisibility())
            bounds = cache.ComputeWorldBound(prim).ComputeAlignedRange()
            if not bounds.IsEmpty():
                record['bounds_min'] = list(bounds.GetMin())
                record['bounds_max'] = list(bounds.GetMax())
        if prim.IsA(UsdGeom.Xformable):
            record['xform_ops'] = [{'name': op.GetOpName(), 'value': str(op.Get()),
                'layers': [str(s.layer.identifier) for s in op.GetAttr().GetPropertyStack()]}
                for op in UsdGeom.Xformable(prim).GetOrderedXformOps()]
        records.append(record)
    viewport = _active_viewport()
    return {'ok': True, 'root_layer': stage.GetRootLayer().identifier,
            'edit_layer': stage.GetEditTarget().GetLayer().identifier,
            'layers': [layer.identifier for layer in stage.GetLayerStack()],
            'camera': str(viewport.camera_path) if viewport else None,
            'prims': records}
