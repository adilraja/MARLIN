"""Finite local M5 jobs using the accepted actor and native MARLIN HDR route."""
import asyncio
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import time
import traceback

QA = Path(__file__).resolve().parent
BASE = QA.parents[1]
REPO = QA.parents[3]
MEDIA = REPO / 'artifacts/gama_dolphin_behaviour_v1/m5'
CAMERA = '/MarlinM5ReviewCamera'
spec = importlib.util.spec_from_file_location('_m5_reused_m4_native', BASE / 'qa/m4/native_worker.py')
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
plain, write, geometry = helpers.plain, helpers.write, helpers.geometry


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def key(seconds):
    return f'{seconds:07.2f}'.replace('.', '_')


def controlled_state(record):
    value = copy.deepcopy(record)
    value['projection'].pop('ui_view_matrix', None)
    value['projection'].pop('ui_projection_matrix', None)
    return value


def environment(stage):
    import numpy as np
    from pxr import UsdGeom
    mesh = UsdGeom.Mesh(stage.GetPrimAtPath('/World/Ocean'))
    ocean = {name: hashlib.sha256(np.asarray(mesh.GetPrim().GetAttribute(name).Get()).tobytes()).hexdigest()
             for name in ('points', 'normals', 'extent', 'faceVertexCounts', 'faceVertexIndices')}
    lights = {str(p.GetPath()): {a.GetName(): plain(a.Get()) for a in p.GetAttributes()}
              for p in stage.Traverse() if 'Light' in p.GetTypeName()}
    return dict(ocean_geometry=ocean, lighting=lights, ocean_phase_s=0., timeline_paused=True)


