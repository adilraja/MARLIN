"""Compare actual Kit scene checkpoints with independently evaluated asset points."""
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from pxr import Gf, Usd, UsdGeom, UsdShade, UsdSkel
from measure_calibration import OUT, ROOT, digest, transform, bounds


def verify():
    review = json.loads((OUT / 'kit_review/preview.json').read_text())
    states = json.loads((OUT / 'kit_review/state_review.json').read_text())
    measured = json.loads((OUT / 'measurements.json').read_text())
    reports = {}
    for label, checkpoint in [('dry', review['checkpoint']), ('shallow', states['final_checkpoint'])]:
        filename = Path(checkpoint['directory']) / 'scene.usdc'
        if digest(filename) != checkpoint['scene_sha256']:
            raise ValueError('Live checkpoint hash mismatch')
        stage = Usd.Stage.Open(Usd.Stage.Open(str(filename)).Flatten())
        if UsdGeom.GetStageMetersPerUnit(stage) != .01 or UsdGeom.GetStageUpAxis(stage) != 'Y':
            raise ValueError('Unexpected live stage units/axes')
        if not UsdSkel.BakeSkinning(stage.Traverse()):
            raise ValueError('Live checkpoint skinning failed')
        animals = {}
        for species, item in review['animals'].items():
            root = stage.GetPrimAtPath(item['spawn']['prim_path'])
            position = np.array(item['request']['position']) * .01
            if label == 'shallow' and species == 'harbour_porpoise':
                position[1] = states['porpoise_shallow']['root_y_m']
            chunks, material_records = [], []
            for prim in sorted(Usd.PrimRange(root), key=lambda p: str(p.GetPath())):
                if not prim.IsA(UsdGeom.Mesh):
                    continue
                points = np.array(UsdGeom.Mesh(prim).GetPointsAttr().Get(1), dtype=np.float64)
                chunks.append(transform(points, UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode(1))) * .01)
                material, _ = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial()
                if not material:
                    raise ValueError('Unbound live material: ' + str(prim.GetPath()))
                textures = []
                for child in Usd.PrimRange(material.GetPrim()):
                    attr = child.GetAttribute('inputs:file')
                    value = attr.Get() if attr else None
                    if value is not None and hasattr(value, 'path') and value.path:
                        path = Path(value.resolvedPath or value.path).resolve()
                        if not path.is_relative_to(ROOT / 'assets') or not path.is_file():
                            raise ValueError('Texture does not resolve inside canonical assets: ' + str(path))
                        textures.append({'path': str(path.relative_to(ROOT)), 'sha256': digest(path)})
                # Eye materials are intentionally constant-colour. Require a
                # bound surface on every mesh and the known texture set across
                # the complete animal, rather than a texture on every eye.
                if not material.GetSurfaceOutput().HasConnectedSource():
                    raise ValueError('Bound material lacks a surface shader')
                material_records.append({'mesh': str(prim.GetPath()), 'material': str(material.GetPath()), 'textures': textures})
            expected_textures = {dep['path'] for dep in measured[species]['dependencies'] if Path(dep['path']).suffix == '.png'}
            actual_textures = {dep['path'] for material in material_records for dep in material['textures']}
            if not expected_textures or actual_textures != expected_textures:
                raise ValueError('Live animal texture set does not match original asset')
            live = np.concatenate(chunks)
            expected = np.load(OUT / (species + '_measurement_points.npz'))['points_m'] + position
            error = float(np.abs(live - expected).max()) if live.shape == expected.shape else float('inf')
            if error > 1e-5:
                raise ValueError('Live asset differs from calibrated points: ' + species)
            anchors = measured[species]['landmarks']
            names = ['beak_candidate', 'tail_candidate'] if species == 'european_storm_petrel' else ['rostrum_candidate', 'fluke_notch_candidate']
            forward = live[anchors[names[0]]['combined_index']] - live[anchors[names[1]]['combined_index']]
            if forward[2] <= 0 or abs(forward[0]) > 1e-5:
                raise ValueError('Nose does not point along +Z')
            heading_cases = []
            for angle, expected_xz in [(0, (0, 1)), (90, (1, 0)), (180, (0, -1)), (270, (-1, 0))]:
                rotated = Gf.Rotation(Gf.Vec3d.YAxis(), angle).TransformDir(Gf.Vec3d(*forward))
                xz = np.array([rotated[0], rotated[2]])
                xz /= np.linalg.norm(xz)
                if not np.allclose(xz, expected_xz, atol=1e-6):
                    raise ValueError('Heading convention mismatch')
                heading_cases.append({'heading_deg': angle, 'nose_horizontal_direction': xz.tolist(), 'passed': True})
            observed90 = next(p for p in states['heading_checks'][species]['inspection']['prims'] if p['path'] == str(root.GetPath()))
            if not any(op['name'] == 'xformOp:rotateXYZ' and op['value'] == '(0, 90, 0)' for op in observed90['xform_ops']):
                raise ValueError('90-degree live heading was not recorded')
            animals[species] = {'passed': True, 'vertex_count': len(live), 'mesh_count': len(chunks),
                'max_point_error_m': error, 'world_bounds_m': bounds(live),
                'landmark_distance_m': float(np.linalg.norm(forward)),
                'heading_cases': heading_cases, 'live_heading90_authored': True,
                'materials': material_records}
        if label == 'shallow':
            top = animals['harbour_porpoise']['world_bounds_m']['maximum'][1]
            bird_bottom = animals['european_storm_petrel']['world_bounds_m']['minimum'][1]
            if abs(top + .02) > 1e-5 or bird_bottom <= 0:
                raise ValueError('Static state clearance mismatch')
        reports[label] = {'checkpoint': checkpoint['checkpoint_id'], 'sha256': checkpoint['scene_sha256'],
                          'animals': animals, 'passed': True}
    for species, data in measured.items():
        for dep in data['dependencies']:
            if digest(ROOT / dep['path']) != dep['sha256']:
                raise ValueError('Original dependency changed after live preview')
    report = {'passed': True, 'scope': 'Geometry, units, heading, texture resolution and static clearance; not biological or optical validation',
              'original_dependencies_unchanged': True, 'checks': reports}
    (OUT / 'live_validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': True, 'states': list(reports), 'original_dependencies_unchanged': True,
                      'max_point_error_m': max(a['max_point_error_m'] for r in reports.values() for a in r['animals'].values())}))


if __name__ == '__main__':
    verify()
