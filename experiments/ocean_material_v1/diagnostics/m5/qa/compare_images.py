"""Measure M5's declared display-image tolerances without treating state hashes as pixels."""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

RESOLUTION = (512, 384)
ROI = (128, 96, 384, 288)


def metrics(a, b):
    if a.shape != (384, 512, 3) or b.shape != a.shape:
        raise ValueError('Both inputs must have the declared 512 x 384 RGB shape')
    if a.dtype != np.uint8 or b.dtype != np.uint8:
        raise ValueError('Display-image comparison requires uint8 RGB inputs')
    # Cast before subtraction: uint8 arithmetic would hide large differences.
    difference = np.abs(a.astype(np.float64) - b.astype(np.float64))
    result = {}
    for name, values in (('full_rgb', difference), ('fixed_central_roi', difference[96:288, 128:384])):
        mean = float(values.mean())
        p99 = float(np.percentile(values, 99))
        result[name] = dict(mean_absolute_difference_8bit=mean,
                            p99_absolute_difference_8bit=p99,
                            maximum_absolute_difference_8bit=float(values.max()),
                            mean_absolute_difference_normalized=mean / 255,
                            p99_absolute_difference_normalized=p99 / 255,
                            passed=mean <= 1 and p99 <= 8)
    return dict(resolution=list(RESOLUTION), roi_xyxy=list(ROI),
                tolerances_8bit=dict(mean_absolute_difference=1, p99_absolute_difference=8),
                comparisons=result, image_tolerance_passed=all(v['passed'] for v in result.values()),
                scene_camera_settings_equality='Must be checked independently; image similarity alone does not establish it')


def read(path):
    with Image.open(path) as image:
        if image.size != RESOLUTION:
            raise ValueError('Saved image dimensions differ from the predeclared capture: ' + str(path))
        if image.mode not in ('RGB', 'RGBA'):
            raise ValueError('Expected an RGB/RGBA display image: ' + str(path))
        return np.asarray(image.convert('RGB'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = metrics(read(args.reference), read(args.candidate))
    result.update(reference=str(args.reference.resolve()), candidate=str(args.candidate.resolve()))
    # Preserve earlier attempts, including failures.
    with args.output.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
