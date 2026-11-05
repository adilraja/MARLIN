"""Fixed local M4 jobs on a frozen copy, one viewport, always restore live stage."""
import asyncio
import copy
import hashlib
import json
import math
from pathlib import Path
import time
import traceback

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[3]
BASE=ROOT.parents[1]
MEDIA=REPO/'artifacts/gama_dolphin_behaviour_v1/m4'
CAMERA='/MarlinM4ReviewCamera'


def plain(value):
    if value is None or isinstance(value,(str,bool,int,float)):return value
    if hasattr(value,'GetReal'):return [float(value.GetReal()),*map(float,value.GetImaginary())]
    try:return [plain(v) for v in value]
    except TypeError:return str(value)


def write(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2);f.write('\n')


def geometry(stage,actor_path):
    import numpy as np
    from pxr import Gf,Usd,UsdGeom,UsdSkel,Vt
    cache=UsdSkel.Cache();model=stage.GetPrimAtPath(actor_path+'/Model')
    for p in Usd.PrimRange(model):
        if p.IsA(UsdSkel.Root):cache.Populate(UsdSkel.Root(p),Usd.PrimDefaultPredicate)
    skel=next(p for p in Usd.PrimRange(model) if p.IsA(UsdSkel.Skeleton))
    transforms=cache.GetSkelQuery(UsdSkel.Skeleton(skel)).ComputeSkinningTransforms(Usd.TimeCode.Default())
    world=UsdGeom.Xformable(skel).ComputeLocalToWorldTransform(Usd.TimeCode.Default());points=[]
    for p in Usd.PrimRange(model):
        if p.IsA(UsdGeom.Mesh):
            vertices=Vt.Vec3fArray(UsdGeom.Mesh(p).GetPointsAttr().Get())
            if not cache.GetSkinningQuery(p).ComputeSkinnedPoints(transforms,vertices,Usd.TimeCode.Default()):raise ValueError('CPU skinning failed in native process')
            points.extend([list(world.Transform(Gf.Vec3d(v))) for v in vertices])
    return np.array(points)


