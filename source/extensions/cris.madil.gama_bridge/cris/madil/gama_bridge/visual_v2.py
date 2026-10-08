"""Temporary owned close-up of the actual live porpoise, using MARLIN capture."""

RTX_EXPOSURE_ATTRIBUTES = frozenset(("exposure:fStop", "exposure:responsivity", "exposure:time"))


def _is_diagnostic_camera_over(spec):
    """Recognize only RTX's bounded scalar exposure opinions on our camera."""
    import math
    from pxr import Sdf

    if (spec is None or spec.specifier != Sdf.SpecifierOver
            or set(spec.ListInfoKeys()) != {"specifier"}
            or spec.nameChildren or spec.variantSets
            or not set(spec.properties.keys()).issubset(RTX_EXPOSURE_ATTRIBUTES)):
        return False
    for prop in spec.properties.values():
        if not isinstance(prop, Sdf.AttributeSpec):
            return False
        fields = set(prop.ListInfoKeys())
        if "default" not in fields or not fields.issubset({"typeName", "variability", "custom", "default"}):
            return False
        if type(prop.default) not in (int, float) or not math.isfinite(prop.default):
            return False
        if prop.layer.ListTimeSamplesForPath(prop.path):
            return False
    return True


def _remove_new_diagnostic_camera_overs(root_path, external_cameras):
    """Remove newly-created RTX exposure overrides at our fixed camera path."""
    removed = []
    for external_layer, existed_before in external_cameras:
        if existed_before:
            continue
        spec = external_layer.GetPrimAtPath(root_path + "/DiagnosticCamera")
        if _is_diagnostic_camera_over(spec):
            evidence = {"layer": external_layer.identifier,
                        "path": str(spec.path), "fields": list(spec.ListInfoKeys()),
                        "exposure_attributes": {prop.name: prop.default for prop in spec.properties.values()}}
            del external_layer.GetPrimAtPath(root_path).nameChildren["DiagnosticCamera"]
            removed.append(evidence)
    return removed


def _is_empty_over(spec):
    """Only an opinion-free prim placeholder qualifies for scoped removal."""
    from pxr import Sdf

    return (spec is not None and spec.specifier == Sdf.SpecifierOver
            and set(spec.ListInfoKeys()) == {"specifier"}
            and not spec.nameChildren and not spec.properties and not spec.variantSets)


def _remove_new_empty_root_overs(root_path, external_roots):
    """Remove only new empty placeholders at this transaction's private root."""
    removed = []
    for external_layer, existed_before in external_roots:
        if existed_before:
            continue
        spec = external_layer.GetPrimAtPath(root_path)
        if _is_empty_over(spec):
            # The owned integration root is a direct child of the pseudo-root.
            # Never prune ancestors or any authored child/property/opinion.
            if str(spec.path.GetParentPath()) != "/":
                continue
            del external_layer.rootPrims[spec.name]
            removed.append(external_layer.identifier)
    return removed


