"""Read-only evidence verification; a pass here does not complete M2 or Gate B."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import tomllib

BASE = Path(__file__).resolve().parents[2]
REPO = BASE.parents[1]
EVIDENCE = BASE / 'diagnostics/m2_feasibility'
FORBIDDEN = {'_build', 'extscache', '__pycache__', '.cache'}


def read(path):
    return json.loads(path.read_text())


def main():
    manifest = read(EVIDENCE/'manifest.json')
    assert manifest['scope'] == 'M2 feasibility only; no dry/native annotation acceptance'
    assert not manifest['milestone_2_complete']
    for record in manifest['files']:
        path = Path(record['path'])
        assert not path.is_absolute() and '..' not in path.parts
        assert not FORBIDDEN.intersection(path.parts) and path.suffix != '.pyc'
        data = (REPO/path).read_bytes()
        assert len(data) == record['bytes'], path
        assert hashlib.sha256(data).hexdigest() == record['sha256'], path

    for record in read(EVIDENCE/'preservation_before.json')['files']:
        assert hashlib.sha256((REPO/record['path']).read_bytes()).hexdigest() == record['sha256']
    for path in (BASE/'qa/m2').iterdir():
        if path.suffix == '.py':
            ast.parse(path.read_text())
        elif path.suffix == '.kit':
            tomllib.loads(path.read_text())

    ledger = read(EVIDENCE/'probe_ledger.json')
    assert ledger['diagnostic_process_count'] == len(ledger['runs']) == 12
    assert ledger['rendered_bundle_attempts'] == ledger['reserve_bundles_used'] == 0
    assert ledger['planned_bundles'] == 120 and ledger['maximum_bundles'] == 144
    assert {p.name for p in (EVIDENCE/'runs').iterdir()} == {r['id'] for r in ledger['runs']}
    profiles, pids, normal = set(), set(), []
    for record in ledger['runs']:
        root = EVIDENCE/'runs'/record['id']
        launch, exit_record = read(root/'launch.json'), read(root/'exit.json')
        assert launch['pid'] == record['pid'] and launch['pid'] not in pids
        assert launch['profile'] not in profiles
        assert launch['profile'] == '/tmp/marlin_above_water_m2_' + record['id']
        profiles.add(launch['profile']); pids.add(launch['pid'])
        assert launch['existing_kit_before'] == ''
        assert launch['gpu_before']['free_mib'] >= 2048
        assert launch['disk_free_bytes'] >= 10*1024**3
        assert '--/app/extensions/registryEnabled=false' in launch['command']
        assert '--/app/extensions/syncRegistryOnStartup=false' in launch['command']
        for filename, sha in launch['source_sha256'].items():
            assert hashlib.sha256((root/filename).read_bytes()).hexdigest() == sha
        assert exit_record['captures'] == 0 and not exit_record['remaining_kit_processes']
        assert exit_record['clean_exit'] == record['clean_exit']
        if exit_record['query_returned']:
            query = read(root/'query.json')
            assert query['build_version'] == '110.2.0+feature.342835.698af100.gl'
            assert not query['packages_pulled'] and not query['provider_enable_attempted']
            assert query['captures'] == 0 and query['passed'] and query['stage_closed']
            assert query['settings']['/app/extensions/registryEnabled'] is False
            assert not query['native_provider_entries']['get_extensions']
            assert not query['native_provider_entries']['get_extension_packages']
        if exit_record['clean_exit']:
            assert exit_record['returncode'] == 0 and not exit_record['cleanup_signals']
            assert exit_record['termination_reason'] is None
            normal.append(record['id'])
        else:
            assert record['id'] in ('metadata01', 'renderer01', 'renderer02', 'sdk1102_metadata01')
    for name in ('renderer03','renderer04'):
        root = EVIDENCE/'runs'/name
        query, result, launch = read(root/'query.json'), read(root/'exit.json'), read(root/'launch.json')
        assert name in normal and query['app_ready'] and query['scene_authored']
        assert query['stage_before_cleanup']['identifier'].startswith('anon:')
        assert result['minimum_observed_free_mib'] >= 768
        assert launch['headless_environment']['DISPLAY'] is None
        assert launch['headless_environment']['WAYLAND_DISPLAY'] is None
        assert launch['headless_environment']['GDK_BACKEND'] == 'x11'
        assert '[Error]' not in (root/'kit_process.log').read_text(errors='replace')
    for name in ('registry03','registry04'):
        remote = read(EVIDENCE/'runs'/name/'registry_queries.json')
        assert remote['private_index_access_temporarily_enabled']
        assert remote['registry_gate_restored'] and remote['installed_packages_unchanged']
        assert not remote['pulls_attempted'] and remote['metadata_sync_result'] is False
        assert all(not row[0] and not row[1] for row in remote['solver_metadata_only'].values())
    assert read(EVIDENCE/'runs/registry04/query.json')['registry_refreshed']
    assert read(EVIDENCE/'runs/sdk1102_metadata02/query.json')['inventory_counts']['get_extension_packages'] == 102
    host = read(EVIDENCE/'host_after.json')
    assert not host['kit_processes']['stdout'] and host['service']['returncode'] == 7
    assert '595.99.02' in host['kernel_driver'] and '595.99.02' in host['gpu']['stdout']
    assert not [p for p in EVIDENCE.rglob('*') if p.suffix.lower() in
                {'.png','.exr','.npz','.npy','.usd','.usdc'}]
    status = read(BASE/'CURRENT_SPRINT_STATUS.json')
    assert status['milestones']['M2'] == 'stopped_before_dependency_installation'
    assert not status['milestone_2_complete'] and status['gate_b'] == 'not_ready'
    assert not status['new_dependencies_installed'] and not status['production_implementation_started']
    audit = subprocess.run(['/usr/bin/python3', '-B', str(BASE/'qa/m1/verify_gate_a_acceptance.py')],
                           cwd=REPO, capture_output=True, text=True, check=True)
    historical = json.loads(audit.stdout)
    assert historical['passed'] and historical['reviewer'] == 'MAR'
    return dict(evidence_verification_passed=True, scope=manifest['scope'],
                manifest_files_verified=len(manifest['files']), diagnostic_processes=12,
                successful_private_renderer_lifecycles=2, native_provider_installed=False,
                compatible_dependency_pin_resolved=False, new_dependencies_installed=False,
                rendered_bundle_attempts=0, source_and_accepted_evidence_preserved=True,
                canonical_source_files_verified=historical['audit_verification']['canonical_source_files_unchanged'],
                milestone_2_complete=False, gate_b='not_ready', separate_ocean_material_m4='open')


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
