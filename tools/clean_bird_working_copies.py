"""Blender preprocessing: versioned support-removal candidates and measurements.

Run with official Blender --background --python tools/clean_bird_working_copies.py.
Original inputs are never edited. Outputs are cleanup candidates pending contact QA.
Cuts use inspected Blender world coordinates (Z up), not MARLIN scene units.
"""
import bpy
import bmesh
import json
import hashlib
import shutil
import argparse
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
RECIPES = {
    'common_guillemot': {
        'cut_z': -0.43, 'max_x': 0.95, 'floor_z': -0.75,
        'contact_refinement': True,
        'foot_front_polygon_px': [[268,546],[268,487],[348,405],[375,371],
            [423,370],[505,400],[500,420],[401,416],[364,485],
            [342,548],[305,570],[300,551]],
        'foot_max_y': -0.25,
        'projection': {'center_x':0.3,'center_z':-0.45,'size':2.2,'pixels':900},
    },
    'gannet': {'cut_z': 0.13, 'max_x': 0.13},
    'storm_petrel': {'cut_z': -5.25, 'max_x': None},
    'common_tern_-_sterna_hirundo': {'cut_z': None, 'max_x': None},
}


def inside_polygon(x, y, polygon):
    inside = False
    for (ax, ay), (bx, by) in zip(polygon, polygon[1:] + polygon[:1]):
        if (ay > y) != (by > y) and x < (bx-ax)*(y-ay)/(by-ay)+ax:
            inside = not inside
    return inside


def remove_support(p, recipe):
    if recipe.get('contact_refinement'):
        projection=recipe['projection']; factor=projection['pixels']/projection['size']
        px=projection['pixels']/2+(p.x-projection['center_x'])*factor
        py=projection['pixels']/2-(p.z-projection['center_z'])*factor
        if p.y < recipe['foot_max_y'] and inside_polygon(px,py,recipe['foot_front_polygon_px']):
            return False
        # Follow the visible underside down toward the original tail.
        boundary=-0.34-0.48*max(0,p.x-0.5)
        return p.z < boundary
    return (p.z < recipe.get('floor_z', -float('inf')) or
            (p.z < recipe['cut_z'] and (recipe['max_x'] is None or p.x < recipe['max_x'])))


def bounds(objects):
    low = [float('inf')] * 3
    high = [-float('inf')] * 3
    count = 0
    for obj in objects:
        for vertex in obj.data.vertices:
            p = obj.matrix_world @ vertex.co
            count += 1
            for axis in range(3):
                low[axis] = min(low[axis], p[axis])
                high[axis] = max(high[axis], p[axis])
    if not count:
        raise RuntimeError('Empty cleaned mesh')
    dimensions = [b-a for a,b in zip(low,high)]
    return {'minimum':low, 'maximum':high, 'dimensions_xyz':dimensions,
            'maximum_dimension':max(dimensions), 'vertices':count,
            'coordinate_system':'Blender world, Z up',
            'units':'native imported units; physical size uncalibrated'}


def run(species=None, version='support_cleanup_v1'):
    for name, recipe in RECIPES.items():
        if species and name != species:
            continue
        source_dir = ROOT / 'assets' / 'avians' / name
        output = source_dir / 'working' / version
        if output.exists():
            raise RuntimeError(f'Refusing to overwrite existing working copy: {output}')
        output.mkdir(parents=True)
        source = source_dir / 'source' / 'scene.gltf'
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(source))
        bpy.context.view_layer.update()
        meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
        before = bounds(meshes)
        removed = 0
        for obj in meshes:
            if recipe['cut_z'] is None:
                continue
            bm = bmesh.new(); bm.from_mesh(obj.data)
            selected = []
            for vertex in bm.verts:
                p = obj.matrix_world @ vertex.co
                if remove_support(p, recipe):
                    selected.append(vertex)
            removed += len(selected)
            bmesh.ops.delete(bm, geom=selected, context='VERTS')
            bm.to_mesh(obj.data); bm.free(); obj.data.update()
        after = bounds(meshes)
        shutil.copy2(source_dir/'source/license.txt', output/'license.txt')
        bpy.ops.wm.save_as_mainfile(filepath=str(output/f'{name}_working.blend'))
        usd_dir = output/'usd'; usd_dir.mkdir()
        result = bpy.ops.wm.usd_export(filepath=str(usd_dir/f'{name}_cleaned.usd'))
        if 'FINISHED' not in result:
            raise RuntimeError(f'USD export failed for {name}')
        report = {'version':'1.0.0','status':'candidate_contact_boundaries_need_review',
            'source':str(source.relative_to(ROOT)),
            'source_gltf_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'recipe':recipe,'removed_vertices':removed,'before':before,'after':after,
            'limitations':['Support contact may contain scanned feet; inspect cut boundary.',
                'No hole filling or invented anatomy; pose unchanged.',
                'Dimensions are mesh extents, not biological body length or validated metres.']}
        (output/'measurements.json').write_text(json.dumps(report,indent=2)+'\n')
        scene=bpy.context.scene; scene.render.engine='BLENDER_WORKBENCH'
        scene.display.shading.light='STUDIO';scene.display.shading.color_type='TEXTURE'
        scene.render.resolution_x=800;scene.render.resolution_y=800;scene.render.resolution_percentage=100
        center=Vector([(a+b)/2 for a,b in zip(before['minimum'],before['maximum'])]);size=before['maximum_dimension']
        bpy.ops.object.camera_add();camera=bpy.context.object;scene.camera=camera
        camera.data.type='ORTHO';camera.data.ortho_scale=size*1.1
        for label,direction in [('front',(0,-1,0)),('back',(0,1,0)),('oblique',(1,-2,0.7))]:
            camera.location=center+Vector(direction).normalized()*size*3
            camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
            scene.render.filepath=str(output/f'{label}.png');bpy.ops.render.render(write_still=True)
        print('CLEANED',name,json.dumps(after),flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--species',choices=list(RECIPES))
    parser.add_argument('--version',default='support_cleanup_v1')
    import sys
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if not args.version.replace('_','').isalnum():
        raise ValueError('Version must contain only letters, numbers and underscores')
    run(args.species,args.version)
