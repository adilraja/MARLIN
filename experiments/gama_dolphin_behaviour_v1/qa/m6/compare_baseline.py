"""Compare every composed prim/property in the pre-work and final checkpoints."""
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('_m5_baseline_comparison',ROOT.parent/'m4/compare_restored_gui_stage.py')
previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
before=previous.record(ROOT/'live_before/scene.usdc')
after=previous.record(ROOT/'live_final/scene.usdc')
missing=sorted(before.keys()-after.keys());extra=sorted(after.keys()-before.keys());changes=[]
for path in sorted(before.keys()&after.keys()):
 for field in sorted(before[path].keys()|after[path].keys()):
  if before[path].get(field)!=after[path].get(field):changes.append(dict(path=path,property=field))
report=dict(passed=not missing and not extra and not changes,prims_before=len(before),prims_after=len(after),
 missing=missing,extra=extra,differences=changes,allowed_exceptions=[])
with (ROOT/'baseline_scene_comparison.json').open('x') as stream:json.dump(report,stream,indent=2);stream.write('\n')
assert report['passed'],report
print(json.dumps(report,indent=2))
