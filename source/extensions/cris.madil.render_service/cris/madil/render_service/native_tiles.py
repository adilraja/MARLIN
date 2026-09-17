"""Native pixels via off-axis camera tiles, never preview upscaling."""
import numpy as np
import asyncio
from .capture_projection import image_projection, record_projection


def tile_specs(width, height, guard=16):
    if width % 8 or height % 8:
        raise ValueError('Native tile grid requires dimensions divisible by eight')
    for row in range(8):
        for col in range(8):
            x,y=col*width//8,row*height//8
            right,bottom=x+width//8,y+height//8
            # Constant buffer size avoids allocator growth between edge/interior
            # tiles. Outer guard rays are rendered but never included in RGB.
            a,b=x-guard,y-guard
            c,d=right+guard,bottom+guard
            yield dict(core=[x,y,right,bottom],bounds=[a,b,c,d],resolution=[c-a,d-b])


def apply_tile(camera, full_aperture, width, height, spec):
    a,b,c,d=spec['bounds']
    aw,ah=full_aperture
    camera.GetHorizontalApertureAttr().Set(aw*(c-a)/width)
    camera.GetVerticalApertureAttr().Set(ah*(d-b)/height)
    camera.GetHorizontalApertureOffsetAttr().Set(aw*((a+c)/(2*width)-.5))
    camera.GetVerticalApertureOffsetAttr().Set(ah*(.5-(b+d)/(2*height)))


async def wait_for_fixed_resolution(viewport, resolution, frames, max_resets=3):
    """Wait a delivered-frame batch and validate the tile buffer size.

    UI/renderer callbacks may reapply the window size asynchronously. Correct
    only that buffer size, restart settling, and fail if it will not stay fixed.
    No camera parameter or renderer-quality setting is adjusted here.
    """
    expected=tuple(resolution)
    resets=0
    while True:
        # Use a single batch wait as documented by the viewport API. Repeated
        # one-frame waits may observe the same already-delivered frame.
        await viewport.wait_for_rendered_frames(frames)
        if tuple(viewport.resolution)!=expected or viewport.fill_frame:
            resets+=1
            if resets>max_resets:
                raise ValueError('Viewport resolution will not remain fixed for native capture')
            viewport.fill_frame=False
            viewport.resolution=expected
        else:
            return resets