async def capture(owner, token):
    """Render a diagnostic frame and restore camera, layer, and controller gate."""
    import asyncio
    import omni.kit.app
    import omni.usd
    from pxr import Gf, Usd, UsdGeom, UsdLux
    from cris.madil.render_service import capture_state
    from cris.madil.render_service.camera import _active_viewport, capture_active_viewport
    from cris.madil.render_service.capture_projection import record_projection

    stage = omni.usd.get_context().get_stage()
    owner._guard(stage, token, capture_state.paused)
    state = owner.buffer.latest
    if state is None:
        raise ValueError("Apply a GAMA step before diagnostic capture")
    viewport = _active_viewport()
    if viewport is None:
        raise ValueError("No active MARLIN viewport is available")
    resolution = tuple(viewport.resolution)
    width, height = resolution
    if width <= 0 or height <= 0:
        raise ValueError("A positive viewport capture resolution is required")

    pose = owner.status()["world_pose"]
    target = Gf.Vec3d(*pose["position_scene_units"])
    forward = Gf.Vec3d(*pose["forward_y_up"])
    side = Gf.Vec3d(forward[2], 0, -forward[0])
    eye = target + (3.0 * side - .8 * forward) / owner.units
    # View from below the mean plane so the ocean surface does not hide the
    # subject. This is a close-up diagnostic, not a survey acquisition camera.
    eye[1] = min(-.2 / owner.units, target[1] + .4 / owner.units)
    camera_path = owner.root_path + "/DiagnosticCamera"
    light_path = owner.root_path + "/DiagnosticLight"
    layer = owner.layer
    # Viewport camera management can create an otherwise empty ancestor over
    # in the active edit layer. Retain every pre-existing external root opinion.
    external_roots = [(external, external.GetPrimAtPath(owner.root_path) is not None)
                      for external in stage.GetLayerStack() if external != layer]
    external_cameras = [(external, external.GetPrimAtPath(camera_path) is not None)
                        for external, _ in external_roots]
    original_layer = layer.ExportToString()
    original_camera = str(viewport.camera_path)
    original_paused = capture_state.paused
    capture_state.paused = True
    result = None
    wait_for_frames = getattr(viewport, "wait_for_rendered_frames", None)
    try:
        with Usd.EditContext(stage, layer):
            camera = UsdGeom.Camera.Define(stage, camera_path)
            camera.GetFocalLengthAttr().Set(35.0)
            camera.GetHorizontalApertureAttr().Set(20.955)
            camera.GetVerticalApertureAttr().Set(20.955 * height / width)
            camera.GetClippingRangeAttr().Set(Gf.Vec2f(.01 / owner.units, 100 / owner.units))
            view = Gf.Matrix4d(1.0)
            view.SetLookAt(eye, target, Gf.Vec3d(0, 1, 0))
            UsdGeom.Xformable(camera.GetPrim()).AddTransformOp().Set(view.GetInverse())
            light = UsdLux.SphereLight.Define(stage, light_path)
            light.CreateIntensityAttr(1500.0)
            light.CreateNormalizeAttr(True)
            light.CreateRadiusAttr(.1 / owner.units)
            UsdGeom.XformCommonAPI(light.GetPrim()).SetTranslate(eye)
        viewport.camera_path = camera_path
        # RTX applies camera/render-product selection asynchronously. Match the
        # existing marine capture's 90 + 30 update settling interval before
        # checking the product, rather than relying on the Python camera path.
        for _ in range(120):
            await omni.kit.app.get_app().next_update_async()
        if wait_for_frames is not None:
            await asyncio.wait_for(wait_for_frames(3), timeout=30)
        if str(viewport.camera_path) != camera_path or tuple(viewport.resolution) != resolution:
            raise ValueError("Diagnostic viewport camera/resolution changed before capture")
        projection_before = record_projection(stage, viewport)
        # Discard the preceding camera frame before retaining the actual image.
        for _ in range(2):
            result = await capture_active_viewport()
            if not result.get("ok"):
                raise ValueError(result.get("error", "Viewport capture failed"))
        if omni.usd.get_context().get_stage() != stage:
            raise ValueError("Active stage changed during diagnostic capture")
        if str(viewport.camera_path) != camera_path or tuple(viewport.resolution) != resolution:
            raise ValueError("Diagnostic viewport camera/resolution changed during capture")
        projection_after = record_projection(stage, viewport)
    finally:
        try:
            viewport.camera_path = original_camera
            # Let camera management finish its restored-camera writes before
            # considering newly-created empty ancestor placeholders for removal.
            for _ in range(30):
                await omni.kit.app.get_app().next_update_async()
            if wait_for_frames is not None:
                await asyncio.wait_for(wait_for_frames(3), timeout=30)
        finally:
            try:
                if not layer.ImportFromString(original_layer):
                    raise RuntimeError("Could not restore the owned diagnostic layer")
            finally:
                try:
                    removed_external_cameras = _remove_new_diagnostic_camera_overs(owner.root_path, external_cameras)
                    removed_external_overs = _remove_new_empty_root_overs(owner.root_path, external_roots)
                finally:
                    capture_state.paused = original_paused

    return {"ok": True, "file_path": result["file_path"],
            "diagnostic_label": "Actual live static pose proxy; temporary below-surface camera and diagnostic light",
            "gama_state": state, "world_pose": pose,
            "camera_position_scene_units": list(eye),
            "camera_target_scene_units": list(target),
            "projection_before_capture": projection_before,
            "projection_after_capture": projection_after,
            "render_product_camera_verified": True,
            "camera_settle_app_updates": 120,
            "rendered_frame_wait_available": wait_for_frames is not None,
            "external_empty_root_overs_removed": removed_external_overs,
            "external_diagnostic_camera_overs_removed": removed_external_cameras,
            "previous_camera_restored": str(viewport.camera_path) == original_camera,
            "owned_layer_restored": layer.ExportToString() == original_layer,
            "controller_gate_restored": capture_state.paused == original_paused}