async def suite(run_id, mode, report):
    import numpy as np
    import carb.settings
    import omni.kit.app
    import omni.timeline
    import omni.usd
    from pxr import Gf, Usd, UsdGeom, UsdSkel
    from omni.kit.viewport.utility import get_active_viewport
    from cris.madil.render_service import calibration_capture, capture_state, ocean
    from cris.madil.render_service.hidef_marine import freeze_stage, settings_record, restore_settings, same_settings, gpu_preflight
    from cris.madil.render_service.ocean_medium import select_preset, PresetRequest, author_frame
    from cris.madil.render_service.capture_projection import record_projection
    from cris.madil.render_service.water_medium_diagnostics import setup_medium_viewport, MediumRequest, capture_hdr
    from cris.madil.gama_bridge.actor_animated_v3 import AnimatedBottlenoseActor, ACTOR

    plan = json.loads((QA / 'locked_plan_v3.json').read_text())
    source_path = REPO / plan['reference']['path']
    assert digest(source_path) == plan['reference']['sha256']
    for name in ('m4_manifest', 'gate_c_acceptance', 'acceptance'):
        assert digest(REPO / plan[name]['path']) == plan[name]['sha256']
    source = json.loads(source_path.read_text())
    profile = json.loads((REPO / plan['capture']['exposure_profile']['path']).read_text())
    app = omni.kit.app.get_app()
    context = omni.usd.get_context()
    live, viewport = context.get_stage(), get_active_viewport()
    assert live is not None and viewport is not None and not calibration_capture._busy
    assert ocean._ocean_animation_subscription is None and ocean._ocean_animation_state is None
    timeline = omni.timeline.get_timeline_interface()
    settings = carb.settings.get_settings()
    guides = [f'/persistent/app/viewport/{viewport.id}/guide/{n}/visible' for n in ('grid', 'axis', 'selection', 'boundingBox')]
    guides += ['/app/viewport/outline/enabled', '/app/viewport/boundingBoxes/enabled',
               '/persistent/app/viewport/displayOptions', f'/persistent/app/viewport/{viewport.id}/fillViewport']
    saved = dict(camera=str(viewport.camera_path), resolution=list(viewport.resolution), fill=viewport.fill_frame,
                 settings=settings_record(), guides={k: settings.get(k) for k in guides},
                 selection=context.get_selection().get_selected_prim_paths(),
                 playing=timeline.is_playing(), time=timeline.get_current_time(), paused=capture_state.paused)
    cache = Usd.StageCache()
    cache.Insert(live)
    owner = None
    calibration_capture._busy = True
    capture_state.paused = True
    timeline.pause()
    directory = MEDIA / run_id
    directory.mkdir(parents=True, exist_ok=False)
    report.update(media_directory=str(directory), records=[], captures=[], gpu=[], checks={}, comparisons=[])
    started = time.monotonic()
    try:
        report['gpu'].append(gpu_preflight(768))
        stage, _ = freeze_stage(live, Usd.TimeCode.Default())
        cache.Insert(stage)
        ok, error = await context.attach_stage_async(stage)
        assert ok, error
        background = stage.GetPrimAtPath('/World/Cetaceans')
        if background:
            UsdGeom.Imageable(background).MakeInvisible()
        viewport.fill_frame = False
        viewport.resolution = (512, 384)
        camera = UsdGeom.Camera.Define(stage, CAMERA)
        camera.CreateFocalLengthAttr(35)
        camera.CreateHorizontalApertureAttr(30.72)
        camera.CreateVerticalApertureAttr(23.04)
        camera.CreateFStopAttr(0)
        camera.CreateClippingRangeAttr(Gf.Vec2f(1, 100000))
        camera.MakeMatrixXform()
        viewport.camera_path = CAMERA
        for _ in range(12):
            await app.next_update_async()
        viewport.resolution = (512, 384)
        select_preset(stage, PresetRequest(selection='original'))
        created = await ocean.start_ocean_animation(ocean.OceanAnimationDataModel(**plan['ocean']['configuration']))
        assert created['ok'], created
        local_ocean = copy.deepcopy(ocean._ocean_animation_state)
        ocean.shutdown_ocean_animation()
        local_ocean['elapsed'] = local_ocean['accumulator'] = 0.
        mesh = UsdGeom.Mesh(stage.GetPrimAtPath('/World/Ocean'))
        arrays = ocean._calculate_animated_ocean(local_ocean, 0.)
        author_frame(mesh, *arrays)
        try:
            ocean._ocean_animation_state = local_ocean
            report['preset'] = select_preset(stage, PresetRequest(selection='engineering_v1', configure_renderer=True))
        finally:
            ocean._ocean_animation_state = None
        setup_medium_viewport(viewport, MediumRequest(renderer='PathTracing'), hide_overlays=False)
        for name, value in {'exposure:time': profile['exposure_time_s'], 'exposure:fStop': profile['exposure_fstop'],
                            'exposure:iso': profile['exposure_iso'], 'exposure:responsivity': profile['exposure_responsivity']}.items():
            camera.GetPrim().GetAttribute(name).Set(value)
        for name in guides:
            settings.set(name, 0 if name.endswith('displayOptions') else False)
        context.get_selection().clear_selected_prim_paths()
        owner = AnimatedBottlenoseActor()
        token = owner.acquire(stage, 'Bottlenose_001')['ownership_token']
        units = UsdGeom.GetStageMetersPerUnit(stage)
        initial = geometry(stage, ACTOR)
        inverse = owner.expected_matrix.GetInverse()
        local_points = np.array([list(inverse.Transform(Gf.Vec3d(*p))) for p in initial])
        target_offset = (local_points.min(axis=0) + local_points.max(axis=0)) / 2
        water_hi = float(np.asarray(arrays[0])[:, 1].max())
        env = environment(stage)
        report.update(environment=env, units=units, body_fingerprint=owner.expected_body,
                      renderer_settings=settings_record(), capture_profile=profile,
                      ocean_configuration=plan['ocean']['configuration'], frozen_ocean_phase_s=0., resolution=[512, 384])
        index = -1

        def seek(seconds):
            nonlocal index
            target = min(len(source)-1, int(math.ceil(seconds/source[0]['simulation_step_s']-1e-10)))
            if index > target or (owner.buffer.samples and seconds < owner.buffer.samples[0]['simulation_time_s']):
                owner.reset(stage, token)
                index = -1
            while index < target:
                index += 1
                owner.apply(stage, token, source[index])
            owner.evaluate(stage, token, seconds)
            a = owner.frame['agent']
            heading = math.radians(a['heading_deg'])
            centre = owner.expected_matrix.Transform(Gf.Vec3d(*target_offset))
            eye = Gf.Vec3d(centre[0]+3.8*math.cos(heading)/units,
                           max(water_hi+1./units, centre[1]+2./units),
                           centre[2]-3.8*math.sin(heading)/units)
            assert eye[1] > water_hi
            camera.GetPrim().GetAttribute('xformOp:transform').Set(Gf.Matrix4d().SetLookAt(eye, centre, Gf.Vec3d(0, 1, 0)).GetInverse())

        def state(seconds, skin=False):
            owner._guard(stage, token, False)
            animation = owner.pose.animation
            record = dict(simulation_time_s=seconds, frame=copy.deepcopy(owner.frame),
                root_matrix=plain(UsdGeom.Xformable(stage.GetPrimAtPath(ACTOR)).ComputeLocalToWorldTransform(Usd.TimeCode.Default())),
                joint_local_matrices=plain(UsdSkel.Cache().GetAnimQuery(animation).ComputeJointLocalTransforms(Usd.TimeCode.Default())),
                joint_translations=plain(animation.GetTranslationsAttr().Get()), joint_rotations=plain(animation.GetRotationsAttr().Get()),
                joint_scales=plain(animation.GetScalesAttr().Get()), pose_controls=copy.deepcopy(owner.pose_controls),
                source_prefix_last_index=index, accepted_steps=owner.buffer.accepted_steps,
                buffer_samples=copy.deepcopy(owner.buffer.samples), body_fingerprint=owner.expected_body,
                camera_matrix=plain(UsdGeom.Xformable(camera.GetPrim()).ComputeLocalToWorldTransform(Usd.TimeCode.Default())),
                projection=record_projection(stage, viewport), environment_sha256=fingerprint(env),
                timeline_s=timeline.get_current_time(), timeline_playing=timeline.is_playing(),
                root_time_samples=stage.GetPrimAtPath(ACTOR).GetAttribute('xformOp:transform').GetTimeSamples(),
                joint_time_samples={n: animation.GetPrim().GetAttribute(n).GetTimeSamples() for n in ('translations', 'rotations', 'scales')})
            return record

        def compare(before, after, label):
            metrics = dict(label=label, simulation_time_s=before['simulation_time_s'],
                root_matrix_error=float(np.max(np.abs(np.asarray(before['root_matrix'])-after['root_matrix']))),
                joint_matrix_error=float(np.max(np.abs(np.asarray(before['joint_local_matrices'])-after['joint_local_matrices']))),
                phase_error=abs(before['pose_controls']['phase']-after['pose_controls']['phase']),
                weight_error=abs(before['pose_controls']['weight']-after['pose_controls']['weight']),
                camera_matrix_error=float(np.max(np.abs(np.asarray(before['camera_matrix'])-after['camera_matrix']))),
                agent_equal=before['frame']['agent']==after['frame']['agent'],
                environment_equal=before['environment_sha256']==after['environment_sha256'],
                body_equal=before['body_fingerprint']==after['body_fingerprint'])
            tol = json.loads((REPO / plan['acceptance']['path']).read_text())
            metrics['passed'] = (metrics['root_matrix_error'] <= tol['root_matrix_component_error'] and
                metrics['joint_matrix_error'] <= tol['joint_matrix_component_error'] and metrics['phase_error'] <= tol['phase_error_cycles'] and
                metrics['weight_error'] <= 1e-9 and metrics['camera_matrix_error'] <= 1e-8 and
                metrics['agent_equal'] and metrics['environment_equal'] and metrics['body_equal'])
            report['comparisons'].append(metrics)
            assert metrics['passed'], metrics

        async def capture(seconds, label, snapshot=False):
            folder = directory / label
            folder.mkdir(exist_ok=False)
            commanded = state(seconds)
            env_before = environment(stage)
            settling = 64 if snapshot else 3
            await asyncio.wait_for(viewport.wait_for_rendered_frames(settling), timeout=30)
            before = state(seconds)
            write(folder/'settle_check.json', dict(commanded=commanded, settled=before,
                exact_commanded_state_held=controlled_state(commanded)==controlled_state(before)))
            assert controlled_state(commanded) == controlled_state(before), 'Commanded state advanced while settling'
            result = await capture_hdr(viewport, folder)
            deadline = time.monotonic()+15
            while time.monotonic() < deadline:
                if (folder/'hdr.exr').is_file() and (folder/'hdr.exr').stat().st_size > 1024:
                    size = (folder/'hdr.exr').stat().st_size
                    for _ in range(3):
                        await app.next_update_async()
                    if (folder/'hdr.exr').stat().st_size == size:
                        break
                await app.next_update_async()
            else:
                raise RuntimeError('Native EXR writer did not settle')
            after = state(seconds)
            write(folder/'capture_hold_check.json', dict(before=before, after=after,
                full_record_equal=before==after, exact=controlled_state(before)==controlled_state(after),
                comparison='Exact commanded state, including authored capture-camera/frustum; UI viewport cache metadata retained separately'))
            assert controlled_state(before) == controlled_state(after), 'Animal/controller/capture-camera state advanced during capture'
            assert environment(stage) == env_before == env, 'Ocean or lighting advanced during capture'
            before.update(capture=result, settle_frames=settling, global_settings=settings_record(),
                          held_exactly_during_capture=True, environment=env)
            if snapshot:
                frozen, sampled = freeze_stage(stage, Usd.TimeCode.Default())
                frozen.GetRootLayer().Export(str(folder/'scene.usdc'))
                before.update(scene_file='scene.usdc', scene_sha256=digest(folder/'scene.usdc'), frozen_sampled_attributes=sampled)
                points = geometry(stage, ACTOR)*units
                np.savez_compressed(folder/'skin.npz', points_m=points)
                before['skin_file'] = 'skin.npz'
                before['skin_sha256'] = digest(folder/'skin.npz')
            before['hdr_npz_sha256'] = digest(folder/'hdr.npz')
            before['hdr_exr_sha256'] = digest(folder/'hdr.exr')
            write(folder/'state.json', before)
            report['captures'].append(dict(label=label, simulation_time_s=seconds, snapshot=snapshot,
                state_sha256=digest(folder/'state.json'), held_exactly=True))
            return before

        # Initial material readiness was independent of the image settle budget.
        quiet = None
        start = time.monotonic()
        while time.monotonic()-start < 90:
            if context.get_stage_loading_status()[2] == 0:
                quiet = time.monotonic() if quiet is None else quiet
                if time.monotonic()-quiet >= 2:
                    break
            else:
                quiet = None
            await app.next_update_async()
        else:
            raise RuntimeError('Stage streaming did not settle')
        await asyncio.wait_for(viewport.wait_for_rendered_frames(3), timeout=90)
        if mode == 'smoke':
            seek(6.)
            await asyncio.wait_for(capture(6., 'smoke_6', True), timeout=60)
        elif mode == 'primary':
            video = {round(i/plan['video']['fps'], 6): i for i in range(plan['video']['frames'])}
            snapshots = {float(t) for t in plan['snapshot_times_s']}
            times = sorted(set(video)|snapshots)
            a_records = {}
            for n, seconds in enumerate(times):
                seek(seconds)
                record = state(seconds)
                a_records[seconds] = record
                report['records'].append(dict(schedule='A', **record))
                if seconds in video:
                    label = f'frame_{video[seconds]:05d}'
                    await asyncio.wait_for(capture(seconds, label, seconds in snapshots), timeout=60)
                else:
                    label = 'snapshot_'+key(seconds)
                    await asyncio.wait_for(capture(seconds, label, True), timeout=60)
                if n % 5 == 0:
                    report['gpu'].append(gpu_preflight(768))
                    (QA/run_id/'progress.json').write_text(json.dumps(dict(phase='full_sequence', completed=n+1, total=len(times), simulation_time_s=seconds, wall_s=time.monotonic()-started))+'\n')
            write(directory/'schedule_a.json', list(a_records.values()))
            for n, seconds in enumerate(times):
                seek(seconds)
                waits = (0, 1, 5)[n % 3]
                for _ in range(waits):
                    await app.next_update_async()
                current = state(seconds)
                compare(a_records[seconds], current, 'schedule_B_extra_updates_'+str(waits))
                report['records'].append(dict(schedule='B', **current))
                if n % 20 == 0:
                    (QA/run_id/'progress.json').write_text(json.dumps(dict(phase='schedule_B', completed=n+1, total=len(times)))+'\n')
            for seconds in plan['reorder_times_s']:
                seek(seconds)
                compare(a_records[seconds], state(seconds), 'reordered_prefix_replay')
                if seconds in plan['fresh_process_times_s']:
                    await asyncio.wait_for(capture(seconds, 'reorder_'+key(seconds), True), timeout=60)
            write(directory/'comparison_records.json', report['comparisons'])
        else:
            primary = json.loads((QA/plan['primary_run']/'result.json').read_text())
            assert primary['status'] == 'passed'
            expected = {r['simulation_time_s']: r for r in json.loads((Path(primary['media_directory'])/'schedule_a.json').read_text())}
            for seconds in reversed(plan['fresh_process_times_s']):
                seek(seconds)
                compare(expected[seconds], state(seconds), 'fresh_process_prefix_replay')
                await asyncio.wait_for(capture(seconds, 'fresh_'+key(seconds), True), timeout=60)

        # Interruption tests used a nonzero, explicitly selected pose.
        seek(16.)
        held = state(16.)
        owner.set_paused(stage, token, True)
        await asyncio.sleep(2.1)
        paused_state = state(16.)
        write(directory/'pause_hold.json', dict(before=held, after=paused_state,
              exact_controlled_state=controlled_state(paused_state)==controlled_state(held)))
        assert controlled_state(paused_state) == controlled_state(held)
        report['checks']['pause_holds_root_body_buffer_phase_camera'] = True
        try:
            owner.evaluate(stage, token, 16.)
        except ValueError:
            report['checks']['paused_evaluate_rejected'] = True
        else:
            raise AssertionError('Paused evaluation was accepted')
        owner.set_paused(stage, token, False)
        assert controlled_state(state(16.)) == controlled_state(held)
        report['checks']['resume_without_jump'] = True
        await asyncio.sleep(2.1)
        missing_state = state(16.)
        write(directory/'missing_hold.json', dict(before=held, after=missing_state,
              exact_controlled_state=controlled_state(missing_state)==controlled_state(held)))
        assert controlled_state(missing_state) == controlled_state(held)
        assert owner.status(stage)['transport_state'] == 'frozen_updates_missing'
        report['checks']['missing_state_freeze'] = True
        missing = copy.deepcopy(source[index+2])
        try:
            owner.apply(stage, token, missing)
        except ValueError:
            assert controlled_state(state(16.)) == controlled_state(held)
            report['checks']['missing_step_rejected_without_partial_mutation'] = True
        else:
            raise AssertionError('Missing-state gap was accepted')
        owner.reset(stage, token)
        now = state(16.)
        assert all(now[k] == held[k] for k in ('root_matrix', 'joint_local_matrices', 'pose_controls', 'frame'))
        assert owner.buffer.accepted_steps == 0
        report['checks']['controlled_reset_holds_pose_phase'] = True
        owner.release(token)
        assert not stage.GetPrimAtPath('/MarlinGamaBottlenose')
        report['checks']['controlled_stop_removes_owned_actor'] = True
        owner = None
        report['status'] = 'passed'
    finally:
        if owner is not None:
            owner.close()
        ocean.shutdown_ocean_animation()
        try:
            ok, error = await context.attach_stage_async(live)
            assert ok, error
            viewport.camera_path = saved['camera']
            viewport.fill_frame = saved['fill']
            viewport.resolution = tuple(saved['resolution'])
            restore_settings(saved['settings'])
            restore_settings(saved['guides'])
            context.get_selection().set_selected_prim_paths(saved['selection'], False)
            timeline.set_current_time(saved['time'])
            if saved['playing']:
                timeline.play()
            for _ in range(12):
                await app.next_update_async()
            report['restoration'] = dict(stage=context.get_stage()==live, camera=str(viewport.camera_path)==saved['camera'],
                resolution=list(viewport.resolution)==saved['resolution'], fill=viewport.fill_frame==saved['fill'],
                settings=same_settings(settings_record(), saved['settings']), timeline=timeline.get_current_time()==saved['time'],
                ocean_stopped=ocean._ocean_animation_subscription is None, actor_removed=not live.GetPrimAtPath('/MarlinGamaBottlenose'))
            assert all(report['restoration'].values()), report['restoration']
        finally:
            capture_state.paused = saved['paused']
            calibration_capture._busy = False
            cache.Clear()
            report['wall_s'] = time.monotonic()-started


