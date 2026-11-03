"""Independently validate native images and compare within-runtime attenuation."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parent


def exr_dimensions(path):
    data=path.read_bytes();assert data[:4]==b'v/1\x01';offset=8
    while data[offset]!=0:
        end=data.index(0,offset);name=data[offset:end].decode();offset=end+1
        end=data.index(0,offset);kind=data[offset:end].decode();offset=end+1
        size=struct.unpack_from('<I',data,offset)[0];offset+=4
        if name=='dataWindow':
            assert kind=='box2i' and size==16
            x0,y0,x1,y1=struct.unpack_from('<4i',data,offset);return x1-x0+1,y1-y0+1
        offset+=size
    raise ValueError('EXR dataWindow missing')


def analyse(folder):
    result=json.loads((folder/'result.json').read_text())
    if not result['ok']:return {'valid_capture_run':False,'failure':result}
    records=json.loads((folder/'capture_records.json').read_text());means={};rows=[]
    for metadata in records:
        case=metadata['case'];name=case['name'];directory=folder/name
        source=ROOT/case['file']
        if hashlib.sha256(source.read_bytes()).hexdigest()!=metadata['source_scene_sha256']:
            source=ROOT/'qa/initial_scenes'/Path(case['file']).name
        assert hashlib.sha256(source.read_bytes()).hexdigest()==metadata['source_scene_sha256']
        assert hashlib.sha256((directory/'captured_scene.usdc').read_bytes()).hexdigest()==metadata['captured_scene_sha256']
        assert metadata['actual_resolution']==[512,384] and metadata['rendered_frame_wait']==64
        assert metadata['gpu_before']['free_mib']>=768
        for filename in ('warmup.png','rgb.png'):
            with Image.open(directory/filename) as image:assert image.size==(512,384);image.verify()
        assert exr_dimensions(directory/'hdr.exr')==(512,384)
        samples=np.load(directory/'hdr.npz',allow_pickle=False)['rgba']
        assert samples.shape==(384,512,4) and np.isfinite(samples).all()
        mean=samples[184:200,248:264,:3].mean(axis=(0,1),dtype=np.float64)
        assert min(mean)>0 and max(mean)<60000,'ROI invalid or potentially clipped: '+name
        means[(case['view'],case['path_m'],case['condition'])]=mean
        rows.append({'case':name,'mean_hdr_rgb':mean.tolist(),'elapsed_seconds':metadata['elapsed_seconds'],
                     'source_scene_sha256':case['sha256'],'directory':str(directory.relative_to(ROOT))})
    tests=[]
    for view,path in sorted({(key[0],key[1]) for key in means}):
        clear=means[(view,path,'clear')];absorption=means[(view,path,'absorption')]
        engineering=means[(view,path,'engineering')]
        ratio=absorption/clear;prediction=np.array([.6,.8,.9])**path
        # Outside the interface, roughness/Fresnel and secondary light are not
        # asserted to be a pure Beer-law measurement. The inside test is direct.
        clear_spread=float((clear.max()-clear.min())/clear.mean())
        error=np.abs(ratio-prediction)
        tests.append({'view':view,'path_m':path,'clear_channel_relative_spread':clear_spread,
                      'clear_neutral_passed':clear_spread<=.01,
                      'absorption_relative_to_clear_rgb':ratio.tolist(),'beer_prediction_rgb':prediction.tolist(),
                      'absolute_ratio_error_rgb':error.tolist(),
                      'inside_absorption_passed':bool(max(error)<=.03) if view=='inside' else None,
                      'engineering_blue_red_ratio':float(engineering[2]/engineering[0]),
                      'engineering_chromatic_attenuation_passed':bool(engineering[2]/engineering[0]>1.05)})
    inside=next(test for test in tests if test['view']=='inside' and test['path_m']==.5)
    clear_inside=means[('inside',.5,'clear')]
    clear_above=means[('above',1,'clear')]
    above_test=next(test for test in tests if test['view']=='above')
    emissive_control=bool(min(clear_inside)>100 and min(clear_above)>100)
    above_absorption=bool(max(above_test['absolute_ratio_error_rgb'])<=.03)
    positive=bool(emissive_control and min(clear_above/clear_inside)>.5 and above_absorption)
    initial_pass=inside['clear_neutral_passed'] and inside['inside_absorption_passed'] and inside['engineering_chromatic_attenuation_passed']
    inside_tests=[test for test in tests if test['view']=='inside']
    sweep_complete=len(inside_tests)==4
    sweep_pass=sweep_complete and all(test['clear_neutral_passed'] and test['inside_absorption_passed'] for test in inside_tests)
    runtime=json.loads((folder/'runtime.json').read_text())
    return {'valid_capture_run':True,'above_water_target_positive_control_passed':positive,
            'emissive_target_positive_controls_passed':emissive_control,
            'above_water_absorption_control_passed':above_absorption,
            'qualified_for_version_comparison':positive,'runtime_build':runtime['build_version'],'records':rows,'tests':tests,
            'initial_inside_optical_checks_passed':bool(initial_pass),'distance_sweep_complete':sweep_complete,
            'distance_sweep_passed':bool(sweep_pass),'m4_animated_integration_completed':False}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('runs',nargs='+');args=parser.parse_args()
    results={name:analyse(ROOT/'runs'/name) for name in args.runs}
    (ROOT/'qa/comparison_analysis.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps({name:{k:v for k,v in value.items() if k not in ('records','tests')} for name,value in results.items()},indent=2))


if __name__=='__main__':main()
