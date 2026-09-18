"""Compare actor-on/off repeats without equating pixel contribution to recognition."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import numpy as np
from PIL import Image, ImageDraw
from gama_live import preserved
from gama_trajectory import call
from verify_gama_capture import BLENDER_PYTHON


def evidence(on_a, off_a, off_b, on_b):
    arrays = [np.asarray(v,dtype=np.int16) for v in (on_a,off_a,off_b,on_b)]
    if len({a.shape for a in arrays}) != 1:
        raise ValueError("Image sizes differ")
    a,b,c,d = arrays
    noise = np.maximum(np.abs(a-d),np.abs(b-c))
    differences = np.stack([a-b,a-c,d-b,d-c])
    # A component must have the same sign in every cross-state comparison AND
    # exceed both observed same-state variations by >1 code value. This is a
    # bounded engineering test, not a statistical significance/detectability test.
    positive = differences.min(axis=0) > noise+1
    negative = differences.max(axis=0) < -noise-1
    mask = np.any(positive|negative,axis=2)
    return mask, noise, differences


def analyse(directory, observe_live=None):
    render = json.loads((directory/"render_report.json").read_text())
    if render["status"] != "rendered_pending_pixel_analysis" or len(render["captures"])!=4:
        raise ValueError("Four successful captures required")
    root = Path(__file__).resolve().parents[1]
    source = root/"artifacts/hidef_marine"/render["source_capture"]
    original = json.loads((source/"metadata.json").read_text())
    after = render["after"]
    # The first render report sampled immediately upon restoration, before an
    # animation update. Keep that original evidence and save a separate live check.
    if observe_live:
        after = call(observe_live,"/integration/gama/marine/audit")
        (directory/"resume_audit.json").write_text(json.dumps(after,indent=2)+"\n")
    elif (directory/"resume_audit.json").exists():
        after = json.loads((directory/"resume_audit.json").read_text())
    geometry = json.loads(subprocess.check_output([BLENDER_PYTHON,"-B",str(root/"tools/verify_gama_capture.py"),str(source),"--geometry"],text=True))
    checks = {"source_unchanged":all(hashlib.sha256((source/k).read_bytes()).hexdigest()==v for k,v in render["source_hashes"].items()),
              "order_on_off_off_on":[r["mode"] for r in render["captures"]]==["on","off","off","on"],
              "live_layers_restored":render["before"]["inspection"]["layers"]==render["after"]["inspection"]["layers"],
              **preserved(render["before"],after)}
    images = []
    for i,capture in enumerate(render["captures"]):
        path = Path(capture["directory"])
        meta = json.loads((path/"metadata.json").read_text())
        image = Image.open(path/"rgb.png").convert("RGB")
        images.append(np.asarray(image))
        checks[f"capture_{i}_geometry_preserved"] = all(meta[k]==original[k] for k in ("config","capture_view_matrix","capture_projection_matrix","camera_position_m"))
        checks[f"capture_{i}_restored"] = all(meta["restoration_checks"].values())
        checks[f"capture_{i}_image_valid"] = (list(image.size)==original["render_product"]["resolution"] and
            hashlib.sha256((path/"rgb.png").read_bytes()).hexdigest()==meta["output_sha256"]["rgb.png"])
    mask,noise,diff = evidence(*images)
    box = geometry["bbox_px"]
    x0,y0,x1,y1 = math.floor(box[0]),math.floor(box[1]),math.ceil(box[2]),math.ceil(box[3])
    if not (0<=x0<x1<=mask.shape[1] and 0<=y0<y1<=mask.shape[0]):
        raise ValueError("Projected ROI outside capture")
    local = mask[y0:y1,x0:x1]
    stats = {"projected_roi_xyxy":[x0,y0,x1,y1],"roi_pixels":int(local.size),
        "consistent_pixels_above_repeat_noise":int(local.sum()),
        "roi_max_repeat_noise_255":int(noise[y0:y1,x0:x1].max()),
        "roi_max_cross_state_difference_255":int(np.abs(diff[:,y0:y1,x0:x1]).max()),
        "whole_image_consistent_pixel_count":int(mask.sum())}
    cx,cy = (x0+x1)//2,(y0+y1)//2
    crop = (cx-16,cy-16,cx+17,cy+17)
    canvas = Image.new("RGB",(1040,300),"white")
    draw = ImageDraw.Draw(canvas)
    heat = np.max(np.abs(diff[0]),axis=2).astype(np.uint8)
    panels = [Image.fromarray(images[0]),Image.fromarray(images[1]),Image.fromarray(heat),Image.fromarray(mask.astype(np.uint8)*255)]
    labels = ["ON: original pixels","OFF: actor hidden","Absolute difference (unscaled)","Consistent > repeat noise + 1"]
    for i,(panel,label) in enumerate(zip(panels,labels)):
        draw.text((i*260+8,8),label,fill="black")
        canvas.paste(panel.crop(crop).resize((231,231),Image.Resampling.NEAREST),(i*260+8,35))
    draw.text((8,278),"Same 33x33 crop, nearest-neighbour 7x. Pixel contribution is not biological recognition.",fill="black")
    canvas.save(directory/"comparison.png")
    report = {"checks":checks,"geometry":geometry,"pixel_evidence":stats,
        "resume_evidence":"resume_audit.json" if (directory/"resume_audit.json").exists() else "render_report.json after",
        "criterion":"Same signed channel effect in all four on/off pairs exceeds both observed same-state differences by >1/255; inside precomputed projected box.",
        "controlled_comparison_valid":all(checks.values()),
        "pixel_contribution_observed":all(checks.values()) and bool(local.any()),
        "instance_segmentation_certified":False,"biological_recognition_certified":False,
        "limitations":["Two repeats per state do not establish statistical significance.","Visibility changes can affect shadows/reflections as well as direct appearance.","This does not certify native resolution, physical asset size or biological detectability."]}
    (directory/"analysis.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory",type=Path)
    parser.add_argument("--observe-live",help="Explicitly query the restored MARLIN API and save a separate resumption audit")
    args=parser.parse_args()
    report=analyse(args.directory,args.observe_live)
    raise SystemExit(0 if report["controlled_comparison_valid"] else 1)
