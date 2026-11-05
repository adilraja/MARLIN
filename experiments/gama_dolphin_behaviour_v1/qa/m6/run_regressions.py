"""Execute the declared, isolated regression commands and preserve all output."""
import concurrent.futures
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[3]


def main():
    plan=json.loads((ROOT/'locked_plan.json').read_text())
    output=ROOT/'regressions_attempt01';output.mkdir(exist_ok=False)
    env=os.environ.copy()
    env['PYTHONDONTWRITEBYTECODE']='1'
    env['PYTHONPATH']=str(REPO/plan['canonical_render_module_path'])+':'+str(REPO/'tools')
    env['MPLCONFIGDIR']='/tmp/marlin-m6-matplotlib'
    def run(item):
        start=time.monotonic()
        result=subprocess.run(item['command'],cwd=REPO,env=env,capture_output=True,text=True,timeout=180)
        text=result.stdout+'\n'+result.stderr
        match=re.search(r'Ran (\d+) tests?',text)
        skipped=re.search(r'OK \(skipped=(\d+)\)',text)
        count=int(match.group(1)) if match else None
        record=dict(id=item['id'],command=item['command'],returncode=result.returncode,
            tests=count,skipped=int(skipped.group(1)) if skipped else 0,
            stdout=result.stdout,stderr=result.stderr,wall_s=time.monotonic()-start,
            utc=datetime.now(timezone.utc).isoformat())
        with (output/(item['id']+'.json')).open('x') as stream:json.dump(record,stream,indent=2);stream.write('\n')
        return record
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        records=list(pool.map(run,plan['regressions']))
    summary=dict(passed=all(r['returncode']==0 for r in records),commands=len(records),
        discovered_tests=sum(r['tests'] or 0 for r in records),
        passed_tests=sum((r['tests'] or 0)-r['skipped'] for r in records if r['returncode']==0),
        skipped_tests=sum(r['skipped'] for r in records),
        failed_commands=[r['id'] for r in records if r['returncode']],
        unknown_test_counts=[r['id'] for r in records if r['tests'] is None],
        scope='Existing bridge/camera/controller/water suites, this sprint M2/M3/M4 suites, fixed HDR display; independent processes, no production writes.')
    with (ROOT/'regression_summary_attempt01.json').open('x') as stream:json.dump(summary,stream,indent=2);stream.write('\n')
    print(json.dumps(summary,indent=2))
    raise SystemExit(0 if summary['passed'] and not summary['unknown_test_counts'] else 1)


if __name__=='__main__':main()
