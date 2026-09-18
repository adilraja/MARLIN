"""Offline capture audit. Does not contact Kit or change original capture files.

Run with Python containing NumPy/Pillow; USD geometry uses Blender's Python.
Pixel contrast is evidence of a feature, not instance segmentation/identity.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

BLENDER_PYTHON = "/home/madil/opt/blender-5.0.1-linux-x64/5.0/python/bin/python3.11"


def geometry(directory):
    from pxr import Gf, Usd, UsdGeom
    meta = json.loads((directory / "metadata.json").read_text())
    sidecar = json.loads((directory / "gama_state.json").read_text())
    stage = Usd.Stage.Open(str(directory / "scene.usdc"))
    prim = stage.GetPrimAtPath(sidecar["actor_path"])
    matrix = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    bbox = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default", "render"]).ComputeWorldBound(prim).ComputeAlignedRange()
    vp = Gf.Matrix4d(meta["capture_view_matrix"]) * Gf.Matrix4d(meta["capture_projection_matrix"])
    width, height = meta["render_product"]["resolution"]
    def pixel(point):
        clip = Gf.Vec4d(*point, 1) * vp
        if clip[3] <= 0:
            raise ValueError("Point behind camera")
        return [(clip[0]/clip[3]+1)*width/2, (1-clip[1]/clip[3])*height/2]
    points = [pixel(bbox.GetCorner(i)) for i in range(8)]
    box = [min(p[0] for p in points), min(p[1] for p in points),
           max(p[0] for p in points), max(p[1] for p in points)]
    camera = UsdGeom.Camera(stage.GetPrimAtPath(meta["render_product"]["camera"]))
    frustum = camera.GetCamera(Usd.TimeCode.Default()).frustum
    def matrix_error(actual, expected):
        return max(abs(actual[i][j]-expected[i][j]) for i in range(4) for j in range(4))
    root = prim.GetParent()
    return {"bbox_px": box, "origin_px": pixel(matrix.ExtractTranslation()),
            "position_scene_units": list(matrix.ExtractTranslation()),
            "forward_y_up": list(matrix.TransformDir(Gf.Vec3d(0, 0, 1))),
            "bounds_scene_units": [list(bbox.GetMin()), list(bbox.GetMax())],
            "meters_per_scene_unit": UsdGeom.GetStageMetersPerUnit(stage),
            "camera_view_matrix_max_error": matrix_error(frustum.ComputeViewMatrix(),meta["capture_view_matrix"]),
            "camera_projection_matrix_max_error": matrix_error(frustum.ComputeProjectionMatrix(),meta["capture_projection_matrix"]),
            "frozen_time_s": root.GetCustomDataByKey("marlin:time_s"),
            "frozen_seed": root.GetCustomDataByKey("marlin:seed"),
            "computed_visibility": str(UsdGeom.Imageable(prim).ComputeVisibility()),
            "mesh_count": sum(p.IsA(UsdGeom.Mesh) for p in Usd.PrimRange(prim))}


def verify(directory, output):
    import numpy as np
    from PIL import Image, ImageDraw
    from verify_capture_projection import verify as verify_projection
    meta = json.loads((directory / "metadata.json").read_text())
    state = json.loads((directory / "gama_state.json").read_text())
    geo = json.loads(subprocess.check_output([BLENDER_PYTHON, "-B", __file__, str(directory), "--geometry"], text=True))
    trajectory = json.loads((Path(__file__).resolve().parents[1] / "artifacts/gama/trajectory_validation.json").read_text())
    sample = state["gama_state"]
    agent = sample["agents"][0]
    heading = math.radians(agent["heading_deg"])
    image = Image.open(directory / "rgb.png").convert("RGB")
    box = geo["bbox_px"]
    pixel_box = [math.floor(box[0]),math.floor(box[1]),math.ceil(box[2]),math.ceil(box[3])]
    cx, cy = int((box[0]+box[2])/2), int((box[1]+box[3])/2)
    region = [cx-16,cy-16,cx+17,cy+17]
    if not (0 <= region[0] < region[2] <= image.width and 0 <= region[1] < region[3] <= image.height):
        raise ValueError("Diagnostic region falls outside image")
    patch = np.asarray(image.crop(tuple(pixel_box)), dtype=float)
    surrounding = np.asarray(image.crop(tuple(region)), dtype=float)
    background = np.median(surrounding.reshape(-1,3),axis=0)
    differences = np.max(np.abs(patch-background),axis=2)
    # Nearest-neighbour magnification of existing pixels, no AI enhancement.
    diagnostic = Image.new("RGB", (800, 570), "white")
    draw = ImageDraw.Draw(diagnostic)
    draw.text((12,10), "GAMA capture audit: ORIGINAL pixels, not a re-render", fill="black")
    overview = image.resize((800,267))
    diagnostic.paste(overview,(0,35))
    x,y = cx*800/image.width,35+cy*267/image.height
    draw.rectangle((x-7,y-7,x+7,y+7),outline="red",width=2)
    crop = image.crop(tuple(region)).resize((231,231),Image.Resampling.NEAREST)
    diagnostic.paste(crop,(12,322))
    outlined = crop.copy()
    box_draw = ImageDraw.Draw(outlined)
    b = [(pixel_box[0]-region[0])*7,(pixel_box[1]-region[1])*7,
         (pixel_box[2]-region[0])*7-1,(pixel_box[3]-region[1])*7-1]
    box_draw.rectangle(b,outline="red",width=1)
    diagnostic.paste(outlined,(263,322))
    draw.text((12,305),"33x33 pixel crop, 7x nearest neighbour",fill="black")
    draw.text((263,305),"Projected world AABB (not a mask)",fill="black")
    draw.text((510,330),f"Image: {image.width} x {image.height}\nOrigin: {geo['origin_px'][0]:.2f}, {geo['origin_px'][1]:.2f}\nBox: {box[2]-box[0]:.2f} x {box[3]-box[1]:.2f} px\nGAMA time: {sample['time_s']} s\nGAMA seed: {sample['seed']}\nNo instance-ID image available.",fill="black")
    output.mkdir(parents=True,exist_ok=True)
    diagnostic.save(output / "visibility_diagnostic.png")
    checks = {
        "linked_files_hash_match": all(hashlib.sha256((directory/k).read_bytes()).hexdigest()==v for k,v in state["files_sha256"].items()),
        "scene_hash_matches_camera_record": hashlib.sha256((directory/"scene.usdc").read_bytes()).hexdigest()==meta["scene_sha256"],
        "matches_verified_gama_trajectory": sample == trajectory["snapshots"][-1],
        "timestamp_matches_frozen_scene": geo["frozen_time_s"] == sample["time_s"],
        "seed_matches_frozen_scene": geo["frozen_seed"] == str(sample["seed"]),
        "world_position_matches": all(abs(a/geo["meters_per_scene_unit"]-b)<1e-5 for a,b in zip(agent["position_m"],geo["position_scene_units"])),
        "heading_matches": max(abs(a-b) for a,b in zip(geo["forward_y_up"],[math.sin(heading),0,math.cos(heading)]))<1e-5,
        "camera_matrices_match_frozen_camera": max(geo["camera_view_matrix_max_error"],geo["camera_projection_matrix_max_error"])<1e-7,
        "image_dimensions_match": list(image.size)==meta["render_product"]["resolution"],
        "actor_inside_image": 0<=box[0]<box[2]<=image.width and 0<=box[1]<box[3]<=image.height,
        "image_geometry_gsd_verification": verify_projection(directory),
    }
    report = {"capture_directory":str(directory),"checks":checks,"geometry_and_provenance_passed":all(checks.values()),
              "geometry":geo,"gama_state":sample,
              "time_and_seed_namespaces":{"gama_simulation_time_s":sample["time_s"],"gama_seed":sample["seed"],
                "camera_geometry_seed":meta["seed"],"camera_randomisation":meta["randomisation"],
                "marlin_snapshot":meta["snapshot"],"note":"Independent clocks/seeds, not expected to equal. Artifact hashes bind the records."},
              "pixel_evidence":{"integer_roi_xyxy":pixel_box,"crop_xyxy":region,"background_rgb_median":background.tolist(),
                "max_channel_difference_255":float(differences.max()),"mean_max_channel_difference_255":float(differences.mean()),
                "roi_pixel_count":int(differences.size)},
              "visibility_status":"local_pixel_feature_only_not_instance_identity_certified",
              "visibility_limitations":["Projected bounds are not a segmentation mask.","Tiny footprint cannot establish a recognisable dolphin.","No instance-ID/depth or actor-on/off reference exists for this image.","Water refraction, occlusion and antialiasing can alter direct-projection appearance."],
              "scientific_detectability_validated":False}
    (output/"verification.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"checks":checks,"geometry":geo,"pixel_evidence":report["pixel_evidence"]},indent=2))
    return all(checks.values())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory",type=Path)
    parser.add_argument("--geometry",action="store_true",help=argparse.SUPPRESS)
    parser.add_argument("--output",type=Path)
    args = parser.parse_args()
    if args.geometry:
        print(json.dumps(geometry(args.directory.resolve())))
    else:
        if args.output is None:
            parser.error("--output is required")
        raise SystemExit(0 if verify(args.directory.resolve(),args.output) else 1)
