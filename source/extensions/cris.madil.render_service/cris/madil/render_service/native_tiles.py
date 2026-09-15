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


async def capture_tiles(stage, viewport, config, directory, preflight):
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
    canvas=Image.new('RGB',(width,height))
    records=[]
    seams=[]
    try:
        for index,spec in enumerate(tile_specs(width,height)):
            preflight()
            apply_tile(camera,original[:2],width,height,spec)
            viewport.fill_frame=False
            viewport.resolution=tuple(spec['resolution'])
            for _ in range(120):
                await omni.kit.app.get_app().next_update_async()
            viewport.fill_frame=False
            viewport.resolution=tuple(spec['resolution'])
            for _ in range(15):
                await omni.kit.app.get_app().next_update_async()
            filename='tile_%02d.png'%index
            capture=capture_viewport_to_file(viewport,file_path=str(directory/filename))
            await capture.wait_for_result(completion_frames=5)
            projection=record_projection(stage,viewport)
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
            # Compare duplicate native rays in neighbouring overlap strips.
            for prior in records:
                aa,bb,cc,dd=prior['bounds']
                left,top,right,bottom=max(a,aa),max(b,bb),min(c,cc),min(d,dd)
                if left>=right or top>=bottom:
                    continue
                with Image.open(directory/prior['file']) as previous:
                    old=np.array(previous.convert('RGB').crop((left-aa,top-bb,right-aa,bottom-bb)),dtype=float)
                new=np.array(tile.crop((left-a,top-b,right-a,bottom-b)),dtype=float)
                delta=np.abs(old-new)
                seams.append(dict(tiles=[prior['file'],filename],mean_absolute_rgb_error=float(delta.mean()),
                                  max_absolute_rgb_error=float(delta.max())))
            canvas.paste(tile.crop((x-a,y-b,r-a,s-b)),(x,y))
            records.append(dict(spec,file=filename,projection=projection))
    finally:
        for attr,value in zip(attrs,original): attr.Set(value)
    canvas.save(directory/'rgb.png')
    result=image_projection(stage,str(viewport.camera_path),(width,height),viewport.time)
    result.update(projection_metadata_version=2,
                  actual_view_matrix=result['capture_view_matrix'],actual_projection_matrix=result['capture_projection_matrix'],
                  actual_viewport_resolution=list(viewport.resolution),
                  assembled_image_resolution=[width,height],
                  render_product={'resolution':[width,height],'kind':'CPU assembly of native-pixel off-axis render products; not one GPU product'},
                  native_tiling=dict(grid=[8,8],guard_pixels=16,settling_frames_per_tile=135,tiles=records,overlap_checks=seams,
                    overlap_mean_error_limit=2.0,overlaps_passed=all(s['mean_absolute_rgb_error']<=2 for s in seams),
                    assembly='Unscaled core crops; no blending. Full camera restored. Screen-space effects may cause differences; overlap checks are empirical, not universal equivalence.'))
    return result
