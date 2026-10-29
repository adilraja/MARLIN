"""Launch the documented existing MARLIN app once, without inspecting runtime files."""
import json
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[3]
out = Path(__file__).resolve().parents[1]
attempt = sys.argv[1] if len(sys.argv) == 2 else '01'
if attempt not in ('01', '02'):
    raise ValueError('Only the bounded first launch and one corrected retry are allowed')
probe = subprocess.run(['pgrep', '-af', '(^|/)(kit|cris.madil.kit.sh)( |$)'], capture_output=True, text=True)
if probe.returncode == 0:
    raise RuntimeError('Kit already running; refusing duplicate launch: ' + probe.stdout)
gpu = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,memory.used,memory.free,driver_version',
                      '--format=csv,noheader,nounits'], capture_output=True, text=True, check=True)
if int(gpu.stdout.splitlines()[0].split(',')[3]) < 2048:
    raise RuntimeError('Less than 2048 MiB free before startup')
work = root/'_build/linux-x86_64/release'
command = [str(work/'cris.madil.kit.sh'), '--enable', 'cris.madil.render_service',
           '--exec', str(out/'qa/audit_in_kit.py'), '--/log/file='+str(out/f'qa/kit_audit_{attempt}.log')]
with (out/f'qa/launch_stdout_{attempt}.log').open('x') as stream:
    child = subprocess.Popen(command, cwd=work, stdin=subprocess.DEVNULL,
                             stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
record = {'pid': child.pid, 'command': command, 'gpu_before': gpu.stdout,
          'note': 'Launch only; runtime execution result determines audit status.'}
(out/f'qa/launch_{attempt}.json').write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps(record, indent=2))
