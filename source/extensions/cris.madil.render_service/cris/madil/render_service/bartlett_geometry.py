"""Flat-plane projection only. No published GSD targets or fitting in this module."""
import math
import numpy as np


def validate(c):
    for name in ('camera_to_plane_m','focal_length_mm','sensor_width_mm','sensor_height_mm'):
        if not math.isfinite(c[name]) or c[name]<=0:
            raise ValueError(name+' must be finite and positive')
    for name in ('image_width_px','image_height_px'):
        if type(c[name]) is not int or not 2<=c[name]<=20000:
            raise ValueError('Invalid image dimensions')
    for a in [c['pitch_from_nadir_deg'],*c['rolls_deg']]:
        if not math.isfinite(a) or abs(a)>=80:
            raise ValueError('Angles must be finite and below 80 degrees')


def basis(pitch_deg,roll_deg):
    p,r = np.deg2rad([pitch_deg,roll_deg])
    # Camera local axes: right, up, forward. Nadir = +X,-Z,-Y.
    rx = np.array([[1,0,0],[0,np.cos(p),-np.sin(p)],[0,np.sin(p),np.cos(p)]])
    rz = np.array([[np.cos(r),-np.sin(r),0],[np.sin(r),np.cos(r),0],[0,0,1]])
    return (rx@rz@np.array([[1,0,0],[0,0,-1],[0,-1,0]])).T


def project(c,roll,u,v):
    """Image-edge coordinates; pixel centres are i+0.5. Returns ground X,Z in metres."""
    right,up,forward = basis(c['pitch_from_nadir_deg'],roll)
    fx = c['focal_length_mm']*c['image_width_px']/c['sensor_width_mm']
    fy = c['focal_length_mm']*c['image_height_px']/c['sensor_height_mm']
    u,v = np.broadcast_arrays(np.asarray(u,dtype=float),np.asarray(v,dtype=float))
    ray = (forward + ((u-c['image_width_px']/2)/fx)[...,None]*right
           - ((v-c['image_height_px']/2)/fy)[...,None]*up)
    if np.any(ray[...,1]>=-1e-10):
        raise ValueError('Some image rays do not hit the ground plane in front of camera')
    t = -c['camera_to_plane_m']/ray[...,1]
    return ray[..., [0,2]]*t[...,None]


def nominal(c):
    return [100*c['camera_to_plane_m']*c['sensor_width_mm']/c['focal_length_mm']/c['image_width_px'],
            100*c['camera_to_plane_m']*c['sensor_height_mm']/c['focal_length_mm']/c['image_height_px']]


def maps_chunk(c,roll,start,stop):
    w,h = c['image_width_px'],c['image_height_px']
    u = np.arange(w)[None,:]+0.5
    v = np.arange(start,stop)[:,None]+0.5
    p = project(c,roll,u,v)
    gx = np.linalg.norm(project(c,roll,u+1,v)-p,axis=-1)*100
    gy = np.linalg.norm(project(c,roll,u,v+1)-p,axis=-1)*100
    gx[:,-1] = np.nan
    if stop==h:
        gy[-1,:] = np.nan
    ratio = gy/gx
    corners = [project(c,roll,u+du,v+dv) for du,dv in [(-.5,-.5),(.5,-.5),(.5,.5),(-.5,.5)]]
    # Two triangles, translated to a local origin to avoid cancellation.
    a,b,d = (corners[i]-corners[0] for i in (1,2,3))
    cross = lambda x,y: x[...,0]*y[...,1]-x[...,1]*y[...,0]
    area = np.abs(cross(a,b)+cross(b,d))*0.5*10000
    return {'gsd_width_cm_px':gx,'gsd_height_cm_px':gy,'anisotropy_height_over_width':ratio,'effective_pixel_area_cm2':area}


def footprint(c,roll):
    w,h = c['image_width_px'],c['image_height_px']
    p = project(c,roll,np.array([0,w,w,0]),np.array([0,0,h,h]))
    return {'roll_deg':roll,'corners_xz_m':p.tolist(),
            'edge_order':'top-left, top-right, bottom-right, bottom-left (image edges)',
            'top_edge_length_m':float(np.linalg.norm(p[1]-p[0])),
            'bottom_edge_length_m':float(np.linalg.norm(p[2]-p[3])),
            'x_extent_m':float(np.ptp(p[:,0])), 'z_extent_m':float(np.ptp(p[:,1]))}


def footprint_gaps(footprints):
    """Across-track gaps at common world-Z sections; no parameter adjustment."""
    ordered = sorted(footprints,key=lambda f: np.mean(np.array(f['corners_xz_m'])[:,0]))
    def section(p,z):
        xs=[]
        for a,b in zip(p,np.roll(p,-1,axis=0)):
            if min(a[1],b[1])-1e-8<=z<=max(a[1],b[1])+1e-8:
                if abs(b[1]-a[1])<1e-10:
                    xs.extend([a[0],b[0]])
                else:
                    xs.append(a[0]+(z-a[1])*(b[0]-a[0])/(b[1]-a[1]))
        return min(xs),max(xs)
    result=[]
    for left,right in zip(ordered,ordered[1:]):
        a,b = np.array(left['corners_xz_m']),np.array(right['corners_xz_m'])
        # Compare facing side edges only. At a slanted top/bottom corner,
        # a section through the whole polygon can hit the far outer tip and
        # misleadingly report a hundreds-of-metres "gap" across the array.
        left_edge,right_edge = a[[1,2]],b[[0,3]]
        low,high = max(left_edge[:,1].min(),right_edge[:,1].min()),min(left_edge[:,1].max(),right_edge[:,1].max())
        if low>high:
            result.append({'roll_pair_deg':[left['roll_deg'],right['roll_deg']], 'common_z_overlap':False})
            continue
        zs = sorted({low,high,*[z for z in [*a[:,1],*b[:,1]] if low<=z<=high]})
        gaps = [section(b,z)[0]-section(a,z)[1] for z in zs]
        result.append({'roll_pair_deg':[left['roll_deg'],right['roll_deg']],
                       'definition':'Across-track X clearance at common world Z, restricted to overlap of facing side edges; negative means overlap',
                       'sections_z_m':zs,'gaps_m':gaps,'min_gap_m':min(gaps),'max_gap_m':max(gaps)})
    return result
