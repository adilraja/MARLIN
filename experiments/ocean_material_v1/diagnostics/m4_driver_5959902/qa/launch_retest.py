"""Checkpoint/close the owned MARLIN process and run the frozen private SDK test."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[3]
OLD = ROOT.parent / 'm4_standalone'
M6 = ROOT.parent / 'm6'
OUT = ROOT / 'run_01'


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def gpu():
    result = subprocess.check_output(['nvidia-smi', '--query-gpu=name,memory.total,memory.used,memory.free,driver_version',
                                     '--format=csv,noheader,nounits'], text=True, timeout=10)
    row = [v.strip() for v in result.strip().split(',')]
    return dict(name=row[0], total_mib=int(row[1]), used_mib=int(row[2]), free_mib=int(row[3]), driver=row[4])


def main():
    OUT.mkdir(exist_ok=False)
    checkpoint = json.loads((M6 / 'qa/pre_work_checkpoint.json').read_text())
    assert hashlib.sha256((Path(checkpoint['directory']) / 'scene.usdc').read_bytes()).hexdigest() == checkpoint['scene_sha256']
    pid = json.loads((M6 / 'qa/preparation.json').read_text())['kit_process_group']
    command = (Path('/proc') / str(pid) / 'cmdline').read_bytes().replace(b'\0', b' ').decode()
    assert 'cris.madil.kit' in command and 'm5/qa/audit_in_kit.py' in command
    assert os.getpgid(pid) == pid
    write(ROOT / 'qa/marlin_shutdown.json', dict(pid=pid, command=command, signal='SIGTERM',
          checkpoint_id=checkpoint['checkpoint_id'], gpu_before=gpu()))
    os.killpg(pid, signal.SIGTERM)
    deadline = time.monotonic() + 50
    while True:
        check = subprocess.run(['pgrep', '-af', '(^|/)(kit|cris.madil.kit.sh)( |$)'], capture_output=True, text=True)
        if check.returncode == 1:
            break
        if time.monotonic() >= deadline:
            raise RuntimeError('Owned MARLIN did not close; no second renderer launched')
        time.sleep(1)
    before = gpu()
    assert before['driver'] == '595.99.02' and before['free_mib'] >= 2048
    sdk = OLD / 'work/sdk-1102'
    private = OLD / 'work/profile_baseline'
    env = os.environ.copy()
    for key, child in [('XDG_CACHE_HOME', 'xdg_cache'), ('XDG_CONFIG_HOME', 'xdg_config'),
                       ('XDG_DATA_HOME', 'xdg_data'), ('CUDA_CACHE_PATH', 'cuda_cache'),
                       ('__GL_SHADER_DISK_CACHE_PATH', 'gl_cache')]:
        env[key] = str(private / child)
    env.update(PYTHONDONTWRITEBYTECODE='1', WATER_REPRO_ROOT=str(OLD), WATER_REPRO_OUTPUT=str(OUT),
               WATER_REPRO_SUITE='initial', WATER_REPRO_SDK=str(sdk))
    args = [str(sdk / 'kit'), str(OLD / 'standalone.kit'), '--portable-root', str(private / 'portable'),
            '--no-window', '--/rtx-transient/resourcemanager/localTextureCachePath=' + str(private / 'texture_cache'),
            '--/log/file=' + str(OUT / 'kit_process.log'), '--exec', str(ROOT / 'qa/capture_in_kit.py')]
    started = time.monotonic()
    with (OUT / 'stdout.log').open('x') as stream:
        process = subprocess.Popen(args, cwd=sdk, env=env, stdin=subprocess.DEVNULL,
                                   stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
    write(OUT / 'launch.json', dict(pid=process.pid, command=args, gpu_before=before,
          reused_private_profile=str(private), harness_sha256=hashlib.sha256((ROOT / 'qa/capture_in_kit.py').read_bytes()).hexdigest()))
    print(json.dumps(dict(pid=process.pid, gpu_before=before, output=str(OUT))), flush=True)
    samples = []
    deadline = started + 480
    while process.poll() is None and time.monotonic() < deadline:
        try:
            samples.append(dict(elapsed_seconds=time.monotonic()-started, **gpu()))
        except Exception as exc:
            samples.append(dict(elapsed_seconds=time.monotonic()-started, error=str(exc)))
        write(OUT / 'gpu_samples.json', samples)
        time.sleep(1)
    if process.poll() is None:
        process.terminate()
        process.wait(timeout=30)
        raise RuntimeError('Bounded reproduction timed out; evidence preserved')
    write(OUT / 'exit.json', dict(exit_code=process.returncode, elapsed_seconds=time.monotonic()-started,
          sampled_peak_used_mib=max(x['used_mib'] for x in samples if 'used_mib' in x),
          sampled_minimum_free_mib=min(x['free_mib'] for x in samples if 'free_mib' in x)))
    result = json.loads((OUT / 'result.json').read_text()) if (OUT / 'result.json').exists() else dict(ok=False, error='No native result file')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
