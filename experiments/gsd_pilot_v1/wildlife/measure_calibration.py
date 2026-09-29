"""Measure pilot assets with real USD skinning and composed world transforms.

Run in official Blender Python. Original layers, geometry and licences are read
only. BakeSkinning runs on a private flattened in-memory stage for measurement.
The chosen reference sizes are sourced in sources.json, not inferred from USD
unit metadata. No biological motion parameters are authored here.
"""
import hashlib
import json
import math
from pathlib import Path
import sys

sys.dont_write_bytecode = True
import numpy as np
from pxr import Gf, Usd, UsdGeom, UsdSkel, UsdUtils

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
PETREL = ROOT / 'assets/birds/european_storm_petrel/usd/glide.usd'
PORPOISE = ROOT / 'assets/cetaceans/model_75a_-_harbor_porpoise/working/calibration_v1/usd/harbour_porpoise_static_candidate.usd'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def transform(points, matrix):
    return (np.column_stack([points, np.ones(len(points))]) @ np.asarray(matrix))[:, :3]


def evaluate(path):
    original_hash = digest(path)
    source = Usd.Stage.Open(str(path))
    if not source or not source.GetDefaultPrim():
        raise ValueError('Asset lacks a default prim: ' + str(path))
    layers, assets, missing = UsdUtils.ComputeAllDependencies(str(path))
    if missing:
        raise ValueError('Missing asset dependencies: ' + str(missing))
    private = Usd.Stage.Open(source.Flatten())
    skinned = any(prim.IsA(UsdSkel.Skeleton) for prim in private.Traverse())
    if skinned and not UsdSkel.BakeSkinning(private.Traverse()):
        raise ValueError('Could not evaluate skinning')
    meshes = []
    points = []
    time = Usd.TimeCode(1)
    for prim in sorted(private.Traverse(), key=lambda p: str(p.GetPath())):
        if not prim.IsA(UsdGeom.Mesh):
            continue
        mesh = UsdGeom.Mesh(prim)
        local = np.array(mesh.GetPointsAttr().Get(time), dtype=np.float64)
        world = transform(local, UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(time))
        if not len(world) or not np.isfinite(world).all():
            raise ValueError('Invalid mesh points: ' + str(prim.GetPath()))
        meshes.append({'path': str(prim.GetPath()), 'start_index': sum(len(x) for x in points),
                       'vertex_count': len(world)})
        points.append(world)
    if not points:
        raise ValueError('No mesh geometry')
    dependencies = []
    for p in sorted({str(path), *[layer.realPath for layer in layers if layer.realPath], *assets}):
        p = Path(p).resolve()
        if not p.is_relative_to(ROOT / 'assets'):
            raise ValueError('Unexpected dependency outside asset tree: ' + str(p))
        dependencies.append({'path': str(p.relative_to(ROOT)), 'sha256': digest(p)})
    if digest(path) != original_hash:
        raise ValueError('Measurement changed original asset')
    return np.concatenate(points), {
        'asset_path': str(path.relative_to(ROOT)), 'asset_sha256': original_hash,
        'default_prim': str(source.GetDefaultPrim().GetPath()),
        'declared_up_axis': str(UsdGeom.GetStageUpAxis(source)),
        'declared_meters_per_unit': UsdGeom.GetStageMetersPerUnit(source),
        'skin_evaluated_on_private_stage': skinned, 'time_code': 1,
        'meshes': meshes, 'dependencies': dependencies,
        'usd_unit_metadata_is_not_biological_scale_evidence': True,
    }


def rotation_matrix(xyz):
    stage = Usd.Stage.CreateInMemory()
    prim = UsdGeom.Xform.Define(stage, '/Orientation')
    UsdGeom.XformCommonAPI(prim).SetRotate(Gf.Vec3f(*xyz), UsdGeom.XformCommonAPI.RotationOrderXYZ)
    return UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())


def bounds(points):
    return {'minimum': points.min(axis=0).tolist(), 'maximum': points.max(axis=0).tolist(),
            'dimensions_xyz': np.ptp(points, axis=0).tolist(),
            'maximum_dimension': float(np.ptp(points, axis=0).max())}


def landmark(index, native, corrected, meshes):
    mesh = next(m for m in meshes if m['start_index'] <= index < m['start_index'] + m['vertex_count'])
    return {'mesh_path': mesh['path'], 'vertex_index': index - mesh['start_index'],
            'combined_index': int(index), 'native_world': native[index].tolist(),
            'corrected_world': corrected[index].tolist()}


