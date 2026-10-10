"""Record a historical entrypoint failure without re-running or changing it."""
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path('/home/madil/kit-app-template')
QA = ROOT / 'experiments/gama_marlin_v1/qa/m8_offline_01'
BASELINE = ROOT / 'experiments/gama_marlin_v1/qa/preserved_output_manifest.json'


def pin(path):
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def read(path):
    return json.loads(path.read_text())


def by_path(rows):
    return {row['path']: row for row in rows}


def main():
    outputs = [QA / 'historical_package_disposition.json', QA / 'summary.md']
    assert not any(path.exists() for path in outputs), 'Disposition outputs already exist'
    originals = {str(p): pin(p) for p in QA.iterdir() if p.is_file()}
    results = read(QA / 'results.json')
    assert results['passed'] is False
    jobs = results['results']
    failure = next(row for row in jobs if row['name'] == 'pilot_sealed_package')
    assert failure['return_code'] == 1 and failure['passed'] is False
    assert all(row['passed'] for row in jobs if row['tests'] is not None)
    assert sum(row['tests'] for row in jobs if row['tests'] is not None) == 360
    assert sum(row['skipped'] for row in jobs) == 0
    baseline = by_path(read(BASELINE)['files'])
    before = by_path(read(QA / 'source_pins_before.json'))
    after = by_path(read(QA / 'source_pins_after.json'))
    assert before == after
    names = ['experiments/gsd_pilot_v1/specification.json',
             'experiments/gsd_pilot_v1/history/milestone_7/specification.json',
             'experiments/gsd_pilot_v1/history/milestone_6/specification.json',
             'experiments/gsd_pilot_v1/qa/m7_package.py',
             'experiments/gsd_pilot_v1/qa/milestone_7_manifest.json']
    records = []
    for name in names:
        path = ROOT / name
        actual = pin(path)
        row = {'path': name, 'bytes': actual['bytes'], 'sha256': actual['sha256']}
        assert row == baseline[name]
        value = dict(actual, preserved_baseline_record=baseline[name], matches_preserved_baseline=True)
        if path.name == 'specification.json':
            value['schema_version'] = read(path)['schema_version']
        if str(path) in before:
            assert actual == before[str(path)] == after[str(path)]
            value.update(execution_before_pin=before[str(path)], execution_after_pin=after[str(path)], execution_pins_unchanged=True)
        records.append(value)
    assert records[0]['schema_version'] == '1.7.0'
    assert records[1]['schema_version'] == '1.6.0'
    package = ROOT / names[3]
    source = package.read_text()
    tree = ast.parse(source)
    assertions = [n for n in ast.walk(tree) if isinstance(n, ast.Assert)]
    version_assert = next(n for n in assertions if ast.get_source_segment(source,n) == 'assert spec["schema_version"] == "1.6.0"')
    assert version_assert.lineno == 33
    writes = [n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr.startswith('write')]
    assert len(writes) == 1 and writes[0].lineno > version_assert.lineno
    stderr_path = Path(failure['stderr']['path'])
    assert pin(stderr_path) == failure['stderr']
    traceback = stderr_path.read_text()
    assert 'line 33, in main' in traceback and 'AssertionError' in traceback
    assert pin(Path(failure['stdout']['path'])) == failure['stdout'] and failure['stdout']['bytes'] == 0
    categories = Counter()
    for job in jobs:
        if job['tests'] is not None:
            categories[job['category']] += job['tests']
    metric = next(job for job in jobs if job['name'] != failure['name'] and job['tests'] is None)
    assert metric['passed'] and metric['return_code'] == 0
    value = {
        'kind': 'm8_historical_package_failure_disposition',
        'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'failed_obsolete_historical_entrypoint',
        'original_run_record': pin(QA/'results.json'),
        'original_run_passed': False,
        'original_failed_execution': failure,
        'original_traceback': traceback,
        'diagnosis': 'The historical M7 package script asserted the M7 schema marker 1.6.0 against the preserved final Pilot specification 1.7.0. The completed baseline and historical M7 snapshot each match their separately recorded preservation hashes.',
        'expected_schema': '1.6.0', 'actual_preserved_final_schema': '1.7.0',
        'assertion': {'source': pin(package), 'line': 33, 'text': ast.get_source_segment(source,version_assert)},
        'preservation_manifest': pin(BASELINE), 'preservation_evidence': records,
        'no_package_outputs_written': True,
        'no_write_basis': {'failure_precedes_only_package_write': True,
                          'only_package_write_line': writes[0].lineno,
                          'only_package_write_expression': ast.get_source_segment(source,writes[0]),
                          'existing_manifest_matches_before_after_and_preserved_baseline': True,
                          'stdout_empty': True,
                          'scope': 'The package process stopped at line 33 before the only output write. Its existing output seal remained byte-identical. New stdout/stderr/execution evidence was written only by the M8 QA runner.'},
        'rerun_performed': False, 'historical_source_or_pilot_artifacts_modified': False,
        'normal_regressions': {'passed': True, 'unittest_cases': 360, 'skipped': 0,
                               'categories': dict(categories), 'additional_metric_self_check_passed': True,
                               'metric_execution': metric,
                               'source_input_pins_unchanged': len(before),
                               'python_syntax_files_passed': len(results['python_syntax_checked']),
                               'git_diff_check_return_code': results['git_diff_check']['return_code']},
        'impact': 'This separate historical packaging failure did not fail any current MARLIN, camera, bridge or capture unittest. It does not invalidate an independently retained live demonstration audit. This disposition makes no independent live, GPU render, ML, biological or M7 dataset completion claim.',
        'original_evidence_preserved': True,
        'live_kit_calls_made': False, 'new_gpu_renders': 0, 'ml_training_started': False,
        'biological_approval': False,
        'disposition_command': [sys.executable,'-B',str(Path(__file__).resolve())],
        'disposition_recipe_pin': pin(Path(__file__))}
    with outputs[0].open('x') as stream:
        stream.write(json.dumps(value,indent=2)+'\n')
    lines = [
        '# M8 offline regression scope and historical failure disposition', '',
        'All **360 unittest cases passed**, with zero skips. The extra Pilot metric self-check also passed. The original run-level `passed:false` remains unchanged because a separate historical packaging entrypoint failed.', '',
        '| Scope | Passed cases |', '| --- | ---: |']
    lines += [f'| {category} | {count} |' for category,count in categories.items()]
    lines += ['',
        'The USD suites used Blender Python 3.11.13 with USD 0.25.8 for real stages, layers, calibrated assets, transforms, removals and projections. Kit viewport, renderer, timeline, HTTP and GPU boundaries were injected fakes where those suites required them; image fixtures do not constitute rendered or biological validation. Pure suites used system Python 3.14.4. Exact commands, runtimes, durations and stdout/stderr hashes are in [results.json](results.json) and each execution record.', '',
        'All 283 pinned source/input files stayed unchanged. AST syntax checks passed for 139 Python files, and `git diff --check` returned 0. This offline command made no live Kit calls, GPU renders, GAMA executions or ML training runs.', '',
        'The historical [m7_package.py](../../../gsd_pilot_v1/qa/m7_package.py) stopped at line 33: `assert spec["schema_version"] == "1.6.0"`. The current preserved final specification is **1.7.0**, SHA-256 `'+records[0]['sha256']+'`; its archived M7 specification is **1.6.0**, SHA-256 `'+records[1]['sha256']+'`. Both match their entries in the preserved baseline manifest.', '',
        'No package outputs were written: the failing assertion preceded the script\'s sole output write at line '+str(writes[0].lineno)+', and the existing M7 package manifest matched both pre/post execution pins and its preserved baseline hash. The [original traceback](pilot_sealed_package.stderr.log) and failed execution remain unchanged. No source fix, Pilot rewrite or successful rerun was substituted.', '',
        'This extra historical failure does not invalidate the 360 current regression passes or an independently retained live demonstration audit. These offline artifacts do not certify live rendering, optics, biology or completion of the blocked M7 150-view dataset.', '',
        '[Machine-readable disposition](historical_package_disposition.json) contains the assertion, original command/result, current and historical specification pins, baseline evidence and write-boundary analysis.', '']
    with outputs[1].open('x') as stream:
        stream.write('\n'.join(lines))
    assert originals == {path:pin(Path(path)) for path in originals}
    print(json.dumps({'created':[pin(path) for path in outputs], 'original_files_unchanged':len(originals), 'package_write_line':writes[0].lineno, 'normal_unittest_cases_passed':360},indent=2))


if __name__ == '__main__':
    main()
