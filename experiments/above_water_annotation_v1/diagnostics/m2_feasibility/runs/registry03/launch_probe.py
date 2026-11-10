"""Finite, offline Kit query. Never stop an existing Kit or install a package."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]
REPO = BASE.parents[1]
RUNTIME = REPO / '_build/linux-x86_64/release'
RUNS = BASE / 'diagnostics/m2_feasibility/runs'


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def gpu():
    row = subprocess.check_output([
        'nvidia-smi', '--query-gpu=name,driver_version,memory.total,memory.free',
        '--format=csv,noheader,nounits'], text=True, timeout=10).strip().split(',')
    assert len(row) == 4, 'Exactly one GPU is required by this probe'
    return dict(name=row[0].strip(), driver=row[1].strip(),
                total_mib=int(row[2]), free_mib=int(row[3]))


def kits():
    result = subprocess.run(['ps', '-C', 'kit', '-o', 'pid=,args='],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode in (0, 1), result.stderr
    return result.stdout.strip()


def run(label, app_name):
    assert label.replace('_', '').isalnum() and len(label) < 48
    assert not kits(), 'Existing Kit found; do not launch or stop it'
    before = gpu()
    assert before['free_mib'] >= 2048, before
    assert shutil.disk_usage(REPO).free >= 10 * 1024**3
    out = RUNS / label
    out.mkdir(parents=True, exist_ok=False)
    profile = Path('/tmp') / ('marlin_above_water_m2_' + label)
    assert not profile.exists(), 'Refuse to reuse a private profile'
    profile.mkdir()
    for filename in ('launch_probe.py', 'query_provider.py', app_name + '.kit'):
        shutil.copyfile(HERE / filename, out / filename)
    env = os.environ.copy()
    for key, child in [('XDG_CACHE_HOME', 'xdg_cache'), ('XDG_CONFIG_HOME', 'xdg_config'),
                       ('XDG_DATA_HOME', 'xdg_data'), ('CUDA_CACHE_PATH', 'cuda_cache'),
                       ('__GL_SHADER_DISK_CACHE_PATH', 'gl_cache')]:
        env[key] = str(profile / child)
    env.update(PYTHONDONTWRITEBYTECODE='1', ABOVE_WATER_M2_OUTPUT=str(out))
    if app_name == 'registry':
        env['ABOVE_WATER_M2_REGISTRY_QUERY'] = '1'
        env['ABOVE_WATER_M2_SYNC_INDEX'] = '1'
        env['ABOVE_WATER_M2_INDEX_ACCESS'] = '1'
    if app_name == 'renderer':
        env['ABOVE_WATER_M2_STAGE_CYCLE'] = '1'
        # A truly headless child process must not inherit the user's Wayland/X11
        # connection. Vulkan rendering does not require a desktop output here.
        # This changes only the new child environment, never the desktop session.
        env.pop('DISPLAY', None)
        env.pop('WAYLAND_DISPLAY', None)
        # GTK can still find wayland-0 through XDG_RUNTIME_DIR when DISPLAY and
        # WAYLAND_DISPLAY are absent. Confine it to an empty private runtime dir
        # and the X11 backend with no display. This is a diagnostic child only.
        runtime_dir = profile / 'xdg_runtime'
        runtime_dir.mkdir(mode=0o700)
        env['XDG_RUNTIME_DIR'] = str(runtime_dir)
        env['GDK_BACKEND'] = 'x11'
    args = [str(RUNTIME/'kit/kit'), str(out/(app_name+'.kit')),
            '--ext-folder', str(RUNTIME/'exts'), '--ext-folder', str(RUNTIME/'extscache'),
            '--no-window', '--portable', '--portable-root=' + str(profile/'portable'),
            '--/app/extensions/registryEnabled=false',
            '--/app/extensions/syncRegistryOnStartup=false',
            '--/app/extensions/registryCache=' + str(profile/'extensions'),
            '--/app/settings/loadUserConfig=false', '--/app/settings/saveUserConfig=false',
            '--/app/settings/persistent=false', '--/app/file/ignoreUnsavedOnExit=true',
            '--/rtx-transient/resourcemanager/localTextureCachePath=' + str(profile/'textures'),
            '--/log/file=' + str(out/'kit_process.log'), '--exec', str(out/'query_provider.py')]
    started = time.monotonic()
    with (out/'stdout.log').open('x') as stream:
        process = subprocess.Popen(args, cwd=REPO, env=env, stdin=subprocess.DEVNULL,
                                   stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
    write(out/'launch.json', dict(recorded_utc=datetime.now(timezone.utc).isoformat(),
          pid=process.pid, command=args, profile=str(profile), gpu_before=before,
          desktop_connection_inherited=app_name != 'renderer',
          headless_environment={key: env.get(key) for key in
                                ('DISPLAY','WAYLAND_DISPLAY','XDG_RUNTIME_DIR','GDK_BACKEND')},
          disk_free_bytes=shutil.disk_usage(REPO).free, existing_kit_before='',
          source_sha256={f: hashlib.sha256((out/f).read_bytes()).hexdigest()
                         for f in ('launch_probe.py','query_provider.py',app_name+'.kit')}))
    print(f'Started {label}, owned PID {process.pid}', flush=True)
    samples, signals = [], []
    reason = None
    quit_seen_at = None
    while process.poll() is None:
        elapsed = time.monotonic() - started
        current = gpu()
        samples.append(dict(elapsed_seconds=elapsed, **current))
        write(out/'gpu_samples.json', samples)
        if (out/'query.json').exists() and quit_seen_at is None:
            quit_seen_at = time.monotonic()
        if current['free_mib'] < 768:
            reason = 'free GPU memory fell below the 768 MiB floor'
        elif quit_seen_at is not None and time.monotonic()-quit_seen_at > 30:
            reason = 'normal shutdown exceeded 30 seconds'
        elif quit_seen_at is None and elapsed > 120:
            reason = 'startup/query exceeded 120 seconds'
        if reason:
            signals.append('SIGTERM owned process group')
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                signals.append('SIGKILL owned process group')
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)
            break
        time.sleep(1)
    time.sleep(1)
    query = json.loads((out/'query.json').read_text()) if (out/'query.json').exists() else None
    result = dict(returncode=process.returncode, elapsed_seconds=time.monotonic()-started,
                  termination_reason=reason, cleanup_signals=signals,
                  query_returned=query is not None, app=app_name,
                  clean_exit=process.returncode == 0 and not signals and bool(query and query['passed']),
                  gpu_after=gpu(), remaining_kit_processes=kits(), captures=0,
                  minimum_observed_free_mib=min(s['free_mib'] for s in samples) if samples else None)
    write(out/'exit.json', result)
    print(json.dumps(result), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('label')
    parser.add_argument('app', choices=('metadata', 'renderer', 'registry'))
    options = parser.parse_args()
    run(options.label, options.app)
