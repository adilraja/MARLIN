"""Finite, private Kit transaction; the main application is never launched/edited."""
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
RUNTIME = REPO/'_build/linux-x86_64/release'


def write(p, value):
    p.write_text(json.dumps(value, indent=2)+'\n')


def gpu():
    r = subprocess.run(['nvidia-smi', '--query-gpu=memory.free,memory.total,driver_version',
                        '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=10)
    assert r.returncode == 0, r.stderr
    free, total, driver = r.stdout.strip().splitlines()[0].split(',')
    return dict(free_mib=int(free), total_mib=int(total), driver=driver.strip())


def run(label, worker, config, rendering=False, batch=None):
    assert label.replace('_', '').isalnum() and len(label) < 48
    other = subprocess.run(['ps', '-C', 'kit', '-o', 'pid=,args='], capture_output=True, text=True, timeout=10)
    assert other.returncode in (0, 1) and not other.stdout.strip(), 'Existing Kit must remain untouched'
    assert shutil.disk_usage(REPO).free > 10*1024**3
    before = gpu() if rendering else None
    if before: assert before['free_mib'] >= 2048, before
    out = BASE/'diagnostics/m2_execution_v1/runs'/label
    out.mkdir(parents=True, exist_ok=False)
    profile = Path('/tmp')/('marlin_annotation_execution_'+label)
    profile.mkdir(mode=0o700, exist_ok=False)
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE='1', ANNOTATION_EXECUTION_OUTPUT=str(out))
    if batch: env['ANNOTATION_CAPTURE_BATCH'] = batch
    env.pop('DISPLAY', None); env.pop('WAYLAND_DISPLAY', None)
    env['GDK_BACKEND'] = 'x11'
    for key, child in [('XDG_CACHE_HOME', 'xdg_cache'), ('XDG_CONFIG_HOME', 'xdg_config'),
                       ('XDG_DATA_HOME', 'xdg_data'), ('CUDA_CACHE_PATH', 'cuda_cache'),
                       ('__GL_SHADER_DISK_CACHE_PATH', 'gl_cache'), ('XDG_RUNTIME_DIR', 'xdg_runtime')]:
        folder = profile/child; folder.mkdir(mode=0o700)
        env[key] = str(folder)
    for src, name in [(worker, 'worker.py'), (config, 'app.kit'), (HERE/'launch.py', 'launch.py')]:
        shutil.copyfile(src, out/name)
    args = [str(RUNTIME/'kit/kit'), str(out/'app.kit'),
            '--ext-folder', str(RUNTIME/'exts'), '--ext-folder', str(RUNTIME/'extscache'),
            '--no-window', '--portable', '--portable-root='+str(profile/'portable'),
            '--/app/extensions/registryEnabled=false', '--/app/extensions/syncRegistryOnStartup=false',
            '--/app/settings/loadUserConfig=false', '--/app/settings/saveUserConfig=false',
            '--/app/settings/persistent=false', '--/app/file/ignoreUnsavedOnExit=true',
            '--/rtx-transient/resourcemanager/localTextureCachePath='+str(profile/'textures'),
            '--/log/file='+str(out/'kit_process.log'), '--exec', str(out/'worker.py')]
    private = BASE/'dependencies/native_provider_1102_v1/extensions'
    if private.exists(): args[2:2] = ['--ext-folder', str(private)]
    start = time.monotonic()
    with (out/'stdout.log').open('x') as stream:
        process = subprocess.Popen(args, cwd=REPO, env=env, stdin=subprocess.DEVNULL,
                                   stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
    write(out/'launch.json', dict(recorded_utc=datetime.now(timezone.utc).isoformat(), pid=process.pid,
          command=args, profile=str(profile), existing_kit_before='', gpu_before=before,
          source_sha256={f: hashlib.sha256((out/f).read_bytes()).hexdigest()
                         for f in ('app.kit', 'worker.py', 'launch.py')}))
    print('Started private transaction', label, 'PID', process.pid, flush=True)
    signals = []; reason = None; quit_seen = None; ready_seen = None; samples = []
    while process.poll() is None:
        elapsed = time.monotonic()-start
        if (out/'ready.json').exists() and ready_seen is None: ready_seen = time.monotonic()
        if (out/'result.json').exists() and quit_seen is None: quit_seen = time.monotonic()
        if rendering:
            current = gpu(); samples.append(dict(elapsed_s=elapsed, **current))
            if current['free_mib'] < 768: reason = '768 MiB GPU free-memory floor breached'
        if elapsed > 120 and ready_seen is None and quit_seen is None: reason = '120-second startup deadline exceeded'
        if elapsed > 600: reason = '600-second transaction deadline exceeded'
        if quit_seen is not None and time.monotonic()-quit_seen > 30: reason = '30-second normal-exit deadline exceeded'
        if reason:
            os.killpg(process.pid, signal.SIGTERM); signals.append('SIGTERM owned process group')
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); signals.append('SIGKILL owned process group'); process.wait(timeout=10)
            break
        time.sleep(1)
    result = json.loads((out/'result.json').read_text()) if (out/'result.json').exists() else None
    record = dict(returncode=process.returncode, elapsed_seconds=time.monotonic()-start,
                  termination_reason=reason, cleanup_signals=signals, worker_returned=result is not None,
                  clean_exit=bool(result and result['passed'] and process.returncode == 0 and not signals),
                  gpu_samples=samples, gpu_after=gpu() if rendering else None)
    write(out/'exit.json', record)
    print(json.dumps({k:v for k,v in record.items() if k != 'gpu_samples'}), flush=True)
    return 0 if record['clean_exit'] else 1


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('label'); p.add_argument('worker', type=Path)
    p.add_argument('config', type=Path); p.add_argument('--rendering', action='store_true'); p.add_argument('--batch')
    a = p.parse_args(); raise SystemExit(run(a.label, a.worker, a.config, a.rendering, a.batch))
