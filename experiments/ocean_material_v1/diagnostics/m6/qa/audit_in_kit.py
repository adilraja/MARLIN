"""One-viewport M6 animal comparisons, preset export, fresh reload and rollback."""
import asyncio
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[3]
RUN = ROOT / 'runs/attempt01'
PACKAGE = REPO / 'experiments/ocean_material_v1/presets/engineering_v1'
ANIMAL = '/World/Cetaceans/Dolphin_001'
CAMERA = '/World/MarlinOceanM6Camera'
spec = importlib.util.spec_from_file_location('marlin_m6_audit_helpers', ROOT / 'qa/audit_helpers.py')
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
plain, write, sha, state_record = (getattr(helpers, name) for name in ('plain', 'write', 'sha', 'state_record'))


def animal_record(stage):
    from pxr import Usd, UsdGeom
    state = state_record(stage)['prim_hashes']
    children = {path: value for path, value in state.items() if path.startswith(ANIMAL + '/')}
    prim = stage.GetPrimAtPath(ANIMAL)
    root = {a.GetName(): plain(a.Get()) for a in prim.GetAuthoredAttributes()
            if a.GetName() != 'xformOp:translate'}
    bbox = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ['default', 'render', 'proxy']).ComputeWorldBound(prim).ComputeAlignedRange()
    return dict(identity_sha256=sha(json.dumps(dict(root=root, children=children), sort_keys=True).encode()),
                world_bounds_min=list(bbox.GetMin()), world_bounds_max=list(bbox.GetMax()),
                root_xform_ops={a.GetName(): plain(a.Get()) for a in prim.GetAttributes() if a.GetName().startswith('xformOp')})


def projected_box(record, projection):
    import numpy as np
    lo, hi = record['world_bounds_min'], record['world_bounds_max']
    matrix = np.array(projection['capture_view_matrix']) @ np.array(projection['capture_projection_matrix'])
    points = np.array([(x, y, z, 1) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]) @ matrix
    if np.any(points[:, 3] <= 0):
        raise ValueError('Animal bounds behind camera')
    ndc = points[:, :3] / points[:, 3:4]
    xs, ys = (ndc[:, 0]+1)*256, (1-ndc[:, 1])*192
    return [float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())]


