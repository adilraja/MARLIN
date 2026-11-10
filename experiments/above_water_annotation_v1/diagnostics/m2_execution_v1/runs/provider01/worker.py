"""Provider import and owned empty-stage lifecycle only; zero capture attempts."""
import asyncio, json, os, traceback
from pathlib import Path
import carb.settings
import omni.kit.app
import omni.usd
OUT=Path(os.environ["ANNOTATION_EXECUTION_OUTPUT"])
def save(n,d): (OUT/n).write_text(json.dumps(d,indent=2,default=str)+"\n")
async def main():
 app=omni.kit.app.get_app(); result=dict(passed=False,captures=0)
 try:
  while not app.is_app_ready(): await app.next_update_async()
  save("ready.json",dict(app_ready=True))
  import omni.replicator.core as rep
  import omni.syntheticdata
  from pxr import Semantics
  result["replicator_file"]=rep.__file__
  result["annotator_registry_methods"]=[x for x in dir(rep.AnnotatorRegistry) if not x.startswith("__")]
  result["semantics_api"]=[x for x in dir(Semantics) if "API" in x]
  m=app.get_extension_manager()
  result["enabled_packages"]=[dict(id=e["id"],package_id=m.get_extension_dict(e["id"]).get("package",{}).get("id")) for e in m.get_extensions() if e["enabled"]]
  result["enabled_inventory"]=[m.get_extension_dict(e["id"]) for e in m.get_extensions() if e["enabled"]]
  assert not carb.settings.get_settings().get("/app/extensions/registryEnabled")
  ctx=omni.usd.get_context(); assert ctx.get_stage() is None
  await ctx.new_stage_async()
  for _ in range(4): await app.next_update_async()
  await ctx.close_stage_async()
  result["stage_closed"]=ctx.get_stage() is None
  result["passed"]=result["stage_closed"]
 except BaseException: result["error"]=traceback.format_exc(); print(result["error"],flush=True)
 finally:
  save("result.json",result);app.post_quit(0 if result["passed"] else 1)
asyncio.ensure_future(main())
