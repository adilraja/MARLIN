"""Reference-plane maps aligned with captured pixels; no target-range fitting."""
import struct
import zlib
import numpy as np
from .bartlett_geometry import maps_chunk, footprint, nominal


def geometry_inputs(config):
    return dict(camera_to_plane_m=config.height_above_target_m,
                focal_length_mm=config.focal_length_mm,
                sensor_width_mm=config.image_width_px*config.pixel_pitch_um/1000,
                sensor_height_mm=config.image_height_px*config.pixel_pitch_um/1000,
                image_width_px=config.image_width_px, image_height_px=config.image_height_px,
                pitch_from_nadir_deg=config.pitch_deg, rolls_deg=[config.roll_deg])


def write_heatmap(path, values):
    """Lossless diagnostic PNG: blue=minimum, yellow=maximum, black=invalid."""
    valid = np.isfinite(values)
    lo, hi = float(values[valid].min()), float(values[valid].max())
    t = np.zeros(values.shape)
    # A constant nadir map must not amplify floating-point roundoff into bands.
    if hi-lo > max(abs(lo),abs(hi),1)*1e-9:
        t[valid] = (values[valid]-lo)/(hi-lo)
    rgb = np.stack((255*t, 80+175*t, 180*(1-t)), axis=-1).astype('uint8')
    rgb[~valid] = 0
    h, w = values.shape
    def chunk(tag, data):
        return struct.pack('!I',len(data))+tag+data+struct.pack('!I',zlib.crc32(tag+data)&0xffffffff)
    raw = b''.join(b'\0'+row.tobytes() for row in rgb)
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',w,h,8,2,0,0,0))+
                     chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b''))


def export_maps(directory, config, translation_m):
    c = geometry_inputs(config)
    maps = {}
    for start in range(0,config.image_height_px,64):
        values = maps_chunk(c,config.roll_deg,start,min(start+64,config.image_height_px))
        for key, value in values.items():
            if key not in maps:
                maps[key] = np.empty((config.image_height_px,config.image_width_px),dtype=np.float64)
            maps[key][start:start+len(value)] = value
    np.savez_compressed(directory/'directional_gsd.npz', **maps)
    ranges = {}
    for key, values in maps.items():
        write_heatmap(directory/(key+'.png'),values)
        ranges[key] = dict(min=float(np.nanmin(values)),max=float(np.nanmax(values)),
                           invalid_pixels=int(np.count_nonzero(~np.isfinite(values))),
                           diagnostic_png=key+'.png')
    fp = footprint(c,config.roll_deg)
    fp['corners_xz_m'] = [[x+translation_m[0],z+translation_m[2]] for x,z in fp['corners_xz_m']]
    return dict(file='directional_gsd.npz', shape_hw=[config.image_height_px,config.image_width_px],
                geometry_inputs=c, ranges=ranges, footprint=fp,
                reference_plane_y_m=config.target_plane_y_m,
                nominal_nadir_gsd_cm_px=nominal(c),
                definition='Forward pixel-centre neighbour distances; image width and height separate. Last column width and last row height are NaN. Pixel area uses projected pixel corners.',
                anisotropy_definition='height-direction spacing divided by width-direction spacing',
                heatmap_legend='Per-map linear scale: blue=reported minimum, yellow=maximum, black=NaN; no shared scale. Numerically uniform ranges (relative spread <=1e-9) use solid blue; numeric maps are unchanged.',
                applicability='Flat mean sea reference plane only. Not wave-surface, body-surface or refracted underwater GSD.',
                sampling='Actual preview pixels, not native sensor pixels; no upsampling or relabelling.')