async def suite():
    import carb.settings
    import numpy as np
    import omni.kit.app
    import omni.timeline
    import omni.usd
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade
    from omni.kit.viewport.utility import get_active_viewport, capture_viewport_to_file
    from cris.madil.render_service import calibration_capture, capture_state, ocean
    from cris.madil.render_service.hidef_marine import (freeze_stage, open_snapshot, gpu_preflight,
        settings_record, restore_settings, same_settings, asset_dependencies)
    from cris.madil.render_service.ocean_medium import select_preset, PresetRequest, author_frame, configuration, surface_arrays
    from cris.madil.render_service.water_diagnostics import DiagnosticCamera
    from cris.madil.render_service.calibration_geometry import build_camera
    from cris.madil.render_service.capture_projection import record_projection
    from cris.madil.render_service.water_medium_diagnostics import setup_medium_viewport, MediumRequest, capture_hdr

    app = omni.kit.app.get_app()
    context = omni.usd.get_context()
    live = context.get_stage()
    viewport = get_active_viewport()
    if live is None or viewport is None or calibration_capture._busy:
        raise RuntimeError('An idle restored live scene and viewport are required')
    retained = Usd.StageCache()
    retained.Insert(live)
    saved = dict(camera=str(viewport.camera_path), resolution=tuple(viewport.resolution), fill=viewport.fill_frame,
                 globals=settings_record(), state=state_record(live), paused=capture_state.paused,
                 selection=context.get_selection().get_selected_prim_paths())
    calibration_capture._busy = True
    capture_state.paused = True
    timeline = omni.timeline.get_timeline_interface()
    playing, seconds = timeline.is_playing(), timeline.get_current_time()
    timeline.pause()
    settings = carb.settings.get_settings()
    guide_paths = [f'/persistent/app/viewport/{viewport.id}/guide/{name}/visible' for name in ('grid', 'axis', 'selection', 'boundingBox')]
    guide_paths += ['/app/viewport/outline/enabled', '/app/viewport/boundingBoxes/enabled', '/persistent/app/viewport/displayOptions']
    guides = {key: settings.get(key) for key in guide_paths}
    records = []
    try:
        gpu_preflight(768)
        frozen, sampled = freeze_stage(live, Usd.TimeCode.Default())
        retained.Insert(frozen)
        local_ocean = copy.deepcopy(ocean._ocean_animation_state)
        local_ocean['elapsed'], local_ocean['accumulator'] = 0, 0
        ok, error = await context.attach_stage_async(frozen)
        if not ok:
            raise RuntimeError(error)
        mesh = UsdGeom.Mesh(frozen.GetPrimAtPath('/World/Ocean'))
        select_preset(frozen, PresetRequest(selection='original'))
        points, normals, extent = ocean._calculate_animated_ocean(local_ocean, 0)
        author_frame(mesh, points, normals, extent)
        top_reference = np.array(mesh.GetPointsAttr().Get(), dtype=np.float32)
        unit = UsdGeom.GetStageMetersPerUnit(frozen)
        initial = animal_record(frozen)
        lo, hi = np.array(initial['world_bounds_min']), np.array(initial['world_bounds_max'])
        centre = (lo+hi)/2
        t = frozen.GetPrimAtPath(ANIMAL).GetAttribute('xformOp:translate').Get()
        if t is None:
            raise RuntimeError('Expected the existing animal translation op')
        original_translation = Gf.Vec3d(*t)
        old_ocean = ocean._ocean_animation_state
        try:
            ocean._ocean_animation_state = local_ocean
            local_height = ocean._sample_ocean_surface_height(float(centre[0]), float(centre[2]))
        finally:
            ocean._ocean_animation_state = old_ocean
        shifts = dict(above=float(top_reference[:, 1].max()+.25/unit-lo[1]),
                      intersecting=float(local_height-centre[1]),
                      below=float(top_reference[:, 1].min()-.25/unit-hi[1]))
        camera_height = max(6., float((hi-lo).max()*unit)*2.5)
        trials = []
        for _ in range(12):
            camera_config = DiagnosticCamera(meters_per_scene_unit=unit, image_width_px=512, image_height_px=384,
                focal_length_mm=35, pixel_pitch_um=40, height_above_target_m=camera_height,
                target_plane_y_m=0, target_width_m=float((hi-lo).max()*unit)/2,
                target_height_m=float((hi-lo).max()*unit)/2, pitch_deg=40)
            camera = build_camera(frozen, camera_config, CAMERA, (float(centre[0]*unit), 0, float(centre[2]*unit)))
            viewport.fill_frame = False
            viewport.resolution = (512, 384)
            viewport.camera_path = CAMERA
            for _ in range(3):
                await app.next_update_async()
            setup_medium_viewport(viewport, MediumRequest(renderer='PathTracing'), hide_overlays=False)
            camera.GetClippingRangeAttr().Set(Gf.Vec2f(.01/unit, max(25., 4*camera_height)/unit))
            projection = record_projection(frozen, viewport)
            boxes = {}
            for pose, shift in shifts.items():
                adjusted = dict(world_bounds_min=(lo+[0, shift, 0]).tolist(), world_bounds_max=(hi+[0, shift, 0]).tolist())
                boxes[pose] = projected_box(adjusted, projection)
            trials.append(dict(height_m=camera_height, boxes=boxes))
            if all(b[0]>=24 and b[1]>=24 and b[2]<=488 and b[3]<=360 for b in boxes.values()):
                break
            camera_height *= 1.15
        else:
            raise RuntimeError('Declared geometric framing did not fit all poses')
        settings.set('/rtx/fog/enabled', False)
        settings.set('/exts/cris.madil.render_service/underwaterCue/enabled', False)
        for key in guide_paths:
            settings.set(key, 0 if key.endswith('displayOptions') else False)
        context.get_selection().clear_selected_prim_paths()
        for _ in range(30):
            await app.next_update_async()
        viewport.resolution = (512, 384)
        active_globals = settings_record()
        write(RUN/'preparation.json', dict(initial_animal=initial, world_units_m=unit,
              frozen_sampled_attributes=sampled, ocean_phase_seconds=0,
              frozen_ocean_y_range_units=[float(top_reference[:, 1].min()), float(top_reference[:, 1].max())],
              centre_surface_height_units=local_height, pose_y_shifts_units=shifts,
              camera_framing_trials=trials, camera_config=camera_config.metadata(),
              camera_physical_far_m=max(25.,4*camera_height), dependencies=asset_dependencies(frozen)))

        async def capture(label, pose, selection):
            directory = RUN / label
            directory.mkdir(exist_ok=False)
            started = time.monotonic()
            try:
                gpu = gpu_preflight(768)
                await asyncio.wait_for(viewport.wait_for_rendered_frames(64), timeout=30)
                stage = context.get_stage()
                projection = record_projection(stage, viewport)
                animal = animal_record(stage)
                assert animal['identity_sha256'] == initial['identity_sha256']
                box = projected_box(animal, projection)
                before = settings_record()
                for filename in ('warmup.png', 'rgb.png'):
                    job = capture_viewport_to_file(viewport, file_path=str(directory/filename))
                    await job.wait_for_result(completion_frames=5)
                hdr = await capture_hdr(viewport, directory)
                snap, count = freeze_stage(stage, Usd.TimeCode.Default())
                snap.GetRootLayer().Export(str(directory/'scene.usdc'))
                surface = UsdGeom.Mesh(stage.GetPrimAtPath('/World/Ocean'))
                config = configuration(surface.GetPrim())
                top = surface_arrays(surface, config)[0] if config else surface.GetPointsAttr().Get()
                assert np.array_equal(np.asarray(top,dtype=np.float32), top_reference)
                state = state_record(stage)
                record = dict(label=label, pose=pose, selection=selection, gpu_before=gpu,
                    elapsed_seconds=time.monotonic()-started, rendered_frame_wait_completed=64,
                    configured_sample_count_is_not_hardware_telemetry=True, projection=projection,
                    animal=animal, direct_geometric_bbox_xyxy_px=box,
                    annotation_definition='Direct projection of world-space render-purpose 3D bounds; no refraction or visible-mask claim',
                    hdr=hdr, global_settings=before, scene_sha256=sha((directory/'scene.usdc').read_bytes()),
                    scene_state=state, ocean_top_points_unchanged=True,
                    bound_material=str(UsdShade.MaterialBindingAPI(surface.GetPrim()).ComputeBoundMaterial()[0].GetPath()),
                    ocean_vertices=len(surface.GetPointsAttr().Get()), ocean_faces=len(surface.GetFaceVertexCountsAttr().Get()),
                    preset_configuration=config, layer_identifier=stage.GetRootLayer().identifier)
                write(directory/'metadata.json',record)
                records.append(record)
                write(RUN/'capture_records.json',records)
                return directory
            except BaseException as exc:
                write(directory/'failure.json',dict(error=str(exc) or type(exc).__name__,traceback=traceback.format_exc(),elapsed_seconds=time.monotonic()-started))
                raise

        for pose in ('above', 'intersecting', 'below'):
            translation = Gf.Vec3d(original_translation)
            translation[1] += shifts[pose]
            UsdGeom.XformCommonAPI(frozen.GetPrimAtPath(ANIMAL)).SetTranslate(translation)
            select_preset(frozen, PresetRequest(selection='original'))
            await asyncio.wait_for(capture('original_'+pose, pose, 'original'), timeout=60)
            choice = select_preset(frozen, PresetRequest(selection='engineering_v1',configure_renderer=False))
            assert choice['ok']
            directory = await asyncio.wait_for(capture('engineering_'+pose, pose, 'engineering_v1'), timeout=60)
            if pose == 'intersecting':
                PACKAGE.mkdir(parents=True,exist_ok=False)
                shutil.copyfile(REPO/'source/extensions/cris.madil.render_service/config/ocean_medium_engineering_v1.json', PACKAGE/'parameters.json')
                shutil.copyfile(directory/'scene.usdc', PACKAGE/'demonstration_scene.usdc')
                bound = UsdShade.MaterialBindingAPI(mesh.GetPrim()).ComputeBoundMaterial()[0]
                layer = Sdf.Layer.CreateNew(str(PACKAGE/'material.usda'))
                Sdf.CreatePrimInLayer(layer, bound.GetPath().GetParentPath())
                flattened = frozen.Flatten()
                Sdf.CopySpec(flattened, bound.GetPath(), layer, bound.GetPath())
                layer.Save()
                write(PACKAGE/'runtime_dependencies.json', dict(dependencies=asset_dependencies(frozen),
                    water_material_texture_assets=[], mdl_source_asset='OmniSurface.mdl', mdl_subidentifier='OmniSurface',
                    runtime_vendor_files_inspected=False, preset_choice=choice))
            rollback = select_preset(frozen, PresetRequest(selection='original'))
            assert rollback['ok']
        snapshot = PACKAGE/'demonstration_scene.usdc'
        snapshot_sha = sha(snapshot.read_bytes())
        reloaded = open_snapshot(snapshot)
        retained.Insert(reloaded)
        ok,error = await context.attach_stage_async(reloaded)
        if not ok:
            raise RuntimeError(error)
        restore_settings(active_globals)
        viewport.camera_path=CAMERA
        viewport.fill_frame=False
        viewport.resolution=(512,384)
        for _ in range(30):
            await app.next_update_async()
        viewport.resolution=(512,384)
        setup_medium_viewport(viewport,MediumRequest(renderer='PathTracing'),hide_overlays=False)
        UsdGeom.Camera(reloaded.GetPrimAtPath(CAMERA)).GetClippingRangeAttr().Set(Gf.Vec2f(.01/unit,max(25.,4*camera_height)/unit))
        assert configuration(reloaded.GetPrimAtPath('/World/Ocean'))
        await asyncio.wait_for(capture('reload_intersecting','intersecting','engineering_v1'),timeout=60)
        rollback=select_preset(reloaded,PresetRequest(selection='original'))
        assert rollback['ok']
        await asyncio.wait_for(capture('rollback_intersecting','intersecting','original'),timeout=60)
        assert sha(snapshot.read_bytes())==snapshot_sha
        write(RUN/'reload_and_rollback.json',dict(saved_scene_sha256=snapshot_sha,
              snapshot_bytes_preserved=True, fresh_layer_identifier=reloaded.GetRootLayer().identifier,
              saved_selection_survived_reload=True, rollback=rollback))
    finally:
        capture_state.paused=True
        ok,error=await context.attach_stage_async(live)
        if not ok:
            raise RuntimeError('Live-stage restoration failed: '+error)
        restore_settings(saved['globals'])
        restore_settings(guides)
        viewport.camera_path=saved['camera']
        viewport.resolution=saved['resolution']
        viewport.fill_frame=saved['fill']
        context.get_selection().set_selected_prim_paths(saved['selection'],False)
        for _ in range(10):
            await app.next_update_async()
        checks=dict(stage=context.get_stage()==live, camera=str(viewport.camera_path)==saved['camera'],
                    resolution=tuple(viewport.resolution)==saved['resolution'], fill=viewport.fill_frame==saved['fill'],
                    renderer_settings=same_settings(settings_record(),saved['globals']),
                    scene=state_record(live)==saved['state'])
        write(RUN/'restoration.json',checks)
        timeline.set_current_time(seconds)
        if playing:
            timeline.play()
        capture_state.paused=saved['paused']
        calibration_capture._busy=False
        retained.Clear()
        assert all(checks.values()),checks


