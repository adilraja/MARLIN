"""Actor-only visibility intervention on private copies, never the live stage."""
import asyncio
import json
import re
import shutil
import tempfile
from pathlib import Path
from pxr import Usd, UsdGeom
from .actor import ACTOR

_busy = False


def hide_only_actor(stage):
    """Author exactly one property; verify roundtrip leaves all other data intact."""
    prim = stage.GetPrimAtPath(ACTOR)
    if not prim or UsdGeom.Imageable(prim).ComputeVisibility() == "invisible":
        raise ValueError("Expected a visible GAMA fixture actor")
    layer = stage.GetRootLayer()
    before = layer.ExportToString()
    attribute = UsdGeom.Imageable(prim).GetVisibilityAttr()
    existed = bool(layer.GetPropertyAtPath(attribute.GetPath()))
    old = attribute.Get()
    with Usd.EditContext(stage, layer):
        attribute.Set(UsdGeom.Tokens.invisible)
        hidden = layer.ExportToString()
        if existed:
            attribute.Set(old)
        else:
            prim.RemoveProperty("visibility")
    if layer.ExportToString() != before:
        raise ValueError("Visibility intervention changed unrelated USD data")
    layer.ImportFromString(hidden)


async def run(capture_id):
    global _busy
    if _busy:
        return {"ok":False,"error":"GAMA counterfactual already running"}
    _busy = True
    try:
        return await _run(capture_id)
    finally:
        _busy = False


async def _run(capture_id):
    from cris.madil.render_service import hidef_marine as marine
    from .marine_check import audit
    if not isinstance(capture_id,str) or not re.fullmatch(r"oblique_[a-z0-9_]+",capture_id):
        raise ValueError("Use a saved HiDef capture ID")
    source = marine.ROOT / capture_id
    metadata = json.loads((source/"metadata.json").read_text())
    sidecar = json.loads((source/"gama_state.json").read_text())
    if metadata["config"]["downsample"] != 4 or sidecar["actor_path"] != ACTOR:
        raise ValueError("Only the saved preview GAMA fixture is supported")
    hashes = {name:marine.digest(source/name) for name in ("scene.usdc","rgb.png","metadata.json","gama_state.json")}
    if any(hashes[k] != v for k,v in sidecar["files_sha256"].items()):
        raise ValueError("Original capture hash mismatch")
    if not marine.same_settings(marine.settings_record(), metadata["renderer_settings"]):
        raise ValueError("Current renderer settings differ from saved capture; no settings were changed")
    marine.gpu_preflight()
    (source.parent.parent/"gama").mkdir(parents=True,exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="counterfactual_",dir=source.parent.parent/"gama"))
    report = {"source_capture":capture_id,"source_hashes":hashes,"actor_path":ACTOR,
              "sequence":["on","off","off","on"],"captures":[],
              "before":await audit(),"status":"running"}
    try:
        inputs = {}
        for mode in ("on","off"):
            derived = Path(tempfile.mkdtemp(prefix="oblique_gama_"+mode+"_",dir=marine.ROOT))
            if mode == "on":
                shutil.copyfile(source/"scene.usdc",derived/"scene.usdc")
            else:
                stage = marine.open_snapshot(source/"scene.usdc")
                hide_only_actor(stage)
                stage.GetRootLayer().Export(str(derived/"scene.usdc"))
                stage = None
            settings = dict(metadata, scene_sha256=marine.digest(derived/"scene.usdc"),
                            test_kind="gama_counterfactual_input_not_a_render",source_capture=capture_id,
                            actor_visibility=mode,rendered_image=None,output_sha256={})
            (derived/"metadata.json").write_text(json.dumps(settings,indent=2)+"\n")
            inputs[mode] = derived.name
        report["derived_inputs"] = inputs
        report["only_intervention"] = ACTOR+".visibility=invisible in off source"
        for mode in report["sequence"]:
            result = await marine.run_capture(replay_id=inputs[mode])
            report["captures"].append({"mode":mode,**result})
            if not result.get("ok"):
                raise RuntimeError(result.get("error","Capture failed"))
        report["status"] = "rendered_pending_pixel_analysis"
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = str(exc)
    finally:
        # Capture restores the gate synchronously; allow live update callbacks
        # to run before testing whether ocean/swimming actually resumed.
        await asyncio.sleep(2)
        report["after"] = await audit()
        report["source_unchanged"] = all(marine.digest(source/name)==value for name,value in hashes.items())
        (directory/"render_report.json").write_text(json.dumps(report,indent=2)+"\n")
    return {"ok":report["status"]!="failed", "directory":str(directory),
            "status":report["status"],"error":report.get("error")}
