"""Optional integration diagnostics; reuse MARLIN capture, never set its optics."""
import hashlib
import json
from pathlib import Path
from pxr import Gf, Usd, UsdGeom
from .actor import ROOT, ACTOR


async def audit():
    import omni.usd
    from cris.madil.render_service.hidef_marine import settings_record
    from cris.madil.render_service.scene_diagnostics import inspect_scene
    from cris.madil.render_service.cetacean_gallery import gallery_swimming_status
    from cris.madil.render_service.ocean import ocean_animation_status
    stage = omni.usd.get_context().get_stage()
    if stage is None:
        raise ValueError("No live stage")
    # Attribute records are read-only, exclude time-varying ocean mesh/animal poses.
    stable = {}
    for path in ("/World/Cameras", "/World/Looks", "/World/Environment", "/Environment"):
        root = stage.GetPrimAtPath(path)
        if root:
            stable[path] = {str(p.GetPath()): {a.GetName(): str(a.Get()) for a in p.GetAttributes()}
                            for p in Usd.PrimRange(root)}
    return {"ok": True, "inspection": await inspect_scene(),
            "swimming": await gallery_swimming_status(), "ocean": await ocean_animation_status(),
            "renderer_settings": settings_record(), "stable_scene_attributes": stable}


async def capture(owner, token):
    import omni.usd
    from cris.madil.render_service import capture_state
    from cris.madil.render_service.hidef_marine import MarineRequest, run_capture
    owner._guard(omni.usd.get_context().get_stage(), token, capture_state.paused)
    state = owner.buffer.latest
    if state is None:
        raise ValueError("Apply a GAMA step before capture")
    pose = owner.status()["world_pose"]
    result = await run_capture(data=MarineRequest(roll_deg=7.7675, downsample=4))
    if not result.get("ok"):
        return result
    directory = Path(result["directory"])
    frozen = Usd.Stage.Open(str(directory / "scene.usdc"))
    prim = frozen.GetPrimAtPath(ACTOR)
    if not prim:
        raise ValueError("Capture snapshot omitted the GAMA actor")
    root = frozen.GetPrimAtPath(ROOT)
    if (root.GetCustomDataByKey("marlin:time_s") != state["time_s"] or
            root.GetCustomDataByKey("marlin:seed") != str(state["seed"])):
        raise ValueError("Frozen GAMA timestamp/seed differs from requested state")
    matrix = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    frozen_pose = {"position_scene_units": list(matrix.ExtractTranslation()),
                   "forward_y_up": list(matrix.TransformDir(Gf.Vec3d(0, 0, 1)))}
    for key in pose:
        if any(abs(a-b) > 1e-5 for a,b in zip(pose[key], frozen_pose[key])):
            raise ValueError("Captured animal pose differs from GAMA snapshot")
    files = {name: hashlib.sha256((directory/name).read_bytes()).hexdigest()
             for name in ("scene.usdc", "rgb.png", "metadata.json")}
    record = {"schema_version": "1.0", "gama_state": state, "actor_path": ACTOR,
              "frozen_pose": frozen_pose, "frozen_state_verified": True,
              "camera_metadata": "metadata.json", "files_sha256": files,
              "biological_calibration": False, "image_visibility_verified": False,
              "note": "Preview HiDef geometry/GSD remain authored by MARLIN; pose match does not prove visibility."}
    sidecar = directory / "gama_state.json"
    sidecar.write_text(json.dumps(record, indent=2) + "\n")
    return {**result, "gama_metadata": str(sidecar), "frozen_state_verified": True}