async def main(run_id, mode):
    if run_id not in ('smoke01', 'smoke02', 'smoke03', 'primary01', 'primary02', 'fresh01') or mode not in ('smoke', 'primary', 'fresh'):
        raise ValueError('Only predeclared finite M5 QA jobs are supported')
    output = QA / run_id
    output.mkdir(exist_ok=False)
    report = dict(status='started', run_id=run_id, mode=mode, pid=os.getpid(),
                  scope='M5 engineering state/capture evidence; no biological/optical qualification or RGB identity inference')
    try:
        import omni.kit.app
        from omni.kit.viewport.utility import get_active_viewport
        from cris.madil.render_service.scene_diagnostics import restore_checkpoint, checkpoint_scene
        app = omni.kit.app.get_app()
        for _ in range(90):
            await app.next_update_async()
        baseline = json.loads((QA/'live_before/checkpoint.json').read_text())
        assert digest(Path(baseline['directory'])/'scene.usdc') == baseline['scene_sha256']
        restored = await restore_checkpoint(baseline['checkpoint_id'])
        write(output/'checkpoint_restore.json', restored)
        assert restored['ok'], restored
        report['runtime'] = dict(build=app.get_build_version(), pid=os.getpid())
        await asyncio.wait_for(get_active_viewport().wait_for_rendered_frames(3), timeout=90)
        await asyncio.wait_for(suite(run_id, mode, report), timeout=7200)
        report['final_checkpoint'] = await checkpoint_scene()
    except BaseException as error:
        report.update(status='failed', error=str(error), traceback=traceback.format_exc())
    finally:
        write(output/'result.json', report)

