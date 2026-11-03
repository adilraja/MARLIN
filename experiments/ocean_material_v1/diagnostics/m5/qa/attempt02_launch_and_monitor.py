"""Launch the documented MARLIN app once and sample GPU memory during M5."""
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[3]
ATTEMPT = sys.argv[1] if len(sys.argv) == 2 else '01'
if ATTEMPT not in ('01', '02'):
    raise ValueError('Only explicitly recorded audit attempts are supported')
RUN = ROOT / ('runs/attempt' + ATTEMPT)
OUT = ROOT / 'qa/driver_recovery_2026_11_03' / ('post_reboot' if ATTEMPT == '01' else 'post_reboot_retry02')


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def gpu():
    p = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,memory.used,memory.free,driver_version',
                         '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=10, check=True)
    row = next(csv.reader(p.stdout.splitlines(), skipinitialspace=True))
    return dict(name=row[0], total_mib=int(row[1]), used_mib=int(row[2]), free_mib=int(row[3]), driver=row[4])


def main():
    OUT.mkdir(exist_ok=False)
    diagnosis = json.loads((OUT.parent / 'diagnosis.json').read_text())
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    assert boot != diagnosis['boot_id'], 'A new boot was required'
    loaded = Path('/proc/driver/nvidia/version').read_text()
    installed = subprocess.check_output(['modinfo', '-F', 'version', 'nvidia'], text=True).strip()
    before = gpu()
    assert re.search(r'\b' + re.escape(installed) + r'\b', loaded)
    assert before['driver'] == installed
    assert before['free_mib'] >= 2048
    verification = subprocess.run(['/usr/bin/python3', '-B', str(ROOT / 'qa/verify_preparation.py')],
                                  text=True, capture_output=True, check=True)
    write(OUT / 'verification.json', dict(utc=datetime.now(timezone.utc).isoformat(), boot_id=boot,
          loaded_driver=loaded, installed_module=installed, gpu_before=before,
          protected_evidence=json.loads(verification.stdout)))
    try:
        urlopen('http://localhost:8011/docs', timeout=2).close()
        raise RuntimeError('MARLIN is already running; refusing a duplicate launch')
    except URLError:
        pass
    process_check = subprocess.run(['pgrep', '-af', '(^|/)(kit|cris.madil.kit.sh)( |$)'], capture_output=True, text=True)
    assert process_check.returncode == 1, process_check.stdout
    script = ROOT / 'qa/audit_in_kit.py'
    compile(script.read_text(), str(script), 'exec')
    work = REPO / '_build/linux-x86_64/release'
    command = [str(work / 'cris.madil.kit.sh'), '--enable', 'cris.madil.render_service',
               '--exec', str(script), '--/log/file=' + str(OUT / 'kit_process.log')]
    with (OUT / 'launch_stdout.log').open('x') as stream:
        process = subprocess.Popen(command, cwd=work, stdin=subprocess.DEVNULL,
                                   stdout=stream, stderr=subprocess.STDOUT, start_new_session=True,
                                   env=dict(os.environ, MARLIN_M5_ATTEMPT=ATTEMPT))
    write(OUT / 'launch.json', dict(pid=process.pid, command=command,
          audit_sha256=hashlib.sha256(script.read_bytes()).hexdigest(), monotonic=time.monotonic()))
    samples = []
    deadline = time.monotonic() + 420
    print(json.dumps(dict(launched_pid=process.pid, gpu_before=before)), flush=True)
    try:
        while time.monotonic() < deadline:
            sample = dict(monotonic=time.monotonic(), utc=datetime.now(timezone.utc).isoformat())
            try:
                sample.update(gpu())
            except Exception as exc:
                sample['error'] = str(exc)
            samples.append(sample)
            write(OUT / 'gpu_samples.json', samples)
            if (RUN / 'done.json').exists() or (RUN / 'audit_failure.json').exists():
                break
            if process.poll() is not None:
                raise RuntimeError('Launched MARLIN exited before audit completion')
            time.sleep(1)
        else:
            raise RuntimeError('Bounded audit monitor expired; MARLIN retained for inspection')
        result_path = RUN / ('done.json' if (RUN / 'done.json').exists() else 'audit_failure.json')
        result = json.loads(result_path.read_text())
        write(OUT / 'monitor_result.json', dict(audit_result=result, sampled_peak_used_mib=max(s['used_mib'] for s in samples if 'used_mib' in s),
              sampled_minimum_free_mib=min(s['free_mib'] for s in samples if 'free_mib' in s), sample_count=len(samples),
              sample_scope='Startup through audit completion; approximately one sample per second, not exact allocation peak'))
        print(json.dumps(result, indent=2), flush=True)
    except BaseException as exc:
        write(OUT / 'monitor_failure.json', dict(error=str(exc), samples_retained=len(samples)))
        raise


if __name__ == '__main__':
    main()
