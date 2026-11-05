"""Describe repeated RGB differences separately from state reproducibility."""
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parent
plan=json.loads((ROOT/'locked_plan_v3.json').read_text())
primary=json.loads((ROOT/plan['primary_run']/'result.json').read_text())
fresh=json.loads((ROOT/'fresh01/result.json').read_text())
assert primary['status']==fresh['status']=='passed'
original={r['simulation_time_s']:r for r in primary['captures'] if not r['label'].startswith('reorder_')}
comparisons=[]
for run in [primary,fresh]:
 for record in run['captures']:
  if not record['label'].startswith(('reorder_','fresh_')):continue
  reference=Path(primary['media_directory'])/original[record['simulation_time_s']]['label']
  candidate=Path(run['media_directory'])/record['label']
  with np.load(reference/'hdr.npz') as z:a=z['rgba'][...,:3].astype(float)
  with np.load(candidate/'hdr.npz') as z:b=z['rgba'][...,:3].astype(float)
  delta=np.abs(a-b)
  before=json.loads((reference/'effective_settings.json').read_text())
  after=json.loads((candidate/'effective_settings.json').read_text())
  changes=[]
  for section in ['camera','render_product']:
   for name in sorted(set(before[section])|set(after[section])):
    if before[section].get(name)!=after[section].get(name):changes.append(section+'/'+name)
  comparisons.append(dict(run=run['run_id'],time_s=record['simulation_time_s'],
   label=record['label'],hdr_exactly_equal=bool(np.array_equal(a,b)),
   mean_absolute_hdr_difference=float(delta.mean()),p99_absolute_hdr_difference=float(np.percentile(delta,99)),
   maximum_absolute_hdr_difference=float(delta.max()),effective_attribute_differences=changes,
   state_comparison='Evaluated separately against locked root/joint/phase/skin criteria'))
report=dict(completed=True,comparisons=comparisons,rgb_identity_required=False,
 interpretation='Native HDR differences are reported without a fitted RGB tolerance. Exact state does not establish RGB identity or sample-count, optical, radiometric or sensor qualification.')
with (ROOT/'rgb_comparison.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(dict(comparisons=len(comparisons),all_hdr_exactly_equal=all(r['hdr_exactly_equal'] for r in comparisons),
 max_observed_mean_absolute_hdr_difference=max(r['mean_absolute_hdr_difference'] for r in comparisons))))
