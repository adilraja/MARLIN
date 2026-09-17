#!/usr/bin/env python3
"""Compare frozen-scene diagnostics on identical native-pixel regions.

This is not a full-image acceptance test. Original PNGs remain unchanged.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


def pixels(directory, record, box):
    a,b,c,d = record['bounds']
    left,top,right,bottom = box
    if not (a <= left < right <= c and b <= top < bottom <= d):
        raise ValueError('Comparison region is outside a tile')
    with Image.open(directory/record['file']) as image:
        return np.asarray(image.convert('RGB').crop(
            (left-a,top-b,right-a,bottom-b)), dtype=np.float64)


def error(first, second):
    if first.shape != second.shape or first.size == 0:
        raise ValueError('Comparison requires equal, nonempty image regions')
    delta = np.abs(first-second)
    return dict(mean_absolute_rgb_error=float(delta.mean()),
                max_absolute_rgb_error=float(delta.max()))


def analyse(directories):
    reports=[]
    source_hash=None
    regions=None
    for directory in directories:
        meta=json.loads((directory/'metadata.json').read_text())
        if not meta.get('tile_diagnostic'):
            raise ValueError('Expected a focused tile diagnostic')
        if source_hash is None:
            source_hash=meta['scene_sha256']
            # Fix comparison regions to the first run, not wider guards in
            # later runs: extra water pixels must not dilute the same error.
            regions=[s for s in meta['native_tiling']['overlap_checks']
                     if not s['identical_tile_repeat']]
        if meta['scene_sha256'] != source_hash:
            raise ValueError('Diagnostics do not share the same frozen scene')
        records={r['file']:r for r in meta['native_tiling']['tiles']}
        comparisons=[]
        for region in regions:
            first,second=(records[name] for name in region['tiles'])
            box=region['overlap_bounds']
            comparison=dict(tiles=region['tiles'],overlap_bounds=box,
                            **error(pixels(directory,first,box),pixels(directory,second,box)))
            # Same-region repeat is the relevant stochastic control, not the
            # mean across a much larger, mostly-water repeated tile.
            controls=[]
            for record in (first,second):
                for repeat in records.values():
                    if repeat['tile_index']==record['tile_index'] and repeat['file']!=record['file']:
                        controls.append(dict(tiles=[record['file'],repeat['file']],
                            **error(pixels(directory,record,box),pixels(directory,repeat,box))))
            comparison['identical_tile_same_region_controls']=controls
            comparisons.append(comparison)
        seams=meta['native_tiling']['overlap_checks']
        reports.append(dict(capture_id=directory.name,diagnostic=meta['tile_diagnostic'],
            main_viewport_preserved=meta['main_viewport_preserved'],
            settling_app_updates_per_tile=meta['native_tiling'].get('settling_app_updates_per_tile',
                meta['native_tiling'].get('settling_frames_per_tile')),
            additional_rendered_frames_per_tile=meta['native_tiling'].get('additional_rendered_frames_per_tile',0),
            settling_policy=meta['native_tiling'].get('settling_policy','Legacy wait; consult the capture version and investigation notes'),
            original_guard_pixels=meta['native_tiling']['guard_pixels'],
            original_overlap_checks=seams,
            fixed_region_comparisons=comparisons,
            worst_fixed_region_mean=max(c['mean_absolute_rgb_error'] for c in comparisons),
            full_image_certified=False))
    return dict(schema_version=1,scene_sha256=source_hash,
        comparison_units='absolute 8-bit RGB code-value differences, not linear radiance',
        overlap_mean_error_limit=2.0,
        interpretation='Focused diagnostic only. Settings changes do not establish individual-effect causality unless all other inputs are equal.',
        runs=reports)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directories',type=Path,nargs='+')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=analyse(args.directories)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    for run in result['runs']:
        print(run['capture_id'],run['diagnostic']['mode'],
              'worst fixed-region mean:',run['worst_fixed_region_mean'],
              'live restored:',run['main_viewport_preserved'])


if __name__=='__main__':
    main()
