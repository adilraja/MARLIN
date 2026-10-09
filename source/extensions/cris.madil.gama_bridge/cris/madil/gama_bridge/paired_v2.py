"""One frozen biological/environmental scene, several Pilot-style GSD cameras."""
import asyncio
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import tempfile

from .exchange_v2 import validate_step
from .paired_state_v2 import resolved_record, camera_condition, source_content_hash

GSDS = (.5, 1., 2., 3., 4.)
CAMERA = "/MarlinGamaPairCamera"
RESOLUTION = (1024, 768)
REPO = Path(__file__).resolve().parents[6]
_recovery_caches = []


def validate_conditions(orders, delay_s):
    if not isinstance(orders, list) or not 1 <= len(orders) <= 3:
        raise ValueError("Expected one to three complete five-GSD orders")
    for order in orders:
        if (not isinstance(order, list) or len(order) != 5 or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in order) or
                sorted(order) != list(GSDS)):
            raise ValueError("Every order must contain exactly 0.5, 1, 2, 3 and 4 cm/px")
    if type(delay_s) not in (int, float) or not math.isfinite(delay_s) or not 0 <= delay_s <= 5:
        raise ValueError("delay_s must be finite and between zero and five seconds")
    return deepcopy(orders), float(delay_s)


def _write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_pilot_camera(condition, gsd, anchor, plane):
    """Check resolved optics/pose rather than trusting the requested GSD label."""
    c = condition["camera_condition"]
    unit = c["meters_per_scene_unit"]
    matrix = c["composed_camera_matrix"]
    expected = [[1, 0, 0, 0], [0, 0, -1, 0], [0, 1, 0, 0],
        [anchor[0] / unit, (plane + gsd * 100) / unit, anchor[1] / unit, 1]]
    if (c["projection"] != "perspective" or c["resolution_px"] != list(RESOLUTION) or
            not math.isclose(unit, .01, abs_tol=1e-12) or
            any(not math.isclose(matrix[i][j], expected[i][j], rel_tol=1e-10, abs_tol=1e-8)
                for i in range(4) for j in range(4))):
        raise ValueError("Composed camera differs from the declared Pilot nadir pose")
    for key, value in (("focal_length", 50 / (100 * unit)),
            ("horizontal_aperture", 1024 * 5e-5 / unit),
            ("vertical_aperture", 768 * 5e-5 / unit),
            ("horizontal_aperture_offset", 0), ("vertical_aperture_offset", 0)):
        if not math.isclose(c[key], value, rel_tol=1e-6, abs_tol=1e-8):
            raise ValueError("Resolved camera optics differ from the declared Pilot geometry")
    separation = matrix[3][1] * unit - plane
    fx = c["focal_length"] / c["horizontal_aperture"] * RESOLUTION[0]
    fy = c["focal_length"] / c["vertical_aperture"] * RESOLUTION[1]
    measured = [100 * separation / f for f in (fx, fy)]
    if any(not math.isclose(value, gsd, rel_tol=1e-6, abs_tol=1e-8) for value in measured):
        raise ValueError("Actual reference-plane GSD differs from the declared condition")
    return {"passed": True, "measured_reference_gsd_xy_cm_px": measured,
        "camera_separation_from_root_plane_m": separation,
        "reference_footprint_wh_m": [RESOLUTION[0] * measured[0] / 100, RESOLUTION[1] * measured[1] / 100],
        "note": "Direct pinhole reference-plane geometry; underwater refraction remains uncalibrated"}


