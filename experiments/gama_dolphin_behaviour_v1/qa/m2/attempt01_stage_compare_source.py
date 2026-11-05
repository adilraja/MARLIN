"""Compare frozen stages after the permitted ocean/chase reconstruction."""
import hashlib
import importlib
import json
from pathlib import Path
import sys
import types
from pxr import Usd

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[3]
package=types.ModuleType('_m2_stage_compare')
package.__path__=[str(REPO/'source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge')]
sys.modules[package.__name__]=package
actor=importlib.import_module(package.__name__+'.actor_v3')


def record(path):
    s=Usd.Stage.Open(str(path));records={}
    for p in s.Traverse():
        values={'type':p.GetTypeName(),'active':p.IsActive()}
        for a in p.GetAttributes():
            times=a.GetTimeSamples()
            values['attr:'+a.GetName()]=[actor._fingerprint_value(a.Get()),[(t,actor._fingerprint_value(a.Get(t))) for t in times]]
        for r in p.GetRelationships():values['rel:'+r.GetName()]=[str(t) for t in r.GetTargets()]
        records[str(p.GetPath())]=values
    return records


if __name__=='__main__':
    before=record(ROOT/'live_before/scene.usdc');after=record(ROOT/'live_final/scene.usdc')
    missing=sorted(before.keys()-after.keys());extra=sorted(after.keys()-before.keys());differences=[]
    for path in sorted(before.keys()&after.keys()):
        for key in sorted(before[path].keys()|after[path].keys()):
            if before[path].get(key)!=after[path].get(key):differences.append(dict(path=path,property=key))
    allowed={('/World/Ocean','attr:points'),('/World/Ocean','attr:extent')}
    unexpected=[d for d in differences if (d['path'],d['property']) not in allowed]
    result=dict(passed=not missing and not extra and not unexpected,prims_before=len(before),prims_after=len(after),missing=missing,extra=extra,differences=differences,unexpected=unexpected,
                allowed_difference='Only regenerated ocean points/extent after restarting its controller. Camera/settings separately verified.')
    print(json.dumps(result,indent=2))
    sys.exit(0 if result['passed'] else 1)
