"""Capture and measure the isolated engineering target using the Kit HTTP API.

This high-contrast RGB threshold is a calibration diagnostic only, not a
wildlife annotation method or renderer-provided instance segmentation.
"""
import argparse
import json
from pathlib import Path
import sys
import urllib.request

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT/'source/extensions/cris.madil.render_service/config/calibration_target_v1.json'


def measure(directory):
    metadata = json.loads((directory/'metadata.json').read_text())
    if metadata.get('targets'):
        return measure_targets(directory,metadata)
    pixels = np.asarray(Image.open(directory/'rgb.png').convert('RGB'), dtype=float).mean(axis=2)
    height, width = pixels.shape
    config = metadata['config']
    x, y, w, h = metadata['expected_bbox_xywh_px']
    # Reject blank/low-contrast captures before extracting target silhouette.
    low, high = float(np.percentile(pixels, 10)), float(pixels.max())
    thresholds = [low+(high-low)*f for f in (0.35, 0.5, 0.65)]
    boxes = []
    for threshold in thresholds:
        rows, cols = np.where(pixels > threshold)
        boxes.append(None if not len(rows) else [int(cols.min()), int(rows.min()),
                      int(cols.max()-cols.min()+1), int(rows.max()-rows.min()+1)])
    errors = [None if b is None else [abs(a-e) for a,e in zip(b,(x,y,w,h))] for b in boxes]
    passed = (width == config['image_width_px'] and height == config['image_height_px']
              and metadata['actual_viewport_resolution'] == [width,height]
              and high-low >= 40 and all(e is not None and max(e) <= 2 for e in errors))
    box = boxes[1]
    result = {'passed': bool(passed), 'method': 'RGB contrast threshold diagnostic, not ground-truth segmentation',
              'image_size_px': [width,height], 'contrast_8bit': high-low,
              'expected_bbox_xywh_px': [x,y,w,h], 'measured_boxes_xywh_px': boxes,
              'absolute_errors_px': errors, 'tolerance_px': 2,
              'measured_gsd_cm_px': None if box is None else [config['target_width_m']*100/box[2],config['target_height_m']*100/box[3]]}
    (directory/'validation.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def measure_targets(directory,metadata):
    raw = Image.open(directory/'rgb.png').convert('RGB')
    pixels = np.asarray(raw,dtype=float).mean(axis=2)
    height,width = pixels.shape
    config = metadata['config']
    low,high = float(np.percentile(pixels,10)),float(pixels.max())
    passed = ([width,height]==[config['image_width_px'],config['image_height_px']]
              and metadata['actual_viewport_resolution']==[width,height] and high-low>=40)
    review = raw.copy()
    draw = ImageDraw.Draw(review)
    records = []
    for t in metadata['targets']:
        x,y,w,h = t['expected_bbox_xywh_px']
        left,top = max(0,int(x)-8),max(0,int(y)-8)
        right,bottom = min(width,int(np.ceil(x+w))+8),min(height,int(np.ceil(y+h))+8)
        expected = Image.new('1',(width,height))
        ImageDraw.Draw(expected).polygon([tuple(p) for p in t['expected_polygon_px']],fill=1)
        expected_mask = np.asarray(expected)[top:bottom,left:right]
        boxes,ious = [],[]
        for fraction in (0.35,0.5,0.65):
            mask = pixels[top:bottom,left:right]>low+(high-low)*fraction
            rows,cols = np.where(mask)
            boxes.append(None if not len(rows) else [int(cols.min())+left,int(rows.min())+top,int(cols.max()-cols.min()+1),int(rows.max()-rows.min()+1)])
            union = np.logical_or(mask,expected_mask).sum()
            ious.append(float(np.logical_and(mask,expected_mask).sum()/union) if union else 0)
        errors = [None if b is None else [abs(a-e) for a,e in zip(b,(x,y,w,h))] for b in boxes]
        ok = all(e is not None and max(e)<=2 for e in errors) and min(ious)>=0.95
        passed = passed and ok
        records.append({'id':t['id'],'passed':ok,'expected_bbox_xywh_px':[x,y,w,h],
                        'measured_boxes_xywh_px':boxes,'absolute_errors_px':errors,
                        'polygon_iou':ious,'predicted_local_gsd_xy_cm_px':t['local_gsd_xy_cm_px']})
        draw.line([tuple(p) for p in t['expected_polygon_px']]+[tuple(t['expected_polygon_px'][0])],fill='lime',width=1)
        gx,gy = t['local_gsd_xy_cm_px']
        draw.text((max(2,x),max(32,y-28)),f"{t['id']}  GSD {gx:.3f}/{gy:.3f} cm/px",fill='yellow')
    draw.rectangle((0,0,width,26),fill='black')
    draw.text((8,8),'CALIBRATION TARGETS ONLY — no ocean/animals | green: predicted geometry',fill='white')
    review.save(directory/'review.png')
    result = {'passed':bool(passed),'method':'RGB diagnostic versus projected polygons; NOT wildlife ground truth',
              'image_size_px':[width,height],'contrast_8bit':high-low,'bbox_tolerance_px':2,
              'minimum_polygon_iou':0.95,'targets':records,'review_image':'review.png',
              'gsd_note':'Directional GSD is ray/plane prediction; render validation checks projected polygons, not a direct GSD measurement.'}
    (directory/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--measure-existing', type=Path)
    parser.add_argument('--roll',type=float,help='Override engineering roll in degrees (not a HiDef convention)')
    args = parser.parse_args()
    directory = args.measure_existing
    if directory is None:
        payload = json.loads(args.config.read_text())
        if args.roll is not None:
            payload['roll_deg'] = args.roll
        req = urllib.request.Request('http://localhost:8011/scene/survey/calibration/capture',
                data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req, timeout=90) as response:
            result = json.load(response)
        if not result.get('ok'):
            raise RuntimeError(result)
        directory = Path(result['directory'])
    result = measure(directory)
    if 'targets' in result:
        summary = {'directory':str(directory.resolve()),'passed':result['passed'],
                   'image_size_px':result['image_size_px'],'target_count':len(result['targets']),
                   'review_image':str((directory/'review.png').resolve()),
                   'contents':'Calibration rectangles only; ocean and animals intentionally excluded.',
                   'details':'validation.json'}
        print(json.dumps(summary,indent=2))
    else:
        print(json.dumps({'directory':str(directory), **result}, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