class KitRuntime:
    """Small dependency boundary for transaction failure tests; one Kit renderer."""
    def __init__(self):
        import carb.settings
        import omni.timeline
        import omni.usd
        from omni.kit.viewport.utility import get_active_viewport
        from cris.madil.render_service import calibration_capture, capture_state, hidef_marine
        from PIL import Image, ImageChops, ImageStat
        self.context = omni.usd.get_context()
        self.viewport = get_active_viewport()
        self.timeline = omni.timeline.get_timeline_interface()
        self.settings = carb.settings.get_settings()
        self.lock, self.gate = calibration_capture, capture_state
        self.marine = hidef_marine
        self.output_root = REPO / "artifacts/gama_pairs"
        self.Image, self.ImageChops, self.ImageStat = Image, ImageChops, ImageStat

    def stage(self):
        return self.context.get_stage()

    def selection(self):
        return self.context.get_selection().get_selected_prim_paths()

    def select(self, paths):
        self.context.get_selection().set_selected_prim_paths(paths, False)

    def renderer(self):
        return self.marine.settings_record()

    def restore_renderer(self, values):
        self.marine.restore_settings(values)

    def display(self):
        return self.settings.get('/persistent/app/viewport/displayOptions')

    def set_display(self, value):
        self.marine.restore_settings({'/persistent/app/viewport/displayOptions': value})

    def ocean_clock(self):
        from cris.madil.render_service import ocean
        state = ocean._ocean_animation_state
        if state is None:
            return {"running": False}
        keys = ("ocean_path", "size", "resolution", "speed", "choppiness", "target_fps", "elapsed", "accumulator", "waves", "position")
        return {"running": ocean._ocean_animation_subscription is not None,
                **{key: deepcopy(state[key]) for key in keys if key in state}}

    def freeze(self, stage, seconds):
        from pxr import Usd
        return self.marine.freeze_stage(stage, Usd.TimeCode(seconds * stage.GetTimeCodesPerSecond()))

    def retain(self, stage):
        from pxr import Usd
        cache = Usd.StageCache()
        cache.Insert(stage)
        return cache

    def dependencies(self, stage):
        return self.marine.asset_dependencies(stage)

    def preflight(self):
        return self.marine.gpu_preflight()

    async def attach(self, stage):
        ok, error = await self.context.attach_stage_async(stage)
        if not ok:
            raise RuntimeError("Could not attach stage: " + str(error))

    async def update(self):
        import omni.kit.app
        await omni.kit.app.get_app().next_update_async()

    async def sleep(self, seconds):
        await asyncio.sleep(seconds)

    def camera(self, stage, gsd, anchor, plane):
        from pxr import Gf, Sdf
        from cris.madil.render_service.calibration_geometry import CalibrationConfig, build_camera
        config = CalibrationConfig(meters_per_scene_unit=.01, image_width_px=1024,
            image_height_px=768, focal_length_mm=50, pixel_pitch_um=5,
            height_above_target_m=gsd * 100, target_plane_y_m=plane,
            target_width_m=2, target_height_m=1)
        camera = build_camera(stage, config, CAMERA, (anchor[0], 0, anchor[1]))
        camera.CreateClippingRangeAttr(Gf.Vec2f(1, 100000))
        exposure = json.loads((REPO / "experiments/gsd_pilot_v1/environment.json").read_text())["camera_exposure_attributes"]
        for name, value in exposure.items():
            camera.GetPrim().CreateAttribute(name, Sdf.ValueTypeNames.Float).Set(value)

    def projection(self, stage):
        from cris.madil.render_service.capture_projection import record_projection
        return record_projection(stage, self.viewport)

    async def capture(self, target):
        from omni.kit.viewport.utility import capture_viewport_to_file
        if target.exists():
            raise ValueError("Capture probe output must be a fresh file")
        # Same generic viewport backend as Pilot, with a unique file rather
        # than /tmp/marlin_viewport.png. Kit can signal rendered-frame
        # completion before the asynchronous PNG writer has finished.
        capture = capture_viewport_to_file(self.viewport, file_path=str(target))
        await capture.wait_for_result(completion_frames=5)
        for _ in range(300):
            try:
                with self.Image.open(target) as image:
                    image.load()
                    if image.size != RESOLUTION:
                        raise ValueError("Fresh capture has the wrong image dimensions")
                return target
            except (OSError, SyntaxError):
                await self.sleep(.1)
        raise RuntimeError("Unique capture PNG was not completely readable within 30 seconds")

    def difference(self, previous, current):
        with self.Image.open(previous) as a, self.Image.open(current) as b:
            if a.size != RESOLUTION or b.size != RESOLUTION:
                raise ValueError("Captured image is not 1024 by 768")
            diff = self.ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
            return sum(self.ImageStat.Stat(diff).mean) / 3


