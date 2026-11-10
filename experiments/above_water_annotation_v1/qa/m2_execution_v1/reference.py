"""Independent CPU pinhole/ray/triangle references; never a replacement label provider."""
import numpy as np

W, H = 512, 384
YY, XX = np.mgrid[:H, :W]
PIXELS = np.c_[XX.ravel()+.5, YY.ravel()+.5]


def project(points, view, projection):
    p = np.c_[points, np.ones(len(points))] @ np.array(view)
    # This bounded validation rejects unsupported near/far crossings explicitly.
    if len(p) and (np.any(-p[:,2] < 1) or np.any(-p[:,2] > 5000)):
        raise ValueError('Near/far crossing is unsupported; no fabricated box')
    clip = p @ np.array(projection)
    if np.any(clip[:,3] <= 0): raise ValueError('Behind-camera geometry')
    ndc = clip[:,:3]/clip[:,3:4]
    return np.c_[(ndc[:,0]+1)*W/2, (1-ndc[:,1])*H/2]


def clip_polygon(poly):
    poly = np.asarray(poly)
    for axis, limit, lower in ((0,0,True),(0,W,False),(1,0,True),(1,H,False)):
        if len(poly) == 0: break
        out = []
        for a, b in zip(poly, np.roll(poly,-1,axis=0)):
            ia = a[axis] >= limit if lower else a[axis] <= limit
            ib = b[axis] >= limit if lower else b[axis] <= limit
            if ia: out.append(a)
            if ia != ib: out.append(a+(b-a)*(limit-a[axis])/(b[axis]-a[axis]))
        poly = np.asarray(out)
    return poly


def geometry_box(points, triangles, view, projection):
    if not len(points): return None
    uv = project(points, view, projection); pieces = []
    for t in triangles:
        p = clip_polygon(uv[t])
        if len(p): pieces.extend(p)
    if not pieces: return None
    pieces = np.asarray(pieces)
    return [*pieces.min(0).tolist(), *pieces.max(0).tolist()]


def raster(points, triangles, view, projection):
    uv = project(points, view, projection); result = np.zeros((H,W),dtype=bool)
    for t in triangles:
        p = uv[t]
        lo = np.maximum(np.floor(p.min(0)).astype(int),0)
        hi = np.minimum(np.ceil(p.max(0)).astype(int),[W,H])
        if np.any(hi <= lo): continue
        yy,xx = np.mgrid[lo[1]:hi[1],lo[0]:hi[0]]; q = np.stack([xx+.5,yy+.5],axis=-1)
        cross = [(q[...,0]-a[0])*(b[1]-a[1])-(q[...,1]-a[1])*(b[0]-a[0]) for a,b in zip(p,np.roll(p,-1,axis=0))]
        cross = np.array(cross)
        hit = np.all(cross>=-1e-10,axis=0)|np.all(cross<=1e-10,axis=0)
        # Degenerate projected triangles have no raster interior.
        area = np.cross(p[1]-p[0],p[2]-p[0])
        if abs(area) > 1e-12: result[lo[1]:hi[1],lo[0]:hi[0]] |= hit
    return result


def rays(camera, view):
    local = np.c_[(PIXELS[:,0]-camera['cx_px'])/camera['fx_px'],
                  -(PIXELS[:,1]-camera['cy_px'])/camera['fy_px'], -np.ones(len(PIXELS))]
    inv = np.linalg.inv(view)
    return inv[3,:3], local @ inv[:3,:3]


def plane_hit(corners, origin, directions):
    a,b,_,d = np.array(corners); u = b-a; v = d-a; n = np.cross(u,v)
    denom = directions@n
    distance = ((a-origin)@n)/np.where(np.abs(denom)>1e-12,denom,np.inf)
    points = origin+distance[:,None]*directions
    rel = points-a
    gram = np.array([[u@u,u@v],[u@v,v@v]])
    co = np.c_[rel@u,rel@v] @ np.linalg.inv(gram)
    hit = (distance>0)&(np.abs(denom)>1e-12)&np.all(co>=-1e-9,axis=1)&np.all(co<=1+1e-9,axis=1)
    return hit.reshape(H,W),distance.reshape(H,W)


def plane_reference(record):
    if record['target_corners_scene_units'] is None: return np.zeros((H,W),dtype=bool)
    origin,directions = rays(record['camera'],np.array(record['projection']['actual_view_matrix']))
    hit,td = plane_hit(record['target_corners_scene_units'],origin,directions)
    if record['occluder_corners_scene_units'] is not None:
        occ,od = plane_hit(record['occluder_corners_scene_units'],origin,directions)
        hit &= ~(occ&(od<td))
    return hit


def boundary_band(record):
    result = np.zeros(H*W,dtype=bool)
    for corners in (record['target_corners_scene_units'],record['occluder_corners_scene_units']):
        if corners is None: continue
        uv = project(np.array(corners),record['projection']['actual_view_matrix'],record['projection']['actual_projection_matrix'])
        for a,b in zip(uv,np.roll(uv,-1,axis=0)):
            t = np.clip(((PIXELS-a)@(b-a))/np.sum((b-a)**2),0,1)
            result |= np.linalg.norm(PIXELS-(a+t[:,None]*(b-a)),axis=1) <= 1+1e-8
    return result.reshape(H,W)


def tight_box(mask):
    y,x = np.where(mask)
    return [int(x.min()),int(y.min()),int(x.max())+1,int(y.max())+1] if len(x) else None
