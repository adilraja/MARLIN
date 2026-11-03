"""Dismiss only a test-owned, informational IOMMU notice; preserve its text."""
import argparse
import json
import os
from pathlib import Path
import signal

ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('run');args=parser.parse_args()
if '/' in args.run or '..' in args.run:raise ValueError('Use an experiment run directory name')
run=ROOT/'runs'/args.run;owned=json.loads((run/'launch.json').read_text())['pid'];records=[]
for process in Path('/proc').iterdir():
    if not process.name.isdigit():continue
    try:
        argv=[a.decode(errors='replace') for a in (process/'cmdline').read_bytes().split(b'\0') if a]
        if not argv or Path(argv[0]).name!='zenity' or '--info' not in argv or 'IOMMU Enabled' not in argv:continue
        parent=int((process/'stat').read_text().split()[3]);ancestors=[]
        for _ in range(8):
            ancestors.append(parent)
            if parent in (0,1) or parent==owned:break
            parent=int((Path('/proc')/str(parent)/'stat').read_text().split()[3])
        if owned not in ancestors:continue
        records.append({'pid':int(process.name),'argv':argv,'ancestors':ancestors,
                        'action':'Dismiss informational notice only; no host or renderer setting changed'})
        os.kill(int(process.name),signal.SIGTERM)
    except (FileNotFoundError,PermissionError,ProcessLookupError):pass
destination=run/'startup_information_dialog.json'
if destination.exists():raise RuntimeError('Notice record already exists')
destination.write_text(json.dumps(records,indent=2)+'\n')
print('Owned informational notices dismissed:',len(records))