async def main():
    import omni.kit.app
    from omni.kit.viewport.utility import get_active_viewport
    from cris.madil.render_service.scene_diagnostics import restore_checkpoint,checkpoint_scene
    from cris.madil.render_service.scene_setup import setup_marine_scene,MarineSceneSetupDataModel
    from cris.madil.render_service.ocean_medium_diagnostics import regression
    app=omni.kit.app.get_app()
    RUN.mkdir(parents=True,exist_ok=False)
    try:
        for _ in range(90):
            await app.next_update_async()
        checkpoint=json.loads((ROOT/'qa/pre_work_checkpoint.json').read_text())
        assert sha((Path(checkpoint['directory'])/'scene.usdc').read_bytes())==checkpoint['scene_sha256']
        restored=await restore_checkpoint(checkpoint['checkpoint_id'])
        write(RUN/'checkpoint_restore.json',restored)
        assert restored['ok']
        await asyncio.wait_for(get_active_viewport().wait_for_rendered_frames(3),timeout=90)
        setup=await setup_marine_scene(MarineSceneSetupDataModel(start_swimming=False))
        write(RUN/'initial_live_setup.json',setup)
        assert setup['ok']
        result=await asyncio.wait_for(regression(),timeout=90)
        assert result['ok'],result
        # The existing regression chooses a new unsealed output directory.
        # Adopt only that newly created evidence; old M4 files remain untouched.
        source=Path(result['directory'])
        shutil.move(str(source),str(RUN/'runtime_regression'))
        write(RUN/'runtime_regression_call.json',dict(response=result,adopted_directory=str(RUN/'runtime_regression')))
        write(RUN/'runtime.json',dict(kit_build=app.get_build_version(),extensions=[{k:e.get(k) for k in ('id','name','version','enabled')}
              for e in app.get_extension_manager().get_extensions() if e.get('enabled')]))
        try:
            await asyncio.wait_for(suite(),timeout=300)
        finally:
            setup=await setup_marine_scene(MarineSceneSetupDataModel(start_swimming=False))
            write(RUN/'final_live_setup.json',setup)
            write(RUN/'final_checkpoint.json',await checkpoint_scene())
        write(RUN/'done.json',dict(ok=True,pixel_analysis_pending=True,human_review_status='pending',
              named_reviewer='MAR',phase_note='Controllers reconstructed after checkpointed process restart; procedural phase/history not preserved'))
    except BaseException as exc:
        write(RUN/'audit_failure.json',dict(error=str(exc) or type(exc).__name__,traceback=traceback.format_exc()))


asyncio.ensure_future(main())
