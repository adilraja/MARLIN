"""Render-only closure of the existing regular ocean grid; no wave model."""
import math
from functools import lru_cache
import numpy as np


def grid_topology(resolution):
    n = resolution + 1
    faces = []
    for row in range(resolution):
        for col in range(resolution):
            i = row*n+col
            faces.append([i, i+n, i+n+1, i+1])
    return faces


def perimeter(resolution):
    n = resolution+1
    return ([r*n for r in range(n)] +
            [resolution*n+c for c in range(1,n)] +
            [r*n+resolution for r in range(resolution-1,-1,-1)] +
            list(range(resolution-1,0,-1)))


def cross(a,b):
    return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])


def face_normal(points,face):
    a,b,c=(points[i] for i in face[:3])
    v=cross(tuple(b[i]-a[i] for i in range(3)),tuple(c[i]-a[i] for i in range(3)))
    length=math.sqrt(sum(x*x for x in v))
    if length <= 1e-12:
        raise ValueError('Degenerate enclosure face')
    return tuple(x/length for x in v)


def topology(resolution):
    faces=grid_topology(resolution)
    ring=perimeter(resolution)
    count=(resolution+1)**2
    centre=count+len(ring)
    for i,a in enumerate(ring):
        j=(i+1)%len(ring);b=ring[j]
        faces.append([b,a,count+i,count+j])
    for i in range(len(ring)):
        faces.append([centre,count+(i+1)%len(ring),count+i])
    return faces


@lru_cache(maxsize=4)
def top_normal_indices(resolution):
    return np.array([i for face in grid_topology(resolution) for i in face],dtype=np.int32)


def enclose(points,normals,resolution,bottom_y,faces=None,arrays=False):
    """Append a bottom ring/centre and return independent corner normals."""
    count=(resolution+1)**2
    if len(points)!=count or len(normals)!=count:
        raise ValueError('Expected the original regular-grid surface arrays')
    source=np.asarray(points,dtype=np.float64)
    normal_values=np.asarray(normals,dtype=np.float64)
    if not math.isfinite(bottom_y) or not np.isfinite(source).all() or not np.isfinite(normal_values).all():
        raise ValueError('Nonfinite enclosure coordinates')
    if source[:,1].min() <= bottom_y:
        raise ValueError('Enclosure bottom intersects the animated surface')
    ring=perimeter(resolution)
    lower=source[ring].copy();lower[:,1]=bottom_y
    output=np.concatenate((source,lower,lower.mean(axis=0,keepdims=True)))
    faces=topology(resolution) if faces is None else faces
    top_count=resolution**2
    boundary_faces=faces[top_count:]
    triangles=output[np.array([face[:3] for face in boundary_faces])]
    boundary_normals=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
    lengths=np.linalg.norm(boundary_normals,axis=1)
    if np.any(lengths<=1e-12):raise ValueError('Degenerate enclosure face')
    boundary_normals/=lengths[:,None]
    corners=np.concatenate((normal_values[top_normal_indices(resolution)],
        np.repeat(boundary_normals,[len(face) for face in boundary_faces],axis=0)))
    extent=[tuple(output.min(axis=0)),tuple(output.max(axis=0))]
    if arrays:return output,corners,extent
    return [tuple(p) for p in output], [tuple(n) for n in corners], extent


def validate(points,faces,resolution):
    from collections import Counter
    directed=Counter((a,b) for face in faces for a,b in zip(face,face[1:]+face[:1]))
    undirected=Counter()
    for (a,b),n in directed.items():undirected[tuple(sorted((a,b)))]+=n
    boundary=sum(n==1 for n in undirected.values())
    nonmanifold=sum(n!=2 for n in undirected.values())
    same_direction=sum(directed[(a,b)]!=directed[(b,a)] for a,b in undirected)
    top=faces[:resolution**2]
    top_up=min(face_normal(points,f)[1] for f in top)
    side=faces[resolution**2:resolution**2+4*resolution]
    centre=points[-1]
    side_out=min(sum(face_normal(points,f)[i]*(sum(points[v][i] for v in f)/len(f)-centre[i])
                     for i in (0,2)) for f in side)
    bottom_down=max(face_normal(points,f)[1] for f in faces[-4*resolution:])
    if boundary or nonmanifold or same_direction or top_up<=0 or side_out<=0 or bottom_down>=0:
        raise ValueError('Closed-medium orientation/topology check failed')
    return {'boundary_edges':boundary,'nonmanifold_edges':nonmanifold,
            'same_direction_shared_edges':same_direction,'minimum_top_normal_y':top_up,
            'minimum_outward_side_dot':side_out,'maximum_bottom_normal_y':bottom_down,
            'points':len(points),'faces':len(faces),'duplicated_top_faces':0,'shared_top_seam_indices':True}
