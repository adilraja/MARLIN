"""Shared frozen-scene transaction for M6 pairing and M7 explicit removal.

The engine keeps capture, gate and restoration semantics in one implementation.
M6 public inputs and output semantics are unchanged; dataset mode adds a second
private scene whose only physical change is removal of the bridge-owned target.
"""
import asyncio
from copy import deepcopy
import math
from pathlib import Path
import shutil
import struct
import tempfile

from .exchange_v2 import validate_step
from .paired_state_v2 import resolved_record, camera_condition, source_content_hash
from .paired_v2 import (CAMERA, RESOLUTION, KitRuntime, validate_conditions,
    verify_pilot_camera, _write, _digest, _recovery_caches)


async def run(owner, token, orders, delay_s, runtime=None, dataset=False):
    """Hold one ownership/scene transaction through all conditions and delays.

    Runtime injection exists for offline failure tests, never as an HTTP option.
    The endpoint accepts only a token, bounded complete orders and bounded delay.
    """
    orders, delay_s = validate_conditions(orders, delay_s)
    if dataset and (orders != [[.5, 1., 2., 3., 4.]] or delay_s != 0):
        raise ValueError("Dataset capture requires the fixed five-GSD paired workload")
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
    directory = Path(tempfile.mkdtemp(prefix="dataset_" if dataset else "paired_", dir=rt.output_root))
    report = {"milestone": 7 if dataset else 6, "passed": False, "status": "running", "source_state": state,
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
    dataset_bundle = None
    active_stage = None
    active_variant = "present"
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
        scene_file = "present_scene.usdc" if dataset else "source_scene.usdc"
        frozen.GetRootLayer().Export(str(directory / scene_file))
        report["source_scene_sha256"] = _digest(directory / scene_file)
        variants = [("present", frozen, identity)]
        if dataset:
            from .dataset_state_v2 import prepare_variants, variant_record, background_record, annotation
            dataset_bundle = prepare_variants(frozen, state, saved["renderer"], dependencies, clock)
            if dataset_bundle["present_record"] != identity:
                raise ValueError("Dataset positive identity differs from the M6 snapshot definition")
            absent = dataset_bundle["absent_stage"]
            retained.Insert(absent)
            absent.GetRootLayer().Export(str(directory / "absent_scene.usdc"))
            report.update(parent_scene_hash=identity["resolved_scene_state_hash"],
                background_scene_hash=dataset_bundle["background_hash"],
                target_removal=dataset_bundle["removal_record"],
                variant_records={"present": identity, "absent": dataset_bundle["absent_record"]},
                variant_scene_files={"present": {"file": scene_file, "sha256": report["source_scene_sha256"]},
                    "absent": {"file": "absent_scene.usdc", "sha256": _digest(directory / "absent_scene.usdc")}},
                annotation_semantics="amodal_direct_evaluated_mesh_projection",
                target_class_scope="Bridge-owned harbour porpoise only; demonstration species remain unlabelled background")
            variants.append(("absent", absent, dataset_bundle["absent_record"]))
            _write(directory / "absent_resolved_state.json", dataset_bundle["absent_record"])
            _write(directory / "manifest.json", report)

        def check(label):
            if rt.stage() != active_stage or not rt.gate.paused or not rt.lock._busy or rt.timeline.is_playing():
                raise ValueError("Frozen capture transaction context/gates changed")
            if rt.timeline.get_current_time() != saved["seconds"] or rt.ocean_clock() != clock["ocean"]:
                report["clock_failure"] = {"label": label,
                    "expected_timeline_seconds": saved["seconds"],
                    "actual_timeline_seconds": rt.timeline.get_current_time(),
                    "expected_ocean": clock["ocean"], "actual_ocean": rt.ocean_clock()}
                raise ValueError("Biological or environmental time advanced during capture")
            if owner.buffer.latest != state:
                raise ValueError("Owned GAMA source state changed during capture")
            common_dependencies = rt.dependencies(frozen)
            if dataset:
                current = variant_record(active_stage, state, rt.renderer(), common_dependencies, clock,
                    active_variant == "present", report["parent_scene_hash"])
                background = background_record(active_stage, state, rt.renderer(), common_dependencies, clock)
                if background["background_hash"] != report["background_scene_hash"]:
                    raise ValueError("Paired target removal changed the frozen background")
            else:
                current = resolved_record(active_stage, state, rt.renderer(), common_dependencies, clock)
            actual_hash = current["resolved_scene_state_hash"]
            check_row = {"label": label, "resolved_scene_state_hash": actual_hash,
                "matches": actual_hash == expected_hash}
            if dataset:
                check_row.update(variant=active_variant, target_present=active_variant == "present",
                    parent_scene_hash=report["parent_scene_hash"], background_scene_hash=background["background_hash"])
            report["state_checks"].append(check_row)
            if actual_hash != expected_hash:
                raise ValueError("Resolved biological/environmental state changed")
            return actual_hash

        for active_variant, active_stage, active_record in variants:
            expected_hash = active_record["resolved_scene_state_hash"]
            if dataset:
                # Both private variants retain the original camera. Select it
                # before attaching so RTX need not author a placeholder for a
                # pair camera that has not yet been built on the next variant.
                rt.viewport.camera_path = saved["camera"]
            await rt.attach(active_stage)
            rt.timeline.pause()
            rt.timeline.set_current_time(saved["seconds"])
            rt.restore_renderer(saved["renderer"])
            rt.select([])
            rt.set_display(0)
            # Timeline setters are committed by Kit's next update after attaching
            # a stage. Keep both gates closed while that context transition settles.
            for _ in range(3):
                await rt.update()
            check((active_variant + "_" if dataset else "") + "after_attach")
            for order_index, order in enumerate(orders):
                for condition_index, gsd in enumerate(order):
                    label = (active_variant + "_" if dataset else "") + f"order_{order_index}_condition_{condition_index}"
                    folder = directory / label
                    folder.mkdir()
                    check(label + "_before_delay")
                    delay = delay_s if order_index else 0
                    if delay:
                        await rt.sleep(delay)
                    check(label + "_after_delay")
                    rt.camera(active_stage, gsd, anchor, plane)
                    rt.viewport.camera_path = CAMERA
                    rt.viewport.fill_frame = False
                    rt.viewport.resolution = RESOLUTION
                    for _ in range(120):
                        await rt.update()
                    rt.viewport.fill_frame = False
                    rt.viewport.resolution = RESOLUTION
                    check(label + "_after_warmup")
                    projection_before = rt.projection(active_stage)
                    condition = camera_condition(active_stage, CAMERA, gsd, [anchor[0], plane, anchor[1]], plane, RESOLUTION)
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
                    projection_after = rt.projection(active_stage)
                    after_condition = camera_condition(active_stage, CAMERA, gsd, [anchor[0], plane, anchor[1]], plane, RESOLUTION)
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
                    if dataset:
                        labels = annotation(active_stage, projection_after, state, active_variant == "present")
                        annotation_path, yolo_path = folder / "annotation.json", folder / "labels.txt"
                        _write(annotation_path, labels["annotation"])
                        yolo_path.write_text(labels["yolo_label"])
                        item.update(variant=active_variant, target_present=active_variant == "present",
                            parent_scene_hash=report["parent_scene_hash"], background_scene_hash=report["background_scene_hash"],
                            annotation=labels["annotation"], annotation_file=str(annotation_path.relative_to(directory)),
                            annotation_sha256=_digest(annotation_path), yolo_file=str(yolo_path.relative_to(directory)),
                            yolo_sha256=_digest(yolo_path))
                        check(label + "_annotations_complete")
                    _write(folder / "capture.json", item)
                    report["captures"].append(item)
                    _write(directory / "manifest.json", report)
        report["all_variant_state_checks_match" if dataset else "all_state_hashes_equal"] = all(x["matches"] for x in report["state_checks"])
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
        report["passed"] = (failure is None and safe and len(report["captures"]) == len(orders) * 5 * (2 if dataset else 1)
            and report.get("all_variant_state_checks_match" if dataset else "all_state_hashes_equal", False))
        report["status"] = "passed" if report["passed"] else "failed"
        _write(directory / "manifest.json", report)
    if isinstance(failure, asyncio.CancelledError):
        raise failure
    response = {"ok": report["passed"], "directory": str(directory),
        "manifest": str(directory / "manifest.json"), "capture_count": len(report["captures"]),
        "resolved_scene_state_hash": report.get("resolved_scene_state_hash"),
        "error": report.get("error"), "recovery_required": report["recovery_required"]}
    if dataset:
        response.update(parent_scene_hash=report.get("parent_scene_hash"),
            background_scene_hash=report.get("background_scene_hash"))
    return response
