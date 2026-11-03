"""Bounded M5 audit, executed by the existing MARLIN app's --exec option.

Reuse MARLIN's capture, snapshot, projection, settings and restoration helpers.
No production source or historical capture is edited; one context/viewport only.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[3]
ATTEMPT = os.environ.get('MARLIN_M5_ATTEMPT', '01')
if ATTEMPT not in ('01', '02'):
    raise ValueError('Only explicitly recorded audit attempts are supported')
RUN = ROOT / ('runs/attempt' + ATTEMPT)
SOURCE = REPO / 'experiments/ocean_material_v1/diagnostics/m4/captures/oblique_f3h1u1um'
RECOVERY = ROOT / 'qa/driver_recovery_2026_11_03'
CAMERA = '/World/MarlinOceanIntegrationDiagnostic/Camera'


def plain(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, 'path') and hasattr(value, 'resolvedPath'):
        return dict(authored=value.path, resolved=value.resolvedPath)
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    try:
        return [plain(v) for v in value]
    except TypeError:
        return str(value)


def write(path, data):
    path.write_text(json.dumps(plain(data), indent=2) + '\n')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def state_record(stage):
    """Hash evaluated authored scene inputs, excluding viewport-owned /Render."""
    records = {}
    for prim in stage.TraverseAll():
        path = str(prim.GetPath())
        if path.startswith('/Render') or path.startswith('/OmniverseKit_'):
            continue
        attrs = {a.GetName(): dict(type=str(a.GetTypeName()), value=plain(a.Get()),
                    connections=[str(p) for p in a.GetConnections()]) for a in prim.GetAuthoredAttributes()}
        data = dict(type=prim.GetTypeName(), active=prim.IsActive(),
                    apis=list(prim.GetAppliedSchemas()), attributes=attrs,
                    relationships={r.GetName(): [str(p) for p in r.GetTargets()] for r in prim.GetRelationships()})
        records[path] = sha(json.dumps(data, sort_keys=True).encode())
    return dict(prim_hashes=records, evaluated_scene_sha256=sha(json.dumps(records, sort_keys=True).encode()),
                scope='Evaluated authored prim types/APIs/attributes/connections/relationships; excludes /Render and default UI cameras')


def effective_record(stage, viewport):
    return {label: {a.GetName(): plain(a.Get()) for a in prim.GetAttributes()
                    if not a.GetName().startswith('outputs:')}
            for label, prim in [('camera', stage.GetPrimAtPath(CAMERA)),
                                ('render_product', stage.GetPrimAtPath(viewport.render_product_path))]}


async def run_suite():
    import carb.settings
    import omni.kit.app
    import omni.timeline
    import omni.usd
    from pxr import Usd
    from omni.kit.viewport.utility import get_active_viewport, capture_viewport_to_file
    from cris.madil.render_service import calibration_capture, capture_state
    from cris.madil.render_service.hidef_marine import (gpu_preflight, settings_record,
        restore_settings, same_settings, open_snapshot, freeze_stage)
    from cris.madil.render_service.capture_projection import record_projection
    from cris.madil.render_service.water_medium_diagnostics import setup_medium_viewport, MediumRequest, capture_hdr

    app = omni.kit.app.get_app()
    context = omni.usd.get_context()
    viewport = get_active_viewport()
    main_stage = context.get_stage()
    if viewport is None or main_stage is None or calibration_capture._busy:
        raise RuntimeError('An idle existing viewport and restored scene are required')
    retained = Usd.StageCache()
    retained.Insert(main_stage)
    saved = dict(camera=str(viewport.camera_path), resolution=tuple(viewport.resolution),
                 fill=viewport.fill_frame, paused=capture_state.paused,
                 settings=settings_record(), state=state_record(main_stage),
                 selection=context.get_selection().get_selected_prim_paths())
    settings = carb.settings.get_settings()
    guide_paths = [f'/persistent/app/viewport/{viewport.id}/guide/{name}/visible'
                   for name in ('grid', 'axis', 'selection', 'boundingBox')]
    guide_paths += ['/app/viewport/outline/enabled', '/app/viewport/boundingBoxes/enabled',
                    '/persistent/app/viewport/displayOptions']
    guides = {path: settings.get(path) for path in guide_paths}
    timeline = omni.timeline.get_timeline_interface()
    playing, seconds = timeline.is_playing(), timeline.get_current_time()
    calibration_capture._busy = True
    capture_state.paused = True
    timeline.pause()
    source_metadata = json.loads((SOURCE / 'metadata.json').read_text())
    assert sha((SOURCE / 'scene.usdc').read_bytes()) == source_metadata['scene_sha256']
    records = []
    active_globals = None

    async def attach(path, mode):
        nonlocal active_globals
        stage = open_snapshot(path)
        ok, error = await context.attach_stage_async(stage)
        if not ok:
            raise RuntimeError(error)
        restore_settings(active_globals if active_globals is not None else saved['settings'])
        settings.set('/rtx/fog/enabled', False)
        settings.set('/exts/cris.madil.render_service/underwaterCue/enabled', False)
        for key in guide_paths:
            settings.set(key, 0 if key.endswith('displayOptions') else False)
        context.get_selection().clear_selected_prim_paths()
        viewport.fill_frame = False
        viewport.resolution = (512, 384)
        viewport.camera_path = CAMERA
        for _ in range(30):
            await app.next_update_async()
        viewport.fill_frame = False
        viewport.resolution = (512, 384)
        setup_medium_viewport(viewport, MediumRequest(renderer=mode), hide_overlays=False)
        if active_globals is None:
            active_globals = settings_record()
        return stage

    async def capture(label, mode, history, reload_input=None):
        directory = RUN / label
        directory.mkdir(exist_ok=False)
        started = time.monotonic()
        try:
            gpu = gpu_preflight(768)
            await asyncio.wait_for(viewport.wait_for_rendered_frames(64), timeout=30)
            stage = context.get_stage()
            if tuple(viewport.resolution) != (512, 384):
                raise RuntimeError('Declared output resolution was not retained')
            projection = record_projection(stage, viewport)
            state = state_record(stage)
            effective = effective_record(stage, viewport)
            for filename in ('warmup.png', 'rgb.png'):
                job = capture_viewport_to_file(viewport, file_path=str(directory / filename))
                await job.wait_for_result(completion_frames=5)
            hdr = await capture_hdr(viewport, directory)
            result = dict(label=label, mode=mode, history=history, gpu_before=gpu,
                elapsed_seconds=time.monotonic()-started, rendered_frame_wait_completed=64,
                actual_gpu_samples_measured=False, projection=projection,
                effective_controls=effective, renderer_globals=settings_record(),
                state=state, hdr=hdr, layer_identifier=stage.GetRootLayer().identifier,
                reload_input=reload_input)
            write(directory / 'metadata.json', result)
            records.append(result)
            write(RUN / 'capture_records.json', records)
            return result
        except BaseException as exc:
            write(directory / 'failure.json', dict(error=str(exc) or type(exc).__name__,
                traceback=traceback.format_exc(), elapsed_seconds=time.monotonic()-started,
                mode=mode, history=history, requested_resolution=[512, 384]))
            raise

    async def bounded_capture(*args, **kwargs):
        return await asyncio.wait_for(capture(*args, **kwargs), timeout=60)

    try:
        gpu_preflight(768)
        fixture = await attach(SOURCE / 'scene.usdc', 'PathTracing')
        await bounded_capture('baseline', 'PathTracing', 'Fresh anonymous read of sealed M4 fixture; 64 rendered frames plus discarded warmup')
        frozen, sampled = freeze_stage(fixture, Usd.TimeCode.Default())
        snapshot = RUN / 'saved_scene.usdc'
        frozen.GetRootLayer().Export(str(snapshot))
        snapshot_sha = sha(snapshot.read_bytes())
        write(RUN / 'snapshot.json', dict(path=str(snapshot), sha256=snapshot_sha,
              source_scene_sha256=source_metadata['scene_sha256'], sampled_attributes=sampled,
              initial_evaluated_state=state_record(frozen)))
        for name in ('repeat_a', 'repeat_b'):
            await bounded_capture(name, 'PathTracing', 'Same stage and retained history; another 64 rendered frames plus discarded warmup')
        for name in ('reload_a', 'reload_b'):
            assert sha(snapshot.read_bytes()) == snapshot_sha
            fixture = await attach(snapshot, 'PathTracing')
            await bounded_capture(name, 'PathTracing', 'Fresh disk read into a new anonymous layer and stage attachment; 64 rendered frames plus discarded warmup',
                                  reload_input=dict(path=str(snapshot), sha256=snapshot_sha))
        product = fixture.GetPrimAtPath(viewport.render_product_path)
        allowed = list(product.GetAttribute('omni:rtx:rendermode').GetMetadata('allowedTokens') or [])
        write(RUN / 'renderer_allowed_tokens.json', allowed)
        if 'RealTimePathTracing' in allowed:
            gpu_preflight(768)
            product.GetAttribute('omni:rtx:rendermode').Set('RealTimePathTracing')
            await bounded_capture('mode_comparison', 'RealTimePathTracing', 'Same frozen stage; renderer-token switch followed by 64 rendered frames plus discarded warmup')
        else:
            write(RUN / 'mode_comparison_unavailable.json', dict(allowed=allowed, render_attempted=False))
        assert sha(snapshot.read_bytes()) == snapshot_sha
        write(RUN / 'execution_result.json', dict(execution_complete=True, capture_count=len(records),
              snapshot_hash_preserved=True, pixel_analysis_pending=True))
    finally:
        capture_state.paused = True
        ok, error = await context.attach_stage_async(main_stage)
        if not ok:
            raise RuntimeError('Could not restore main stage: ' + error)
        restore_settings(saved['settings'])
        restore_settings(guides)
        viewport.camera_path = saved['camera']
        viewport.resolution = saved['resolution']
        viewport.fill_frame = saved['fill']
        context.get_selection().set_selected_prim_paths(saved['selection'], False)
        for _ in range(10):
            await app.next_update_async()
        restoration = dict(main_stage_restored=context.get_stage() == main_stage,
            camera_restored=str(viewport.camera_path) == saved['camera'],
            resolution_restored=tuple(viewport.resolution) == saved['resolution'],
            fill_restored=viewport.fill_frame == saved['fill'],
            renderer_globals_restored=same_settings(settings_record(), saved['settings']),
            scene_state_restored=state_record(main_stage) == saved['state'])
        write(RUN / 'restoration.json', restoration)
        timeline.set_current_time(seconds)
        if playing:
            timeline.play()
        capture_state.paused = saved['paused']
        calibration_capture._busy = False
        retained.Clear()
        if not all(restoration.values()):
            raise RuntimeError('A restoration check failed; inspect restoration.json')


async def main():
    import omni.kit.app
    from cris.madil.render_service.scene_diagnostics import restore_checkpoint, checkpoint_scene
    from cris.madil.render_service.scene_setup import setup_marine_scene, MarineSceneSetupDataModel
    from cris.madil.render_service.hidef_marine import settings_record, same_settings
    from omni.kit.viewport.utility import get_active_viewport
    app = omni.kit.app.get_app()
    RUN.mkdir(parents=True, exist_ok=False)
    try:
        for _ in range(90):
            await app.next_update_async()
        checkpoint = json.loads((RECOVERY / 'pre_reboot_checkpoint.json').read_text())
        assert sha((Path(checkpoint['directory']) / 'scene.usdc').read_bytes()) == checkpoint['scene_sha256']
        result = await restore_checkpoint(checkpoint['checkpoint_id'])
        write(RUN / 'checkpoint_restore.json', result)
        if not result['ok']:
            raise RuntimeError('Checkpoint restoration failed')
        viewport = get_active_viewport()
        checks = dict(camera=str(viewport.camera_path) == checkpoint['camera'],
                      resolution=list(viewport.resolution) == checkpoint['resolution'],
                      fill_frame=viewport.fill_frame == checkpoint['fill_frame'],
                      renderer_settings=same_settings(settings_record(), checkpoint['renderer_settings']))
        write(RUN / 'checkpoint_restore_checks.json', checks)
        if not all(checks.values()):
            raise RuntimeError('Restored checkpoint settings differ')
        # Establish initial renderer readiness separately from the unchanged
        # 64-frame/30-second capture-settle budget. The first attempt entered
        # capture before the app reported its first RTX-ready frame.
        readiness_started = time.monotonic()
        await asyncio.wait_for(viewport.wait_for_rendered_frames(3), timeout=90)
        write(RUN / 'startup_readiness.json', dict(completed_rendered_frames=3,
              elapsed_seconds=time.monotonic()-readiness_started, timeout_seconds=90,
              scope='Initial app renderer readiness, before the capture suite; no image accepted here'))
        manager = app.get_extension_manager()
        write(RUN / 'runtime.json', dict(kit_build=app.get_build_version(),
              extensions=[{k: e.get(k) for k in ('id', 'name', 'version', 'enabled')}
                          for e in manager.get_extensions() if e.get('enabled')]))
        try:
            await asyncio.wait_for(run_suite(), timeout=300)
        finally:
            # Reconstruct the recorded standard live controllers only after
            # restoring the frozen checkpoint. Phase/history continuity is not claimed.
            setup = await setup_marine_scene(MarineSceneSetupDataModel(start_swimming=False))
            write(RUN / 'live_controllers_reconstructed.json', setup)
            write(RUN / 'final_checkpoint.json', await checkpoint_scene())
        write(RUN / 'done.json', dict(ok=True, image_analysis_pending=True,
              phase_note='User reboot reset GPU history; standard ocean/chase controllers reconstructed after audit; swimming remained stopped.'))
    except BaseException as exc:
        write(RUN / 'audit_failure.json', dict(error=str(exc) or type(exc).__name__, traceback=traceback.format_exc()))


asyncio.ensure_future(main())
