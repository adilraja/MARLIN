"""Measured, hash-bound size candidate for the isolated actor only."""
import hashlib
import json
from pathlib import Path
from pxr import Gf, Usd, UsdGeom

PROFILE_PATH = Path(__file__).resolve().parents[3]/"config/bottlenose_calibration_v1.json"


def measure(model_prim, asset, profile="coastal_candidate_v1"):
    if profile not in ("coastal_candidate_v1", "legacy_preview"):
        raise ValueError("Unknown isolated-actor calibration profile")
    config=json.loads(PROFILE_PATH.read_text())
    if hashlib.sha256(Path(asset).read_bytes()).hexdigest()!=config["asset_sha256"]:
        raise ValueError("Bottlenose asset changed: remeasure landmarks before using calibration")
    meshes=[p for p in Usd.PrimRange(model_prim) if p.IsA(UsdGeom.Mesh)]
    if len(meshes)!=1:
        raise ValueError("Expected the inspected single-mesh bottlenose")
    mesh=UsdGeom.Mesh(meshes[0])
    # Exclude motion root translation/heading; include reference hierarchy and
    # the model's fixed rotation. Called before model scaling is authored.
    matrix=UsdGeom.XformCache().ComputeRelativeTransform(meshes[0],model_prim.GetParent())[0]
    points=[matrix.Transform(Gf.Vec3d(p)) for p in mesh.GetPointsAttr().Get()]
    landmarks={}
    for name,landmark in config["landmarks"].items():
        ids=landmark["vertices"]
        landmarks[name]=[sum(points[i][axis] for i in ids)/len(ids) for axis in range(3)]
    length=landmarks["rostrum_tip"][2]-landmarks["fluke_notch_candidate"][2]
    if not .38<length<.41 or landmarks["dorsal_tip"][1]<=0:
        raise ValueError("Measured orientation/length disagrees with inspected mesh")
    factor=config["target_axial_length_m"]/length if profile=="coastal_candidate_v1" else 1.0
    bounds=[[min(p[i] for p in points)*factor for i in range(3)],
            [max(p[i] for p in points)*factor for i in range(3)]]
    origin_y=config["waterline"]["origin_y_m"]
    return {"profile":profile,"status":config["status"] if profile!="legacy_preview" else "uncalibrated_legacy_preview",
            "reference":config["reference"],"asset_sha256":config["asset_sha256"],
            "source_axial_length":length,"scale_multiplier_relative_to_legacy":factor,
            "axial_length_m":length*factor,"model_bounds_m":bounds,
            "dimensions_m":[b-a for a,b in zip(*bounds)],
            "landmarks_m":{k:[x*factor for x in v] for k,v in landmarks.items()},
            "mean_plane_clearance_at_fixture_depth_m":-(origin_y+bounds[1][1]),
            "origin_depth_m":-origin_y,"waterline_status":"shallow_swim_not_breathing; animated wave clearance unresolved",
            "specimen_calibrated":False,"uncertainties":config["uncertainties"]}
