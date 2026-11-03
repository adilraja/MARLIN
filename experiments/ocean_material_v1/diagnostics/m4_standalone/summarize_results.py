"""Summarise sealed native outputs; generate a fixed-scale scientific preview."""
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parent
FINAL=['baseline_render_09','candidate_render_03']


def main():
    analysis=json.loads((ROOT/'qa/comparison_analysis.json').read_text())
    files=['capture_in_kit.py','standalone.kit','scene_manifest.json']
    protocol={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in files}
    assert (ROOT/'capture_in_kit.py').read_bytes()==(ROOT/'qa/final_capture_harness.py').read_bytes()
    assert (ROOT/'standalone.kit').read_bytes()==(ROOT/'qa/final_app.kit').read_bytes()
    runs={}
    for name in FINAL:
        run=ROOT/'runs'/name;result=analysis[name]
        assert result['qualified_for_version_comparison']
        records=json.loads((run/'capture_records.json').read_text())
        assert len(records)==6 and all(x['native_material_readiness_passed'] for x in records)
        samples=[json.loads(line) for line in (run/'gpu_samples.jsonl').read_text().splitlines()]
        runs[name]={
            'runtime_build':result['runtime_build'],
            'comparison_qualified':True,
            'initial_inside_optical_checks_passed':result['initial_inside_optical_checks_passed'],
            'tests':result['tests'],
            'means':{x['case']['name']:x['hdr']['centre_rgb'] for x in records},
            'minimum_pre_capture_free_mib':min(x['gpu_before']['free_mib'] for x in records),
            'minimum_sampled_free_mib':min(x['free_mib'] for x in samples),
            'peak_sampled_used_mib':max(x['used_mib'] for x in samples),
            'process_seconds':json.loads((run/'exit.json').read_text())['elapsed_seconds'],
            'water_mdl_sha256':records[0]['mdl_sha256'],
        }
        (run/'protocol_record.json').write_text(json.dumps({
            'common_source_hashes':protocol,
            'snapshot_note':'Common harness/app snapshots preserved unchanged after final launches',
        },indent=2)+'\n')
    inventory=[]
    for run in sorted((ROOT/'runs').glob('*_render_*')):
        records=json.loads((run/'capture_records.json').read_text()) if (run/'capture_records.json').exists() else []
        inventory.append({'run':run.name,'captures':len(records),
            'classification':'final_matched_comparison' if run.name in FINAL else
                'supporting_positive_control_run' if run.name=='baseline_render_08' else
                'dry_geometry_camera_control' if run.name=='baseline_render_03' else 'exploratory_unqualified',
            'exit':json.loads((run/'exit.json').read_text()) if (run/'exit.json').exists() else None})
    summary={'final_runs':runs,'common_source_hashes':protocol,'capture_inventory':inventory,
        'total_retained_captures':sum(x['captures'] for x in inventory),
        'final_comparison_captures':12,'underwater_fix_qualified':False,
        'distance_sweep_executed':False,'milestone_4_complete':False,
        'marlin_restoration':json.loads((ROOT/'qa/marlin_restoration_validation.json').read_text()),
        'marlin_original_executable_verified':json.loads((ROOT/'qa/marlin_runtime_after.json').read_text())['executable_unchanged']}
    (ROOT/'RESULT_SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')

    output=ROOT/'comparisons';output.mkdir(exist_ok=True)
    image=Image.new('RGB',(1080,830),'#101a25');draw=ImageDraw.Draw(image)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',17)
    small=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',14)
    draw.text((22,12),'Native HDR controls — identical fixed log scale',font=font,fill='white')
    draw.text((22,38),'Inside: path .5 m    |    Above: target depth 1 m    |    No per-image exposure adjustment',font=small,fill='#a8b8ca')
    for column,condition in enumerate(['clear','absorption','engineering']):
        draw.text((180+300*column,65),condition,font=font,fill='white')
    for row,(run_name,view) in enumerate((run,view) for run in FINAL for view in ['inside','above']):
        y=95+row*175
        version='110.2.0' if run_name.startswith('baseline') else '110.4.1'
        draw.text((15,y+35),version,font=font,fill='white')
        draw.text((15,y+60),view,font=font,fill='#a8b8ca')
        for column,condition in enumerate(['clear','absorption','engineering']):
            case=f'{view}_{"0500" if view=="inside" else "1000"}_{condition}'
            rgba=np.load(ROOT/'runs'/run_name/case/'hdr.npz',allow_pickle=False)['rgba']
            pixels=(np.clip(np.log1p(np.maximum(rgba[:,:,:3],0))/np.log1p(12000),0,1)*255).round().astype('uint8')
            panel=Image.fromarray(pixels).resize((210,157),Image.Resampling.LANCZOS)
            x=175+column*300;image.paste(panel,(x,y))
            mean=runs[run_name]['means'][case]
            draw.text((x,y+158),'RGB '+', '.join(str(round(v)) for v in mean),font=small,fill='#c6d0df')
    draw.text((22,805),'Mapping: log1p(RGB) / log1p(12000). Float NPZ/EXR remain the measurement evidence.',font=small,fill='#a8b8ca')
    image.save(output/'sdk_controls.png')
    print(json.dumps({'runs':runs,'total_retained_captures':summary['total_retained_captures']},indent=2))


if __name__=='__main__':main()
