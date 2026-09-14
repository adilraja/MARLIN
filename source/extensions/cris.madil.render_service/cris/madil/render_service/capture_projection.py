"""Image projection is not ViewportAPI.projection (which uses UI aspect)."""
import math
from pxr import UsdGeom


def image_projection(stage, camera_path, resolution, time_code):
    camera = UsdGeom.Camera(stage.GetPrimAtPath(camera_path))
    if not camera:
        raise ValueError('Capture camera is missing')
    cam = camera.GetCamera(time_code)
    width, height = resolution
    if not math.isclose(cam.horizontalAperture/cam.verticalAperture, width/height, rel_tol=1e-6):
        raise ValueError('Capture camera aperture and image aspect disagree; conformed projection is not validated')
    frustum = cam.frustum
    return dict(capture_view_matrix=[list(r) for r in frustum.ComputeViewMatrix()],
                capture_projection_matrix=[list(r) for r in frustum.ComputeProjectionMatrix()],
                capture_projection_source='Authored USD camera frustum, matching full-image aspect and square pixels; not the UI projection',
                matrix_convention='USD/Gf row-vector world * view * projection; NDC x/y [-1,1], image origin top-left',
                capture_projection_validation='geometry_checked; raster validation recorded separately')


def record_projection(stage, viewport):
    resolution=tuple(viewport.resolution)
    result=image_projection(stage,str(viewport.camera_path),resolution,viewport.time)
    product=stage.GetPrimAtPath(viewport.render_product_path)
    if not product:
        raise ValueError('Capture render product is missing')
    cameras=[str(p) for p in product.GetRelationship('camera').GetTargets()]
    product_resolution=tuple(product.GetAttribute('resolution').Get())
    if cameras != [str(viewport.camera_path)] or product_resolution != resolution:
        raise ValueError('Render product camera/resolution differs from capture request')
    pixel_aspect=product.GetAttribute('pixelAspectRatio').Get()
    window=product.GetAttribute('dataWindowNDC').Get()
    if pixel_aspect is not None and not math.isclose(pixel_aspect,1):
        raise ValueError('Non-square render-product pixels are unsupported')
    if window is not None and tuple(window)!=(0,0,1,1):
        raise ValueError('Cropped render product is unsupported')
    result.update(actual_viewport_resolution=list(resolution),
                  ui_view_matrix=[list(r) for r in viewport.view],
                  ui_projection_matrix=[list(r) for r in viewport.projection],
                  ui_projection_note='ViewportAPI.projection describes the UI element; never use as capture-image intrinsics',
                  render_product=dict(path=str(product.GetPath()),camera=cameras[0],resolution=list(product_resolution),
                                      pixel_aspect_ratio=pixel_aspect,data_window_ndc=list(window) if window is not None else None))
    # Preserve field availability for existing consumers, but explicitly version
    # its corrected semantics. Old artifacts remain unchanged and untrusted.
    result.update(projection_metadata_version=2,
                  actual_view_matrix=result['capture_view_matrix'],
                  actual_projection_matrix=result['capture_projection_matrix'],
                  actual_matrix_alias_note='Version 2: aliases for capture-camera matrices; version 1 stored UI matrices')
    return result
