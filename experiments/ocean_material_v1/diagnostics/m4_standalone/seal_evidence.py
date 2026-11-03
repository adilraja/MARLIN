"""Package runnable inputs and final evidence; seal local records without SDKs."""
import hashlib
import json
from pathlib import Path
import zipfile
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[3]
FINAL=['baseline_render_09','candidate_render_03']
REPORT=REPO/'experiments/ocean_material_v1/reports/M4_STANDALONE_VERSION_COMPARISON.md'


def pin(path, base):
    return {'path':str(path.relative_to(base)), 'bytes':path.stat().st_size,
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    now=datetime.now(timezone.utc).isoformat()
    for run in (ROOT/'runs').iterdir():
        if not run.is_dir():continue
        for name in ['stdout.log','kit_process.log']:
            source=run/name
            if source.is_file():
                target=run/(source.stem+'_snapshot.log')
                if not target.exists():target.write_bytes(source.read_bytes())
    summary=json.loads((ROOT/'RESULT_SUMMARY.json').read_text())
    inputs=['README.md','standalone.kit','capture_in_kit.py','run_reproducer.py',
            'scene_manifest.json','REPRODUCTION_AMENDMENT.md','RESULT_SUMMARY.json',
            'NVIDIA_SUPPORT_ADDENDUM.md','comparisons/sdk_controls.png']
    paths=[(ROOT/name,name) for name in inputs]
    paths += [(p,str(p.relative_to(ROOT))) for p in sorted((ROOT/'scenes').glob('*.usda'))]
    paths += [(REPORT,'COMPARISON_REPORT.md')]
    for name in FINAL:
        run=ROOT/'runs'/name
        paths += [(p,str(p.relative_to(ROOT))) for p in sorted(run.rglob('*'))
                  if p.is_file() and p.name not in ['stdout.log','kit_process.log','stdout_snapshot.log','kit_process_snapshot.log']]
    paths += [(ROOT/'qa/final_validation.json','qa/final_validation.json')]
    package=ROOT/'marlin_camera_inside_reproducer.zip'
    if package.exists():raise RuntimeError('Refusing to overwrite sealed package')
    package_pins=[]
    with zipfile.ZipFile(package,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path,name in paths:
            data=path.read_bytes()
            if path==REPORT:
                data=data.replace(b'(../diagnostics/m4_standalone/',b'(')
            archive.writestr(name,data)
            package_pins.append({'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
        archive.writestr('PACKAGE_CONTENTS.json',json.dumps(package_pins,indent=2)+'\n')
    with zipfile.ZipFile(package) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist())==len(set(archive.namelist()))
        for item in archive.namelist():
            p=Path(item);assert not p.is_absolute() and '..' not in p.parts
            assert not any(part in ('work','_build','extscache','.cache','__pycache__') for part in p.parts)
        for entry in package_pins:
            data=archive.read(entry['path'])
            assert hashlib.sha256(data).hexdigest()==entry['sha256']
        scenes=json.loads(archive.read('scene_manifest.json'))
        assert len(scenes['cases'])==15
        for case in scenes['cases']:
            assert hashlib.sha256(archive.read(case['file'])).hexdigest()==case['sha256']
    package_qa={'recorded_at_utc':now,'entries':len(package_pins)+1,
                'package_bytes':package.stat().st_size,'package_sha256':hashlib.sha256(package.read_bytes()).hexdigest(),
                'crc_paths_content_hashes_checked':True,'scene_manifest_hashes_checked':15,
                'native_sdk_binaries_included':False,'second_host_execution_tested':False}
    (ROOT/'qa/package_validation.json').write_text(json.dumps(package_qa,indent=2)+'\n')
    excluded={'manifest.json'}
    files=[]
    # Enumerate explicit experiment trees only; do not descend into private SDKs.
    for entry in ROOT.iterdir():
        if entry.name=='work':continue
        candidates=entry.rglob('*') if entry.is_dir() else [entry]
        for path in candidates:
            if not path.is_file() or path.name in excluded:continue
            if path.name in ('stdout.log','kit_process.log'):continue
            files.append(pin(path,REPO))
    files.append(pin(REPORT,REPO))
    preservation=json.loads((ROOT/'qa/preservation_checks.json').read_text())
    assert all(not item['mismatches'] for item in preservation)
    manifest={'kind':'m4_standalone_isolated_sdk_comparison','recorded_at_utc':now,
        'status':'valid_positive_controls_inside_camera_attenuation_unresolved_in_both_sdks',
        'final_comparison_runs':FINAL,'final_comparison_captures':12,
        'total_retained_captures':summary['total_retained_captures'],
        'camera_inside_fix_qualified':False,'full_milestone_complete':False,
        'marlin_original_binary_verified':True,'marlin_scene_settings_controllers_restored':True,
        'prior_pinned_evidence_files_unchanged':1514,'pre_work_source_files_unchanged':128,
        'support_addendum_sent':False,'package':pin(package,REPO),
        'source_pins':json.loads((ROOT/'qa/marlin_source_before.json').read_text()),
        'files':sorted(files,key=lambda item:item['path'])}
    (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    for item in manifest['files']:
        assert hashlib.sha256((REPO/item['path']).read_bytes()).hexdigest()==item['sha256']
    print(json.dumps({'sealed_files':len(files),'package':package_qa},indent=2))


if __name__=='__main__':main()