async def run(owner, token, orders, delay_s, runtime=None):
    """Hold one ownership/scene transaction through all conditions and delays.

    Runtime injection exists for offline failure tests, never as an HTTP option.
    The endpoint accepts only a token, bounded complete orders and bounded delay.
    """
    orders, delay_s = validate_conditions(orders, delay_s)
    rt = runtime or KitRuntime()
    if rt.lock._busy or rt.gate.paused:
        raise ValueError("Another capture transaction is active")
    original_stage = rt.stage()
    owner._guard(original_stage, token, rt.gate.paused)
    if not math.isclose(owner.units, .01, rel_tol=0, abs_tol=1e-12):
        raise ValueError("Pilot paired capture requires the declared centimetre stage")
    if original_stage.GetPrimAtPath(CAMERA) or any(layer.GetPrimAtPath(CAMERA) for layer in original_stage.GetLayerStack()):
        raise ValueError("The reserved paired-capture camera path already exists")
    state = validate_step(owner.buffer.latest)
    if len(state["agents"]) != 1 or rt.viewport is None or not rt.viewport.updates_enabled:
        raise ValueError("One applied GAMA animal and an updating viewport are required")
    source_pose = deepcopy(owner.status()["world_pose"])
    if source_pose is None:
        raise ValueError("Apply a GAMA step before paired capture")
    agent = state["agents"][0]
    anchor, plane = list(agent["horizontal_position_m"]), -agent["depth_m"]
    saved = {"camera": str(rt.viewport.camera_path), "resolution": tuple(rt.viewport.resolution),
        "fill_frame": rt.viewport.fill_frame, "selection": rt.selection(), "renderer": rt.renderer(),
        "display": rt.display(), "seconds": rt.timeline.get_current_time(),
        "playing": rt.timeline.is_playing(), "paused": rt.gate.paused, "busy": rt.lock._busy}
    gpu = rt.preflight()
    retained = rt.retain(original_stage)
    rt.output_root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="paired_", dir=rt.output_root))
    report = {"milestone": 6, "passed": False, "status": "running", "source_state": state,
        "source_world_pose": source_pose, "orders": orders, "artificial_delay_s": delay_s,
        "delay_policy": "Applied before every capture in second and later orders",
        "captures": [], "state_checks": [], "gpu_preflight": gpu,
        "protocol": {"image_resolution": list(RESOLUTION), "focal_length_mm": 50,
            "pixel_pitch_um": 5, "projection": "nadir ideal perspective", "camera_anchor_xz_m": anchor,
            "reference_plane_y_m": plane, "only_camera_y_varies": True,
            "footprint_policy": "Height and footprint vary with GSD, as in Pilot v1",
            "environment": "Frozen current presentation environment; Pilot camera geometry, not a reproduction of Pilot's flat-water/diffuse environment",
            "biological_suitability": "provisional engineering proxy", "rgb_bitwise_reproducibility_claimed": False}}
    failure = None
    restored = False
    frozen = None
    clock = None
    source_hash = None
    rt.lock._busy = True
    rt.gate.paused = True
    try:
        rt.timeline.pause()
        source_hash = source_content_hash(original_stage)
        report["original_source_content_hash"] = source_hash
        # No await before flattening and sampling the entire composed scene.
        clock = {"source_timeline_seconds": saved["seconds"],
            "source_time_code": saved["seconds"] * original_stage.GetTimeCodesPerSecond(),
            "ocean": rt.ocean_clock(), "clocks_synchronized_to_gama": False}
        frozen, sampled = rt.freeze(original_stage, saved["seconds"])
        if frozen.GetPrimAtPath('/Render'):
            frozen.RemovePrim('/Render')
        retained.Insert(frozen)
        dependencies = rt.dependencies(frozen)
        identity = resolved_record(frozen, state, saved["renderer"], dependencies, clock)
        expected_hash = identity["resolved_scene_state_hash"]
        report.update(resolved_scene_state_hash=expected_hash, environment_clock=clock,
            frozen_sampled_attributes=sampled, pose_mapping="static_pose_proxy_v1",
            animation_phase="not_applicable_static_pose", dependencies=dependencies)
        _write(directory / "resolved_state.json", identity)
        frozen.GetRootLayer().Export(str(directory / "source_scene.usdc"))
        report["source_scene_sha256"] = _digest(directory / "source_scene.usdc")

        def check(label):
            if rt.stage() != frozen or not rt.gate.paused or not rt.lock._busy or rt.timeline.is_playing():
                raise ValueError("Frozen capture transaction context/gates changed")
            if rt.timeline.get_current_time() != saved["seconds"] or rt.ocean_clock() != clock["ocean"]:
                report["clock_failure"] = {"label": label,
                    "expected_timeline_seconds": saved["seconds"],
                    "actual_timeline_seconds": rt.timeline.get_current_time(),
                    "expected_ocean": clock["ocean"], "actual_ocean": rt.ocean_clock()}
                raise ValueError("Biological or environmental time advanced during capture")
            if owner.buffer.latest != state:
                raise ValueError("Owned GAMA source state changed during capture")
            current = resolved_record(frozen, state, rt.renderer(), rt.dependencies(frozen), clock)
            actual_hash = current["resolved_scene_state_hash"]
            report["state_checks"].append({"label": label, "resolved_scene_state_hash": actual_hash,
                "matches": actual_hash == expected_hash})
            if actual_hash != expected_hash:
                raise ValueError("Resolved biological/environmental state changed")
            return actual_hash

        await rt.attach(frozen)
        rt.timeline.pause()
        rt.timeline.set_current_time(saved["seconds"])
        rt.restore_renderer(saved["renderer"])
        rt.select([])
        rt.set_display(0)
        # Timeline setters are committed by Kit's next update after attaching
        # a stage. Keep both gates closed while that context transition settles.
        for _ in range(3):
            await rt.update()
        check("after_attach")
        for order_index, order in enumerate(orders):
            for condition_index, gsd in enumerate(order):
                label = f"order_{order_index}_condition_{condition_index}"
                folder = directory / label
                folder.mkdir()
                check(label + "_before_delay")
                delay = delay_s if order_index else 0
                if delay:
                    await rt.sleep(delay)
                check(label + "_after_delay")
                rt.camera(frozen, gsd, anchor, plane)
                rt.viewport.camera_path = CAMERA
                rt.viewport.fill_frame = False
                rt.viewport.resolution = RESOLUTION
                for _ in range(120):
                    await rt.update()
                rt.viewport.fill_frame = False
                rt.viewport.resolution = RESOLUTION
                check(label + "_after_warmup")
                projection_before = rt.projection(frozen)
                condition = camera_condition(frozen, CAMERA, gsd, [anchor[0], plane, anchor[1]], plane, RESOLUTION)
                camera_validation = verify_pilot_camera(condition, gsd, anchor, plane)
                probes, previous, accepted = [], None, None
                for attempt in range(1, 8):
                    check(label + f"_probe_{attempt}_before")
                    target = folder / f"probe_{attempt:02d}.png"
                    source = await rt.capture(target)
                    if Path(source) != target:
                        shutil.copyfile(source, target)
                    with target.open('rb') as stream:
                        header = stream.read(24)
                    if header[:8] != b'\x89PNG\r\n\x1a\n' or struct.unpack('>II', header[16:24]) != RESOLUTION:
                        raise ValueError("Capture dimensions do not match the protocol")
                    check(label + f"_probe_{attempt}_after")
                    difference = None if previous is None else rt.difference(previous, target)
                    probes.append({"file": str(target.relative_to(directory)), "sha256": _digest(target),
                        "mean_absolute_rgb_difference_from_previous": difference})
                    if attempt >= 3 and difference is not None and difference < 1:
                        accepted = target
                        break
                    previous = target
                    await rt.sleep(2)
                if accepted is None:
                    raise ValueError("RGB did not settle within seven probes; all probes retained")
                image = folder / "rgb.png"
                shutil.copyfile(accepted, image)
                projection_after = rt.projection(frozen)
                after_condition = camera_condition(frozen, CAMERA, gsd, [anchor[0], plane, anchor[1]], plane, RESOLUTION)
                if after_condition != condition or str(rt.viewport.camera_path) != CAMERA or tuple(rt.viewport.resolution) != RESOLUTION:
                    raise ValueError("Camera condition changed during capture")
                final_hash = check(label + "_complete")
                item = {"order_index": order_index, "condition_index": condition_index,
                    "gsd_cm_px": gsd, "artificial_delay_s": delay,
                    "resolved_scene_state_hash": final_hash, "camera_condition": condition,
                    "camera_geometry_validation": camera_validation,
                    "projection_before_capture": projection_before, "projection_after_capture": projection_after,
                    "render_product_camera_verified": True, "rgb_file": str(image.relative_to(directory)),
                    "rgb_sha256": _digest(image), "settling_probes": probes,
                    "settling_threshold_mean_absolute_rgb": 1.,
                    "settling_note": "Consecutive-frame settling only; not proof of RTX sample count or bitwise identity"}
                _write(folder / "capture.json", item)
                report["captures"].append(item)
                _write(directory / "manifest.json", report)
        report["all_state_hashes_equal"] = all(x["matches"] for x in report["state_checks"])
        report["status"] = "captured_pending_restoration"
    except BaseException as error:
        failure = error
        report.update(status="failed", error=str(error) or type(error).__name__)
    finally:
        errors = []
        try:
            # This camera already exists on the frozen copy. Select it before
            # reattaching live USD so Kit never needs to create the pair camera
            # on the original scene during viewport restoration.
            rt.viewport.camera_path = saved["camera"]
            await rt.attach(original_stage)
            restored = rt.stage() == original_stage
            if not restored:
                raise RuntimeError("Original stage was not restored")
        except BaseException as error:
            errors.append("stage: " + (str(error) or type(error).__name__))
        for name, action in (
            ("renderer", lambda: rt.restore_renderer(saved["renderer"])),
            ("camera", lambda: setattr(rt.viewport, "camera_path", saved["camera"])),
            ("resolution", lambda: setattr(rt.viewport, "resolution", saved["resolution"])),
            ("fill_frame", lambda: setattr(rt.viewport, "fill_frame", saved["fill_frame"])),
            ("selection", lambda: rt.select(saved["selection"])),
            ("display", lambda: rt.set_display(saved["display"])),
            ("timeline_time", lambda: rt.timeline.set_current_time(saved["seconds"]))):
            try:
                action()
            except BaseException as error:
                errors.append(name + ": " + (str(error) or type(error).__name__))
        if restored:
            try:
                for _ in range(30):
                    await rt.update()
                from .visual_v2 import _is_diagnostic_camera_over
                removed = []
                for layer in original_stage.GetLayerStack():
                    spec = layer.GetPrimAtPath(CAMERA)
                    if spec is not None:
                        if not _is_diagnostic_camera_over(spec):
                            raise ValueError("Foreign authored content appeared at the reserved pair-camera path")
                        del layer.rootPrims[spec.name]
                        removed.append(layer.identifier)
                report["new_pair_camera_overs_removed"] = removed
                report["restored_source_content_hash"] = source_content_hash(original_stage)
                if source_hash is not None and report["restored_source_content_hash"] != source_hash:
                    raise ValueError("Original non-camera scene content changed during paired capture")
                owner._guard(original_stage, token, False)
                if owner.status()["world_pose"] != source_pose or owner.buffer.latest != state:
                    raise ValueError("Original GAMA actor changed during paired capture")
                if clock is not None and rt.ocean_clock() != clock["ocean"]:
                    raise ValueError("Original ocean clock advanced during paired capture")
                if saved["playing"]:
                    rt.timeline.play()
                else:
                    rt.timeline.pause()
            except BaseException as error:
                errors.append("live_restore: " + (str(error) or type(error).__name__))
        checks = {"original_stage": restored}
        try:
            checks.update(camera=str(rt.viewport.camera_path) == saved["camera"],
                resolution=tuple(rt.viewport.resolution) == saved["resolution"],
                fill_frame=rt.viewport.fill_frame == saved["fill_frame"],
                selection=rt.selection() == saved["selection"],
                renderer=rt.marine.same_settings(rt.renderer(), saved["renderer"]),
                display=rt.display() == saved["display"],
                timeline_time=rt.timeline.get_current_time() == saved["seconds"],
                timeline_playing=rt.timeline.is_playing() == saved["playing"],
                source_content=(source_hash is None or report.get("restored_source_content_hash") == source_hash))
        except BaseException as error:
            errors.append("verification: " + (str(error) or type(error).__name__))
            checks["verification_completed"] = False
        safe = restored and not errors and all(checks.values())
        rt.gate.paused = saved["paused"] if safe else True
        rt.lock._busy = saved["busy"] if safe else True
        checks.update(controller_gate=rt.gate.paused == saved["paused"],
            capture_lock=rt.lock._busy == saved["busy"])
        report.update(restoration_checks=checks, restoration_errors=errors,
            recovery_required=not safe, controller_gate_restored=checks["controller_gate"])
        if safe:
            retained.Clear()
        else:
            try:
                rt.timeline.pause()
            except BaseException as error:
                errors.append("recovery_pause: " + (str(error) or type(error).__name__))
            _recovery_caches.append({"cache": retained, "original_stage": original_stage,
                "saved": saved, "owner": owner, "token": token, "directory": str(directory)})
        report["passed"] = (failure is None and safe and len(report["captures"]) == len(orders) * 5
            and report.get("all_state_hashes_equal", False))
        report["status"] = "passed" if report["passed"] else "failed"
        _write(directory / "manifest.json", report)
    if isinstance(failure, asyncio.CancelledError):
        raise failure
    return {"ok": report["passed"], "directory": str(directory),
        "manifest": str(directory / "manifest.json"), "capture_count": len(report["captures"]),
        "resolved_scene_state_hash": report.get("resolved_scene_state_hash"),
        "error": report.get("error"), "recovery_required": report["recovery_required"]}