async def capture_tiles(stage, viewport, config, directory, preflight, diagnostic=None):
    # Import before changing the camera. Absence fails safely, not midway.
    from PIL import Image
    from pxr import UsdGeom
    import omni.kit.app
    from omni.kit.viewport.utility import capture_viewport_to_file
    camera=UsdGeom.Camera(stage.GetPrimAtPath(viewport.camera_path))
    attrs=[camera.GetHorizontalApertureAttr(),camera.GetVerticalApertureAttr(),
           camera.GetHorizontalApertureOffsetAttr(),camera.GetVerticalApertureOffsetAttr()]
    original=[a.Get() for a in attrs]
    if original[2:] != [0,0]:
        raise ValueError('Tiled profile requires the declared centred full camera')
    width,height=config.image_width_px,config.image_height_px
    canvas=Image.new('RGB',(width,height)) if diagnostic is None else None
    records=[]
    seams=[]
    guard=64 if diagnostic=='guard64' else 16
    specs=list(tile_specs(width,height,guard))
    indices=([3] if diagnostic=='sdk_smoke' else [3,3,3] if diagnostic in ('sdk_single','sdk_low_repeat') else [3,4,3,4] if diagnostic=='sdk_pair' else [3,4,4,5,11,12,13]) if diagnostic else list(range(len(specs)))
    rendered_frame_wait=diagnostic in ('rendered_frames','pt_denoised','pt_raw','pt_raw_8192')
    try:
        for sample,index in enumerate(indices):
            spec=specs[index]
            preflight()
            apply_tile(camera,original[:2],width,height,spec)
            filename=('sample_%02d_tile_%02d.png'%(sample,index)) if diagnostic else 'tile_%02d.png'%index
            if diagnostic in ('sdk_single','sdk_pair','sdk_smoke','sdk_low_repeat'):
                from .sdk_tile_capture import capture_sdk_tile
                projection=await capture_sdk_tile(stage,viewport,spec['resolution'],directory/filename,samples=16 if diagnostic in ('sdk_smoke','sdk_low_repeat') else 1024)
                resolution_resets=0
            else:
                projection,resolution_resets=await capture_legacy_tile(stage,viewport,spec,directory/filename,rendered_frame_wait)
            if diagnostic:
                import carb.settings
                settings=carb.settings.get_settings()
                projection['diagnostic_renderer_settings']={key:settings.get(key) for key in (
                    '/rtx/rendermode','/rtx/pathtracing/spp','/rtx/pathtracing/totalSpp',
                    '/rtx/pathtracing/optixDenoiser/enabled')}
            for attempt in range(100):
                try:
                    with Image.open(directory/filename) as image:
                        tile=image.convert('RGB')
                    break
                except (OSError,ValueError):
                    if attempt==99:
                        raise RuntimeError('Tile PNG writer did not finish within 10 seconds')
                    await asyncio.sleep(.1)
            if list(tile.size)!=spec['resolution']:
                raise ValueError('Tile image dimensions do not match camera')
            a,b,c,d=spec['bounds'];x,y,r,s=spec['core']
            for prior in records:
                aa,bb,cc,dd=prior['bounds']
                left,top,right,bottom=max(a,aa),max(b,bb),min(c,cc),min(d,dd)
                if left>=right or top>=bottom:
                    continue
                with Image.open(directory/prior['file']) as previous:
                    old=np.array(previous.convert('RGB').crop((left-aa,top-bb,right-aa,bottom-bb)),dtype=float)
                new=np.array(tile.crop((left-a,top-b,right-a,bottom-b)),dtype=float)
                delta=np.abs(old-new)
                seams.append(dict(tiles=[prior['file'],filename],tile_indices=[prior['tile_index'],index],
                                  identical_tile_repeat=prior['tile_index']==index,
                                  overlap_bounds=[left,top,right,bottom],mean_absolute_rgb_error=float(delta.mean()),
                                  max_absolute_rgb_error=float(delta.max())))
            if canvas is not None:
                canvas.paste(tile.crop((x-a,y-b,r-a,s-b)),(x,y))
            records.append(dict(spec,tile_index=index,file=filename,projection=projection,
                                resolution_resets=resolution_resets))
    finally:
        for attr,value in zip(attrs,original): attr.Set(value)
    if canvas is not None:
        canvas.save(directory/'rgb.png')
    result=image_projection(stage,str(viewport.camera_path),(width,height),viewport.time)
    result.update(projection_metadata_version=2,
                  actual_view_matrix=result['capture_view_matrix'],actual_projection_matrix=result['capture_projection_matrix'],
                  actual_viewport_resolution=list(viewport.resolution),
                  assembled_image_resolution=[width,height] if canvas is not None else None,
                  render_product=({'resolution':[width,height],'kind':'CPU assembly of native-pixel off-axis render products; not one GPU product'}
                                  if canvas is not None else {'resolution':None,'reference_resolution':[width,height],
                                    'kind':'Focused off-axis products only; no full image assembled'}),
                  native_tiling=dict(grid=[8,8],complete_image=diagnostic is None,guard_pixels=guard,
                    settling_app_updates_per_tile=None if diagnostic in ('sdk_single','sdk_pair','sdk_smoke','sdk_low_repeat') else 135,
                    additional_rendered_frames_per_tile=None if diagnostic in ('sdk_single','sdk_pair','sdk_smoke','sdk_low_repeat') else (135 if rendered_frame_wait else 3),
                    settling_policy='SDK synchronized lifecycle; actual GPU samples unverified' if diagnostic in ('sdk_single','sdk_pair','sdk_smoke','sdk_low_repeat') else 'Delivered-frame batch, then dimension check; not a measured sample counter.',
                    tiles=records,overlap_checks=seams,
                    overlap_mean_error_limit=2.0,overlaps_passed=all(s['mean_absolute_rgb_error']<=2 for s in seams),
                    assembly='Unscaled core crops; no blending. Full camera restored. Screen-space effects may cause differences; overlap checks are empirical, not universal equivalence.'))
    return result


async def capture_legacy_tile(stage,viewport,spec,destination,rendered_frame_wait):
    import omni.kit.app
    from omni.kit.viewport.utility import capture_viewport_to_file
    viewport.fill_frame=False
    viewport.resolution=tuple(spec['resolution'])
    for _ in range(120):
        await omni.kit.app.get_app().next_update_async()
    viewport.fill_frame=False
    viewport.resolution=tuple(spec['resolution'])
    for _ in range(15):
        await omni.kit.app.get_app().next_update_async()
    # App updates need not correspond to delivered GPU frames. Also
    # guard against late callbacks resetting the buffer to UI size.
    settled_frames=135 if rendered_frame_wait else 3
    resolution_resets=await asyncio.wait_for(wait_for_fixed_resolution(
        viewport,spec['resolution'],settled_frames),timeout=90)
    # Fail before writing RGB if a renderer transition has reset the
    # product dimensions or conformed the authored camera aperture.
    record_projection(stage,viewport)
    capture=capture_viewport_to_file(viewport,file_path=str(destination))
    await capture.wait_for_result(completion_frames=5)
    projection=record_projection(stage,viewport)
    return projection,resolution_resets
