"""Checkpoint-verified replacement of the known MARLIN process for M5 QA."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[3]


def main(mode):
    assert mode in ('primary', 'primary_retry', 'primary_retry02', 'primary_retry03', 'fresh', 'audit')
    if mode == 'fresh':
        result = json.loads((ROOT/'primary02/result.json').read_text())
        assert result['status']=='passed' and all(result['restoration'].values())
    output = ROOT / ('launch_'+mode)
    output.mkdir(exist_ok=False)
    if mode == 'primary':
        old_record = ROOT.parent/'m4/live_restore_gui_final/launch.json'
    elif mode == 'primary_retry':
        old_record = ROOT/'launch_primary/launch.json'
    elif mode == 'primary_retry02':
        old_record = ROOT/'launch_primary_retry/launch.json'
    elif mode == 'primary_retry03':
        old_record = ROOT/'launch_primary_retry02/launch.json'
    elif mode == 'fresh':
        old_record = ROOT/'launch_primary_retry03/launch.json'
    else:
        assert json.loads((ROOT/'fresh01/result.json').read_text())['status']=='passed'
        old_record = ROOT/'launch_fresh/launch.json'
    previous = json.loads(old_record.read_text())
    pid = previous['pid']
    cmdline = (Path('/proc')/str(pid)/'cmdline').read_bytes()
    assert b'cris.madil.kit' in cmdline and str(REPO).encode() in cmdline
    checkpoint = json.loads((ROOT/'live_before/checkpoint.json').read_text())
    import hashlib
    assert hashlib.sha256((Path(checkpoint['directory'])/'scene.usdc').read_bytes()).hexdigest()==checkpoint['scene_sha256']
    env = os.environ.copy()
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    old_env = (Path('/proc')/str(pid)/'environ').read_bytes().split(b'\0')
    for item in old_env:
        if b'=' in item:
            name, value = item.split(b'=', 1)
            if name.decode() in ('DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY', 'XDG_RUNTIME_DIR', 'DBUS_SESSION_BUS_ADDRESS'):
                env[name.decode()] = value.decode()
    (output/'old_process.json').write_text(json.dumps(dict(pid=pid, command=cmdline.decode().split('\0'),
        checkpoint=checkpoint['checkpoint_id'], requested_signal='SIGTERM', utc=datetime.now(timezone.utc).isoformat()),indent=2)+'\n')
    os.kill(pid, signal.SIGTERM)
    for _ in range(120):
        status=Path('/proc')/str(pid)/'stat'
        if not status.exists() or status.read_text().split(') ',1)[1].startswith('Z'):
            break
        time.sleep(.25)
    else:
        raise RuntimeError('Known MARLIN process did not exit after SIGTERM; no new instance started')
    command=[str(REPO/'_build/linux-x86_64/release/cris.madil.kit.sh'),
        '--enable','cris.madil.render_service','--enable','cris.madil.gama_bridge',
        '--ext-folder',str(REPO/'source/extensions'),'--exec',str(ROOT/('entry_'+mode+'.py')),
        '--/log/file='+str(output/'kit_process.log'),'--/app/window/enabled=true',
        '--/app/window/width=1280','--/app/window/height=720',
        '--/persistent/app/window/width=1280','--/persistent/app/window/height=720',
        '--/app/window/maximized=false','--/persistent/app/window/maximized=false',
        '--/app/window/saveSizeOnExit=false','--/app/file/ignoreUnsavedOnExit=true']
    with (output/'launcher.log').open('x') as stream:
        process=subprocess.Popen(command,cwd=REPO/'_build/linux-x86_64/release',env=env,
                                 stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
    record=dict(pid=process.pid, command=command, utc=datetime.now(timezone.utc).isoformat(),
        old_process_exit_code='Not observable by this launcher; recorded disappearance after SIGTERM',
        purpose='Checkpointed implementation loading and required M5 fresh-process replay')
    (output/'launch.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(dict(mode=mode,pid=process.pid,checkpoint=checkpoint['checkpoint_id'])))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['primary','primary_retry','primary_retry02','primary_retry03','fresh','audit'])
    main(parser.parse_args().mode)
