"""Static, manifest-driven inspection of new survey assets (not calibration)."""

import math

import omni.usd
from pydantic import BaseModel, Field
from pxr import Gf, Usd, UsdGeom

from .api import router
from .camera import _active_viewport
from .cetacean import CetaceanSpawnDataModel, spawn_cetacean
from .survey_spec import PROJECT_ROOT, asset_inventory


class SurveyGalleryRequest(BaseModel):
    elevation: float = Field(default=800.0)
    spacing: float = Field(default=1200.0, gt=0)
    display_size: float = Field(default=700.0, gt=0)
    columns: int = Field(default=3, ge=1, le=6)
    activate_viewport_camera: bool = True


def inspection_transform(minimum, maximum, target, display_size):
    """Fit full bounds into a slot, preserving relative native proportions."""
    values = (*minimum, *maximum, *target, display_size)
    if not all(math.isfinite(v) for v in values) or display_size <= 0:
        raise ValueError("Inspection bounds and placement must be finite")
    dimensions = [b - a for a, b in zip(minimum, maximum)]
    if min(dimensions) < 0 or max(dimensions) <= 0:
        raise ValueError("Asset has empty or degenerate bounds")
    scale = display_size / max(dimensions)
    position = [t - scale * (a + b) / 2 for a, b, t in zip(minimum, maximum, target)]
    return scale, position


@router.get('/scene/survey/gallery/inventory', summary='List survey assets and calibration gaps')
async def survey_gallery_inventory():
    return {'ok': True, 'animals': asset_inventory()}


@router.post('/scene/survey/gallery', summary='Create a static inspection gallery for available survey assets')
async def create_survey_gallery(data: SurveyGalleryRequest):
    if not all(math.isfinite(v) for v in (data.elevation, data.spacing, data.display_size)) or data.display_size >= data.spacing:
        return {'ok': False, 'error': 'Use finite dimensions with display_size smaller than spacing.'}
    stage = omni.usd.get_context().get_stage()
    if stage is None:
        return {'ok': False, 'error': 'No live USD stage is open.'}
    inventory = asset_inventory()
    available = [a for a in inventory if a['available']]
    if not available:
        return {'ok': False, 'error': 'No converted survey assets are available.'}
    rows = (len(available) + data.columns - 1) // data.columns
    animals = []
    for index, asset in enumerate(available):
        row, column = divmod(index, data.columns)
        target = ((column - (min(data.columns, len(available)) - 1) / 2) * data.spacing,
                  data.elevation, (row - (rows - 1) / 2) * data.spacing)
        name = 'SurveyInspect_' + asset['species_id']
        path = '/World/Cetaceans/' + name
        existing = stage.GetPrimAtPath(path)
        # Only replace prims created by this endpoint.
        if existing and existing.GetCustomDataByKey('marlinSurveyInspection') != True:
            animals.append({'ok': False, 'species': asset['species_id'], 'error': f'Unowned prim at {path}'})
            continue
        try:
            result = await spawn_cetacean(CetaceanSpawnDataModel(
                name=name, asset_path=str(PROJECT_ROOT / asset['usd_path']),
                position=(0, 0, 0), model_rotation=(0, 0, 0), scale=1))
            if not result.get('ok'):
                animals.append({**result, 'species': asset['species_id']})
                continue
            prim = stage.GetPrimAtPath(path)
            prim.SetCustomDataByKey('marlinSurveyInspection', True)
            bounds = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ['default', 'render', 'proxy']).ComputeWorldBound(prim).ComputeAlignedRange()
            minimum, maximum = tuple(bounds.GetMin()), tuple(bounds.GetMax())
            scale, position = inspection_transform(minimum, maximum, target, data.display_size)
            xform = UsdGeom.XformCommonAPI(prim)
            xform.SetScale(Gf.Vec3f(scale, scale, scale))
            xform.SetTranslate(Gf.Vec3d(*position))
            meshes = [str(p.GetPath()) for p in Usd.PrimRange(prim) if p.IsA(UsdGeom.Mesh)]
            animals.append({**result, 'species': asset['species_id'], 'common_name': asset['common_name'],
                            'scale': scale, 'position': position, 'slot_center': target,
                            'native_bounds_min': minimum, 'native_bounds_max': maximum,
                            'native_dimensions': [b-a for a,b in zip(minimum,maximum)],
                            'mesh_paths': meshes, 'possible_helpers': [p for p in meshes if 'icosphere' in p.lower()],
                            'calibration_status': 'uncalibrated_display_only',
                            'manifest': f"assets/survey_species/{asset['species_id']}/manifest.json"})
        except Exception as exc:
            animals.append({'ok': False, 'species': asset['species_id'], 'prim_path': path, 'error': str(exc)})
    camera_result = {'activated': False}
    if data.activate_viewport_camera:
        viewport = _active_viewport()
        if viewport is None:
            camera_result['error'] = 'No active viewport; select the inspection prims manually.'
        else:
            camera_path = '/World/Cameras/SurveyInspectionCamera'
            previous = str(viewport.camera_path)
            span = max(data.columns, rows, 3) * data.spacing
            camera = UsdGeom.Camera.Define(stage, camera_path)
            camera.GetFocalLengthAttr().Set(35)
            camera.GetHorizontalApertureAttr().Set(36)
            camera.GetVerticalApertureAttr().Set(24)
            camera.GetClippingRangeAttr().Set(Gf.Vec2f(1, max(100000, span * 20)))
            view = Gf.Matrix4d(1)
            view.SetLookAt(Gf.Vec3d(span * 0.5, data.elevation + span * 1.5, -span * 2),
                           Gf.Vec3d(0, data.elevation, 0), Gf.Vec3d(0, 1, 0))
            xform = UsdGeom.Xformable(camera)
            xform.ClearXformOpOrder()
            xform.AddTransformOp().Set(view.GetInverse())
            viewport.camera_path = camera_path
            camera_result = {'activated': True, 'camera_path': camera_path, 'previous_camera_path': previous}
    return {'ok': all(a['ok'] for a in animals), 'loaded_count': sum(a['ok'] for a in animals),
            'animals': animals, 'missing_species': [a['species_id'] for a in inventory if not a['available']],
            'camera': camera_result,
            'note': 'Native orientation; each full asset bounds fitted independently for inspection. Sizes are not physically calibrated; helper geometry is retained.'}