def run():
    OUT.mkdir(exist_ok=True)
    inputs = json.loads((OUT / 'calibration_inputs.json').read_text())
    records = {}
    for species, path, correction in [
        ('european_storm_petrel', PETREL, [-90, -math.degrees(math.atan2(11.5, 21)), 0]),
        ('harbour_porpoise', PORPOISE, [-90, 0, 0]),
    ]:
        selected = inputs['targets'][species]
        if str(path.relative_to(ROOT)) != selected['asset_path'] or digest(path) != selected['asset_sha256']:
            raise ValueError('Selected asset changed; calibration must be reviewed and versioned')
        for dependency in selected['source_dependencies']:
            if digest(ROOT / dependency['path']) != dependency['sha256']:
                raise ValueError('Selected dependency changed: ' + dependency['path'])
        native, report = evaluate(path)
        corrected = transform(native, rotation_matrix(correction))
        if species == 'european_storm_petrel':
            # Identify extremities in the previously reviewed approximate body
            # frame, then align that measured beak-tail vector to MARLIN +Z.
            beak, tail = int(np.argmax(corrected[:, 2])), int(np.argmin(corrected[:, 2]))
            forward = native[beak] - native[tail]
            correction = [math.degrees(math.atan2(forward[1], forward[2])),
                          -math.degrees(math.atan2(forward[0], math.hypot(forward[1], forward[2]))), 0]
            corrected = transform(native, rotation_matrix(correction))
            left, right = int(np.argmin(corrected[:, 0])), int(np.argmax(corrected[:, 0]))
            measured = float(np.linalg.norm(corrected[beak] - corrected[tail]))
            factor = selected['reference_length_m'] / measured
            anchors = {name: landmark(i, native, corrected, report['meshes']) for name, i in
                       [('wing_tip_min_x', left), ('wing_tip_max_x', right),
                        ('beak_candidate', beak), ('tail_candidate', tail)]}
            metric_name = 'euclidean_beak_to_tail_candidate_distance'
            reference = selected['reference_length_m']
            report['posed_wing_tip_distance_m'] = float(np.linalg.norm(corrected[right] - corrected[left])) * factor
            report['wingspan_reference_not_used_for_scaling_m'] = .38
            report['why_wingspan_not_used'] = 'Bent asymmetrical mounted wings are not a fully extended wingspan measurement; fitting to 0.38 m produces an oversized body.'
        else:
            prior = json.loads((path.parents[1] / 'calibration.json').read_text())
            predicted = []
            for key in ['candidate_rostrum_tip_native', 'candidate_fluke_notch_native']:
                predicted.append((np.array(prior['landmarks'][key]) - np.array(prior['native_origin_subtracted'])) * prior['uniform_scale_to_m'])
            ids = [int(np.argmin(np.linalg.norm(native - point, axis=1))) for point in predicted]
            if any(np.linalg.norm(native[i] - point) > 1e-5 for i, point in zip(ids, predicted)):
                raise ValueError('Porpoise candidate landmarks not found in exported USD')
            measured = float(np.linalg.norm(corrected[ids[1]] - corrected[ids[0]]))
            # Physical scaling was already baked into the separate existing candidate.
            factor = 1.0
            reference = selected['reference_length_m']
            if abs(measured - reference) > 1e-5:
                raise ValueError('Porpoise exported geometry no longer matches its reference')
            anchors = {name: landmark(i, native, corrected, report['meshes']) for name, i in
                       zip(['rostrum_candidate', 'fluke_notch_candidate'], ids)}
            metric_name = 'euclidean_rostrum_to_fluke_notch_candidate_distance'
        metric = corrected * factor
        # Verify the exact reference composition used by the spawning endpoint:
        # motion root scale + child reference with fixed orientation.
        stage = Usd.Stage.CreateInMemory()
        UsdGeom.SetStageUpAxis(stage, 'Y')
        UsdGeom.SetStageMetersPerUnit(stage, .01)
        root = UsdGeom.Xform.Define(stage, '/World/Cetaceans/Calibration')
        UsdGeom.XformCommonAPI(root).SetScale(Gf.Vec3f(*([factor / .01] * 3)))
        model = UsdGeom.Xform.Define(stage, str(root.GetPath()) + '/Model')
        model.GetPrim().GetReferences().AddReference(str(path), report['default_prim'])
        UsdGeom.XformCommonAPI(model).SetRotate(Gf.Vec3f(*correction), UsdGeom.XformCommonAPI.RotationOrderXYZ)
        if report['skin_evaluated_on_private_stage'] and not UsdSkel.BakeSkinning(stage.Traverse()):
            raise ValueError('Could not skin composed reference')
        composed = []
        for prim in sorted(stage.Traverse(), key=lambda p: str(p.GetPath())):
            if prim.IsA(UsdGeom.Mesh):
                local = np.array(UsdGeom.Mesh(prim).GetPointsAttr().Get(1), dtype=np.float64)
                composed.append(transform(local, UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode(1))) * .01)
        composed = np.concatenate(composed)
        error = float(np.abs(composed - metric).max())
        if error > 1e-5:
            raise ValueError('Referenced stage composition does not match measured calibration')
        report.update(species=species, vertex_count=len(native), native_world_bounds=bounds(native),
                      correction_xyz_deg=correction, corrected_native_bounds=bounds(corrected),
                      measurement_metric=metric_name, native_measurement=measured,
                      reference_measurement_m=reference, metres_per_corrected_native_unit=factor,
                      spawn_scale_for_centimetre_stage=factor / .01, metric_world_bounds=bounds(metric),
                      landmarks=anchors, composed_reference_max_error_m=error,
                      original_asset_unchanged=digest(path) == report['asset_sha256'])
        np.savez_compressed(OUT / (species + '_measurement_points.npz'), points_m=metric,
                            landmark_points_m=np.array([v['corrected_world'] for v in anchors.values()]) * factor,
                            landmark_names=np.array(list(anchors)))
        records[species] = report
    (OUT / 'measurements.json').write_text(json.dumps(records, indent=2) + '\n')
    print(json.dumps({key: {k: value[k] for k in ['vertex_count', 'native_measurement',
                     'metres_per_corrected_native_unit', 'spawn_scale_for_centimetre_stage',
                     'metric_world_bounds', 'composed_reference_max_error_m']} for key, value in records.items()}, indent=2))


if __name__ == '__main__':
    run()