async def execute(job):
    import numpy as np
    import carb.settings
    import omni.kit.app
    import omni.timeline
    import omni.usd
    from pxr import Gf,Sdf,Usd,UsdGeom
    from omni.kit.viewport.utility import get_active_viewport,capture_viewport_to_file
    from cris.madil.render_service import calibration_capture,capture_state,ocean
    from cris.madil.render_service.hidef_marine import freeze_stage,settings_record,restore_settings,same_settings,gpu_preflight
    from cris.madil.render_service.ocean_medium import select_preset,PresetRequest,author_frame
    from cris.madil.render_service.capture_projection import record_projection
    from cris.madil.render_service.water_medium_diagnostics import setup_medium_viewport,MediumRequest
    from cris.madil.gama_bridge.actor_animated_v3 import AnimatedBottlenoseActor,ACTOR

    job_id=job['job_id'];mode=job['mode']
    if not job_id.replace('_','').isalnum() or mode not in ('smoke','review','dry'):raise ValueError('Only fixed M4 review jobs are supported')
    profile_name=job.get('capture_profile','native_capture_v1')
    if not profile_name.replace('_','').isalnum():raise ValueError('Invalid local capture profile')
    profile_path=ROOT/(profile_name+'.json');profile=json.loads(profile_path.read_text())
    if not 1e-6<=profile['exposure_time_s']<=1 or not .5<=profile['exposure_fstop']<=32 or not 1<=profile['exposure_iso']<=6400:
        raise ValueError('Diagnostic camera exposure outside declared engineering range')
    result_dir=ROOT/'native_runs'/job_id;result_dir.mkdir(parents=True,exist_ok=False)
    directory=MEDIA/job_id;directory.mkdir(parents=True,exist_ok=False)
    app=omni.kit.app.get_app();context=omni.usd.get_context();live=context.get_stage();viewport=get_active_viewport()
    if live is None or viewport is None or calibration_capture._busy:raise ValueError('An idle live scene and viewport are required')
    retained=Usd.StageCache();retained.Insert(live)
    timeline=omni.timeline.get_timeline_interface();settings=carb.settings.get_settings()
    guides=[f'/persistent/app/viewport/{viewport.id}/guide/{n}/visible' for n in ('grid','axis','selection','boundingBox')]
    guides+=['/app/viewport/outline/enabled','/app/viewport/boundingBoxes/enabled','/persistent/app/viewport/displayOptions',f'/persistent/app/viewport/{viewport.id}/fillViewport']
    saved=dict(camera=str(viewport.camera_path),resolution=list(viewport.resolution),fill=viewport.fill_frame,settings=settings_record(),
        guides={k:settings.get(k) for k in guides},selection=context.get_selection().get_selected_prim_paths(),
        playing=timeline.is_playing(),time=timeline.get_current_time(),paused=capture_state.paused)
    report=dict(status='started',job=job,media_directory=str(directory),frames=[],gpu=[],restoration=None,
        scope='Native preview, frozen ocean phase 0; explicit recorded GAMA state; no RGB/radiometric/sample-count certification',dry_geometry_diagnostic=mode=='dry',
        capture_profile=profile,capture_profile_sha256=hashlib.sha256(profile_path.read_bytes()).hexdigest())
    calibration_capture._busy=True;capture_state.paused=True;timeline.pause();owner=None
    try:
        report['gpu'].append(gpu_preflight(768))
        frozen,_=freeze_stage(live,Usd.TimeCode.Default());retained.Insert(frozen)
        ok,error=await context.attach_stage_async(frozen)
        if not ok:raise RuntimeError(error)
        # Diagnostic isolation applies only to this disposable frozen copy.
        # The experimental actor lives outside /World/Cetaceans.
        background=frozen.GetPrimAtPath('/World/Cetaceans')
        if background:UsdGeom.Imageable(background).MakeInvisible()
        viewport.fill_frame=False;settings.set_bool(guides[-1],False);viewport.resolution=(512,384)
        camera=UsdGeom.Camera.Define(frozen,CAMERA)
        camera.CreateFocalLengthAttr(35);camera.CreateHorizontalApertureAttr(30.72);camera.CreateVerticalApertureAttr(23.04)
        camera.CreateFStopAttr(0);camera.CreateClippingRangeAttr(Gf.Vec2f(1,100000))
        camera.MakeMatrixXform();viewport.camera_path=CAMERA
        for _ in range(12):await app.next_update_async()
        viewport.resolution=(512,384)
        local_ocean=copy.deepcopy(ocean._ocean_animation_state);local_ocean['elapsed']=0.;local_ocean['accumulator']=0.
        mesh=UsdGeom.Mesh(frozen.GetPrimAtPath('/World/Ocean'))
        select_preset(frozen,PresetRequest(selection='original'))
        arrays=ocean._calculate_animated_ocean(local_ocean,0);author_frame(mesh,*arrays)
        water_hi=float(np.array(arrays[0])[:,1].max());water_lo=float(np.array(arrays[0])[:,1].min())
        old_ocean=ocean._ocean_animation_state
        try:
            ocean._ocean_animation_state=local_ocean
            report['preset']=select_preset(frozen,PresetRequest(selection='engineering_v1',configure_renderer=True))
        finally:ocean._ocean_animation_state=old_ocean
        setup_medium_viewport(viewport,MediumRequest(renderer='PathTracing'),hide_overlays=False)
        for key,value in {'exposure:time':profile['exposure_time_s'],'exposure:fStop':profile['exposure_fstop'],
                          'exposure:iso':profile['exposure_iso'],'exposure:responsivity':profile['exposure_responsivity']}.items():
            camera.GetPrim().GetAttribute(key).Set(value)
        for k in guides[:-1]:settings.set(k,0 if k.endswith('displayOptions') else False)
        context.get_selection().clear_selected_prim_paths()
        if mode=='dry':mesh.MakeInvisible()
        owner=AnimatedBottlenoseActor();token=owner.acquire(frozen,'Bottlenose_001')['ownership_token']
        source=json.loads((BASE/'trajectories/m3_ref_a01/trajectory.json').read_text());index=-1
        unit=UsdGeom.GetStageMetersPerUnit(frozen)
        initial=geometry(frozen,ACTOR);inverse=owner.expected_matrix.GetInverse()
        root_points=np.array([list(inverse.Transform(Gf.Vec3d(*p))) for p in initial]);rest_center=(root_points.min(axis=0)+root_points.max(axis=0))/2
        report.update(geometry_vertices=len(initial),water_surface_bounds_units=[water_lo,water_hi],rest_camera_target_offset_units=rest_center.tolist(),renderer_settings=settings_record(),resolution=[512,384],timeline_before=saved['time'])

        def seek(t):
            nonlocal index
            final=min(len(source)-1,int(math.ceil(t/source[0]['simulation_step_s']-1e-10)))
            if index>final or (index>=0 and t<max(0,index-1)*source[0]['simulation_step_s']):
                owner.reset(frozen,token);index=-1
            while index<final:
                index+=1;owner.apply(frozen,token,source[index])
            owner.evaluate(frozen,token,t)

        async def shot(t,view,filename,diagnostic=False):
            seek(t);frame=owner.frame;a=frame['agent'];h=math.radians(a['heading_deg'])
            centre=owner.expected_matrix.Transform(Gf.Vec3d(*rest_center))
            if view=='top':eye=Gf.Vec3d(centre[0],max(4.5/unit,centre[1]+4.5/unit),centre[2]);up=Gf.Vec3d(0,0,1)
            else:
                right,forward=(3.8,0.) if view=='close' else (3.2,2.2)
                y=centre[1]+(.5 if view=='close' else 2.0)/unit if mode=='dry' else max(water_hi+1./unit,centre[1]+(2.0 if view=='close' else 3.0)/unit)
                eye=Gf.Vec3d(centre[0]+(right*math.cos(h)+forward*math.sin(h))/unit,y,centre[2]+(-right*math.sin(h)+forward*math.cos(h))/unit);up=Gf.Vec3d(0,1,0)
            camera.GetPrim().GetAttribute('xformOp:transform').Set(Gf.Matrix4d().SetLookAt(eye,centre,up).GetInverse())
            if mode!='dry' and eye[1]<=water_hi:raise ValueError('Review camera entered water bounds')
            for _ in range(8 if diagnostic else 3):await app.next_update_async()
            await asyncio.wait_for(viewport.wait_for_rendered_frames(3),timeout=30)
            if diagnostic:
                warm=capture_viewport_to_file(viewport,file_path=str(directory/'warmup.png'));await warm.wait_for_result(completion_frames=5)
            path=directory/filename
            capture=capture_viewport_to_file(viewport,file_path=str(path));await capture.wait_for_result(completion_frames=5)
            # Completion may precede the writer thread's final filesystem flush.
            # A unique image must have its complete PNG footer before pose advance.
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                data=path.read_bytes() if path.is_file() else b''
                if data.startswith(b'\x89PNG\r\n\x1a\n') and data.endswith(b'\x00\x00\x00\x00IEND\xaeB\x60\x82'):break
                await app.next_update_async()
            else:raise ValueError('Native capture did not finish a complete PNG')
            pose=owner.pose.animation
            record=dict(file=filename,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),simulation_time_s=t,view=view,
                state=a['behavioural_state'],frame=frame,pose_controls=owner.pose_controls,root_matrix=plain(owner.expected_matrix),
                joint_translations=plain(pose.GetTranslationsAttr().Get()),joint_rotations=plain(pose.GetRotationsAttr().Get()),joint_scales=plain(pose.GetScalesAttr().Get()),
                camera_position_m=list(eye*unit),camera_above_surface_bounds=bool(eye[1]>water_hi),projection=record_projection(frozen,viewport),body_immutable_signature=owner.expected_body)
            record['camera_exposure']={key:plain(camera.GetPrim().GetAttribute(key).Get()) for key in
                ('exposure','exposure:time','exposure:fStop','exposure:iso','exposure:responsivity','omni:rtx:autoExposure:enabled')}
            if diagnostic:
                vertices=geometry(frozen,ACTOR)*unit;lo,hi=vertices.min(axis=0),vertices.max(axis=0)
                record['evaluated_skin_bounds_m']=[lo.tolist(),hi.tolist()]
                record['surface_relation_bounds']='fully_below_wave_band' if hi[1]<water_lo*unit else 'fully_above_wave_band' if lo[1]>water_hi*unit else 'overlaps_wave_height_band; inspect actual contact visually'
                record['vertices_above_mean_sea_level']=int((vertices[:,1]>0).sum())
                snapshot=directory/(path.stem+'.usda');owner.layer.Export(str(snapshot))
                reopened=Usd.Stage.Open(str(snapshot));UsdGeom.SetStageUpAxis(reopened,'Y');UsdGeom.SetStageMetersPerUnit(reopened,unit);reopened.GetRootLayer().Save()
                record['pose_snapshot']=snapshot.name;record['pose_snapshot_sha256']=hashlib.sha256(snapshot.read_bytes()).hexdigest()
            write(directory/(path.stem+'.json'),record);report['frames'].append({k:record[k] for k in ('file','sha256','simulation_time_s','view','state')})
            if len(report['frames'])%20==0:
                report['gpu'].append(gpu_preflight(768))
                (result_dir/'progress.json').write_text(json.dumps(dict(frames=len(report['frames']),latest_time_s=t,latest_view=view))+'\n')

        # Settle actual file/texture streaming before the first diagnostic image.
        quiet=None;start=time.monotonic()
        while time.monotonic()-start<90:
            loading=context.get_stage_loading_status()
            if loading[2]==0:
                if quiet is None:quiet=time.monotonic()
                if time.monotonic()-quiet>=2:break
            else:quiet=None
            await app.next_update_async()
        else:raise RuntimeError('Stage streaming did not settle')
        if mode=='smoke':
            shots=[(6.,'top'),(6.,'oblique'),(6.,'close'),(6.625,'close'),(30.,'close'),(56.,'close')]
        else:
            times=[6.,6.3125,6.625,6.9375,16.,30.,42.,56.] if mode=='dry' else json.loads((ROOT/'locked_plan.json').read_text())['diagnostic_simulation_times_s']
            shots=[(float(t),view) for t in times for view in ('top','oblique','close')]
        for n,(t,view) in enumerate(shots):await shot(t,view,f'shot_{n:03d}_{view}.png',True)
        if mode in ('review','dry'):
            plan=json.loads((ROOT/'locked_plan.json').read_text())['review_clip'];fps=plan['fps'];frame_index=0
            for segment,(first,last) in enumerate(plan['simulation_windows_s']):
                for i in range(round((last-first)*fps)):
                    await shot(first+i/fps,'close',f'clip_{frame_index:05d}.png')
                    report['frames'][-1].update(segment=segment,edited_cut=i==0,playback_fps=fps);frame_index+=1
        report['status']='passed'
    except BaseException as error:
        report.update(status='failed',error=str(error),traceback=traceback.format_exc())
    finally:
        try:
            if owner is not None:owner.close()
            ok,error=await context.attach_stage_async(live)
            if not ok:raise RuntimeError(error)
            viewport.camera_path=saved['camera'];viewport.fill_frame=saved['fill'];viewport.resolution=tuple(saved['resolution'])
            restore_settings(saved['settings']);restore_settings(saved['guides'])
            context.get_selection().set_selected_prim_paths(saved['selection'],False)
            timeline.set_current_time(saved['time'])
            if saved['playing']:timeline.play()
            for _ in range(12):await app.next_update_async()
            restored=settings_record()
            report['restoration']=dict(stage=context.get_stage()==live,camera=str(viewport.camera_path)==saved['camera'],resolution=list(viewport.resolution)==saved['resolution'],fill_frame=viewport.fill_frame==saved['fill'],settings=all(same_settings(v,restored[k]) for k,v in saved['settings'].items()),timeline=timeline.get_current_time()==saved['time'])
            if not all(report['restoration'].values()):report['status']='failed'
        except BaseException:
            report['restoration_error']=traceback.format_exc();report['status']='failed'
        finally:
            capture_state.paused=saved['paused'];calibration_capture._busy=False
        write(result_dir/'result.json',report);write(directory/'result.json',report)
        retained.Clear()


async def worker():
    jobs=ROOT/'native_jobs';jobs.mkdir(exist_ok=True)
    seen={p.name for p in jobs.glob('*.json') if (ROOT/'native_runs'/p.stem/'result.json').is_file()}
    write(ROOT/'native_worker_ready_attempt06.json',dict(ready=True,allowed_modes=['smoke','review','dry'],read_only_job_poll=True))
    import omni.kit.app
    while True:
        for path in sorted(jobs.glob('*.json')):
            if path.name in seen:continue
            seen.add(path.name)
            try:await execute(json.loads(path.read_text()))
            except BaseException as error:
                write(ROOT/(path.stem+'_worker_failure.json'),dict(error=str(error),traceback=traceback.format_exc()))
        for _ in range(30):await omni.kit.app.get_app().next_update_async()
