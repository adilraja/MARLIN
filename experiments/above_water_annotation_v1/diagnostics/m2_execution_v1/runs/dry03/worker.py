"""Allowlisted M2 dry captures in one owned, immutable Kit scene/product."""
import asyncio
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time
import traceback

import numpy as np
from pxr import Gf, Sdf, Semantics, Usd, UsdGeom, UsdLux, UsdRender, UsdSkel, Vt
import carb.settings
import omni.kit.app
import omni.timeline
import omni.usd
import omni.replicator.core as rep
from omni.replicator.core.bindings._omni_replicator_exrwriter import save_exr_to_stream, load_exr_from_stream
from omni.kit.viewport.utility import get_active_viewport_window
from PIL import Image

REPO = Path('/home/madil/kit-app-template')
BASE = REPO/'experiments/above_water_annotation_v1'
OUT = Path(os.environ['ANNOTATION_EXECUTION_OUTPUT'])
LEDGER = BASE/'diagnostics/m2_execution_v1/attempt_ledger.json'
DECL = json.loads((BASE/'declarations/capture_declaration.json').read_text())
CONTRACT = json.loads((BASE/'contracts/capture_contract.json').read_text())
ACTOR = CONTRACT['target']['planned_owned_root']
UNIT = .01
sys.path.insert(0, str(REPO/'source/extensions/cris.madil.render_service/cris/madil/render_service'))
from capture_projection import record_product_projection


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def plain(v):
    if isinstance(v, dict): return {str(k): plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)): return [plain(x) for x in v]
    if isinstance(v, np.ndarray): return v.tolist()
    if isinstance(v, np.generic): return v.item()
    if isinstance(v, (str, float, int, bool)) or v is None: return v
    try: return [plain(x) for x in v]
    except TypeError: return str(v)


def save(p, d):
    p.write_text(json.dumps(plain(d), indent=2, allow_nan=False)+'\n')


def start_attempt(item, reserve):
    ledger = json.loads(LEDGER.read_text())
    assert len(ledger['attempts']) < 144
    assert sum(x['reserve'] for x in ledger['attempts']) < 24 if reserve else True
    aid = 'attempt_%03d' % (len(ledger['attempts'])+1)
    folder = BASE/'diagnostics/m2_execution_v1/captures'/aid
    folder.mkdir(parents=True, exist_ok=False)
    entry = dict(attempt_id=aid, declaration_id=item['id'], reserve=reserve,
                 run=str(OUT.relative_to(BASE)), folder=str(folder.relative_to(BASE)),
                 started_utc=datetime.now(timezone.utc).isoformat(), status='started')
    ledger['attempts'].append(entry); save(LEDGER, ledger)
    return folder


def finish_attempt(folder, status, reason=None):
    ledger = json.loads(LEDGER.read_text()); e = next(x for x in ledger['attempts'] if x['attempt_id'] == folder.name)
    e.update(status=status, reason=reason, finished_utc=datetime.now(timezone.utc).isoformat())
    save(LEDGER, ledger)


def label(prim, value):
    api = Semantics.SemanticsAPI.Apply(prim, 'M2Class')
    api.CreateSemanticTypeAttr().Set('class'); api.CreateSemanticDataAttr().Set(value)


def mesh(stage, path, points, colour, semantic=None):
    m = UsdGeom.Mesh.Define(stage, path)
    m.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*p) for p in points]))
    m.CreateFaceVertexCountsAttr([4]); m.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
    m.CreateSubdivisionSchemeAttr('none'); m.CreateDoubleSidedAttr(True)
    m.CreateDisplayColorAttr([Gf.Vec3f(*colour)])
    if semantic: label(m.GetPrim(), semantic)
    return m


def project(points, view, projection):
    p = np.c_[points, np.ones(len(points))] @ view @ projection
    if np.any(p[:, 3] <= 0): raise ValueError('Unsupported near/behind-camera geometry')
    p = p[:, :3]/p[:, 3:4]
    return np.c_[(p[:, 0]+1)*256, (1-p[:, 1])*192]


def skin(stage):
    model = stage.GetPrimAtPath(ACTOR+'/Model'); cache = UsdSkel.Cache()
    for p in Usd.PrimRange(model):
        if p.IsA(UsdSkel.Root): cache.Populate(UsdSkel.Root(p), Usd.PrimDefaultPredicate)
    skeleton = next(p for p in Usd.PrimRange(model) if p.IsA(UsdSkel.Skeleton))
    sq = cache.GetSkelQuery(UsdSkel.Skeleton(skeleton))
    transforms = sq.ComputeSkinningTransforms(Usd.TimeCode.Default())
    world = UsdGeom.Xformable(skeleton).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    all_points = []; all_faces = []; paths = []
    for p in Usd.PrimRange(model):
        if not p.IsA(UsdGeom.Mesh): continue
        assert str(p.GetPath()) in CONTRACT['target']['source_meshes']
        m = UsdGeom.Mesh(p); vertices = Vt.Vec3fArray(m.GetPointsAttr().Get())
        assert cache.GetSkinningQuery(p).ComputeSkinnedPoints(transforms, vertices, Usd.TimeCode.Default())
        pts = np.array([list(world.Transform(Gf.Vec3d(v))) for v in vertices])
        count = list(m.GetFaceVertexCountsAttr().Get()); indices = list(m.GetFaceVertexIndicesAttr().Get())
        start = 0; base = len(all_points)
        for n in count:
            face = indices[start:start+n]
            for j in range(1, n-1): all_faces.append([base+face[0], base+face[j], base+face[j+1]])
            start += n
        all_points.extend(pts); paths.append(str(p.GetPath()))
        label(p, CONTRACT['target']['class_name'])
    return np.array(all_points), np.array(all_faces), paths, plain(sq.ComputeJointLocalTransforms(Usd.TimeCode.Default()))


async def build(item):
    ctx = omni.usd.get_context(); app = omni.kit.app.get_app()
    assert ctx.get_stage() is None
    pose_id = item['fixture'][-1] if item['fixture'].startswith('animal_') else 'A'
    pose = next(p for p in DECL['source_poses'] if p['id'] == pose_id)
    animal = item['fixture'].startswith('animal_')
    root_record = None; joint_record = None; skin_error = None
    if animal:
        for key in ('scene', 'state', 'evaluated_skin'):
            assert sha(REPO/pose[key]['path']) == pose[key]['sha256']
        stage = Usd.Stage.Open(Sdf.Layer.OpenAsAnonymous(str(REPO/pose['scene']['path'])))
        # The frozen actor contains its materials; remove every other root in this owned copy.
        for p in list(stage.GetPseudoRoot().GetChildren()):
            if str(p.GetPath()) != '/MarlinGamaBottlenose': stage.RemovePrim(p.GetPath())
        stage.SetDefaultPrim(stage.GetPrimAtPath('/MarlinGamaBottlenose'))
        pts, faces, owned, joint_record = skin(stage)
        source_skin = np.load(REPO/pose['evaluated_skin']['path'])['points_m']
        skin_error = float(np.max(np.abs(pts*UNIT-source_skin)))
        assert skin_error <= 2e-6, skin_error
        root_record = plain(UsdGeom.Xformable(stage.GetPrimAtPath(ACTOR)).ComputeLocalToWorldTransform(Usd.TimeCode.Default()))
        assert np.max(np.abs(np.array(root_record)-pose['root_matrix'])) <= 1e-8
        # Dry uses the declared original accepted pose; no Y placement amendment.
        ok, error = await ctx.attach_stage_async(stage); assert ok, error
    else:
        await ctx.new_stage_async(); stage = ctx.get_stage()
        UsdGeom.SetStageMetersPerUnit(stage, UNIT); UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
        pts = np.empty((0, 3)); faces = np.empty((0, 3), dtype=int); owned = []
    assert stage.GetRootLayer().anonymous
    assert UsdGeom.GetStageUpAxis(stage) == 'Y' and abs(UsdGeom.GetStageMetersPerUnit(stage)-UNIT) < 1e-10
    camdecl = next(c for c in DECL['cameras'] if c['pose'] == pose_id and c['view'] == item['view'])
    position = np.array(camdecl['position_m'])/UNIT; target = np.array(camdecl['look_at_m'])/UNIT
    view = Gf.Matrix4d().SetLookAt(Gf.Vec3d(*position), Gf.Vec3d(*target), Gf.Vec3d(0, 0, -1))
    camera = UsdGeom.Camera.Define(stage, '/M2Camera')
    camera.AddTransformOp().Set(view.GetInverse())
    camera.CreateFocalLengthAttr(35); camera.CreateHorizontalApertureAttr(30.72); camera.CreateVerticalApertureAttr(23.04)
    camera.CreateClippingRangeAttr(Gf.Vec2f(1, 5000)); camera.CreateFStopAttr(0)
    camera.GetPrim().ApplyAPI('OmniRtxCameraAutoExposureAPI_1')
    camera.GetPrim().ApplyAPI('OmniRtxCameraExposureAPI_1')
    for name, value in {'omni:rtx:autoExposure:enabled':False, 'exposure':0., 'exposure:time':1.,
                        'exposure:fStop':1., 'exposure:iso':100., 'exposure:responsivity':1.}.items():
        a = camera.GetPrim().GetAttribute(name); assert a; a.Set(value)
    projection = camera.GetCamera().frustum.ComputeProjectionMatrix()
    points = np.array([[target[0]-.5/UNIT, 0, target[2]-.5/UNIT],
                       [target[0]+.5/UNIT, 0, target[2]-.5/UNIT],
                       [target[0]+.5/UNIT, 0, target[2]+.5/UNIT],
                       [target[0]-.5/UNIT, 0, target[2]+.5/UNIT]])
    fixture = item['fixture']; occluder = None
    if not animal:
        uv = project(points, np.array(view), np.array(projection))
        if fixture == 'fiducial_image_clipped':
            depth = -(np.r_[target, 1] @ np.array(view))[2]
            shift = 256*depth/(35/30.72*512)
            points[:, 0] += shift
        if fixture == 'fiducial_out_of_frame':
            depth = -(np.c_[points, np.ones(4)] @ np.array(view))[:, 2]
            shift = float(np.max((528-uv[:, 0])*depth/(35/30.72*512)))
            points[:, 0] += shift
        if fixture != 'target_absent':
            mesh(stage, '/M2Target', points, (.8, .15, .03), 'm2_fiducial')
            pts = points; faces = np.array([[0,1,2], [0,2,3]]); owned = ['/M2Target']
        if fixture in ('fiducial_half_occluded', 'fiducial_fully_occluded'):
            uv = project(points, np.array(view), np.array(projection)); lo = uv.min(0); hi = uv.max(0)
            x0, y0 = lo-8; x1, y1 = hi+8
            if fixture == 'fiducial_half_occluded': x1 = 256
            pixels = np.array([[x0,y0],[x1,y0],[x1,y1],[x0,y1]])
            local = np.c_[(pixels[:,0]-256)/camdecl['fx_px']*300,
                          -(pixels[:,1]-192)/camdecl['fy_px']*300, np.full(4,-300),np.ones(4)]
            occluder = (local @ np.array(view.GetInverse()))[:, :3]
            mesh(stage, '/M2Occluder', occluder, (.08,.14,.2), 'm2_occluder')
        if fixture == 'target_absent':
            # Target absence does not mean a renderer with no geometry at all.
            # A distinctly labelled negative background verifies real native
            # pixels and mappings; never synthesize an empty target image.
            mesh(stage, '/M2NonTargetBackground',
                 [[target[0]-2000,-400,target[2]-2000],
                  [target[0]+2000,-400,target[2]-2000],
                  [target[0]+2000,-400,target[2]+2000],
                  [target[0]-2000,-400,target[2]+2000]], (.12,.17,.22),'m2_negative_background')
    dome = UsdLux.DomeLight.Define(stage, '/M2Light'); dome.CreateIntensityAttr(.35)
    distant = UsdLux.DistantLight.Define(stage, '/M2Sun'); distant.CreateIntensityAttr(.8)
    distant.AddRotateXYZOp().Set(Gf.Vec3f(-65, 25, 0))
    return stage, dict(item=item, camera=camdecl, camera_path='/M2Camera', owned_meshes=owned,
        target_corners_scene_units=points if not animal and fixture != 'target_absent' else None,
        occluder_corners_scene_units=occluder, pose_id=pose_id if animal else None,
        root_matrix=root_record, joint_local_matrices=joint_record, skin_source_max_error_m=skin_error,
        source_pose=pose if animal else None, scene_present=bool(owned),
        source_commit='6305d6c115f31c902bc62e694fae51015146bf51'), pts, faces


async def capture(item, reserve):
    app = omni.kit.app.get_app(); ctx = omni.usd.get_context(); rp = None; annos = {}; folder = None
    result = dict(id=item['id'], passed=False)
    try:
        stage, record, points, faces = await build(item)
        record['attached_engines_before'] = ctx.get_attached_hydra_engine_names()
        if not record['attached_engines_before']:
            record['owned_engine_uid'] = omni.usd.create_hydra_engine('rtx',ctx)
        record['attached_engines_after'] = ctx.get_attached_hydra_engine_names()
        assert record['attached_engines_after'] == ['rtx']
        rp = rep.create.render_product('/M2Camera', (512,384), name='M2Dry')
        products = [str(p.GetPath()) for p in stage.TraverseAll() if p.IsA(UsdRender.Product)]
        assert products == [rp.path], products
        product = stage.GetPrimAtPath(rp.path)
        for name, value in {'omni:rtx:rendermode':'PathTracing', 'omni:rtx:fog:enabled':False,
                            'omni:rtx:pt:fireflyFilter:enabled':False,
                            'omni:rtx:post:tonemap:operator':'raw'}.items():
            a = product.GetAttribute(name); assert a, name; a.Set(value)
        for name in ('HdrColor', 'instance_segmentation', 'instance_id_segmentation', 'bounding_box_2d_tight', 'rpFabricTime', 'ReferenceTime', 'camera_params'):
            annos[name] = rep.AnnotatorRegistry.get_annotator(name); annos[name].attach(rp)
        record['projection'] = record_product_projection(stage, rp.path, '/M2Camera', (512,384), Usd.TimeCode.Default())
        record['settings'] = {str(p.GetPath()):{a.GetName():plain(a.Get()) for a in p.GetAttributes() if not a.GetName().startswith('outputs:')}
                              for p in (stage.GetPrimAtPath('/M2Camera'),product)}
        record['timeline_before'] = dict(time=omni.timeline.get_timeline_interface().get_current_time(), playing=omni.timeline.get_timeline_interface().is_playing())
        assert not record['timeline_before']['playing']
        # An attempted image starts here, including settling/capture failures.
        folder = start_attempt(item, reserve); save(folder/'fixture.json', record)
        np.savez_compressed(folder/'direct_geometry.npz', points_scene_units=points, triangles=faces)
        stage.GetRootLayer().Export(str(folder/'scene.usdc'))
        before = sha(folder/'scene.usdc')
        settle_start = time.monotonic()
        async def settle():
            for _ in range(64):
                await rep.orchestrator.step_async(rt_subframes=1, delta_time=0.0, pause_timeline=True)
        await asyncio.wait_for(settle(), timeout=45)
        record['delivered_settling_frames'] = 64
        record['settling_seconds'] = time.monotonic()-settle_start
        # No await between these synchronous copies: one completed graph evaluation.
        time_before = plain(annos['rpFabricTime'].get_data(do_array_copy=True))
        hdr = annos['HdrColor'].get_data(do_array_copy=True)
        native = annos['instance_segmentation'].get_data(do_array_copy=True)
        renderer_native = annos['instance_id_segmentation'].get_data(do_array_copy=True)
        # Preserve unavailable/raw outputs before enforcing shape/identity.
        for name,raw in [('renderer_instance',renderer_native),('standard_instance',native)]:
            if isinstance(raw,dict) and isinstance(raw.get('data'),np.ndarray):
                np.save(folder/(name+'_raw.npy'),raw['data'])
                save(folder/(name+'_raw_info.json'),raw.get('info',{}))
        from omni.syntheticdata.scripts.helpers import get_instance_mappings
        sdk_mapping = get_instance_mappings()
        bbox = annos['bounding_box_2d_tight'].get_data(do_array_copy=True)
        params = annos['camera_params'].get_data(do_array_copy=True)
        reference_time = plain(annos['ReferenceTime'].get_data(do_array_copy=True))
        time_after = plain(annos['rpFabricTime'].get_data(do_array_copy=True))
        assert time_before == time_after
        assert isinstance(hdr, np.ndarray) and hdr.shape == (384,512,4) and hdr.dtype.kind == 'f' and np.isfinite(hdr).all(), (type(hdr),getattr(hdr,'shape',None))
        mask = renderer_native['data']; assert mask.shape == (384,512) and mask.dtype == np.uint32
        np.savez_compressed(folder/'hdr.npz', rgba=hdr.astype(np.float32))
        np.save(folder/'native_instance_mask.npy', mask)
        np.save(folder/'native_tight_boxes.npy', bbox['data'])
        save(folder/'native_instance_info.json', renderer_native.get('info',{}))
        np.save(folder/'standard_instance_mask.npy',native['data'])
        save(folder/'standard_instance_info.json',native.get('info',{}))
        save(folder/'sdk_instance_mappings.json',sdk_mapping)
        save(folder/'native_box_info.json', bbox.get('info',{}))
        save(folder/'native_camera_params.json', params)
        save(folder/'native_time.json', dict(before=time_before, after=time_after, reference_time=reference_time))
        buf = io.BytesIO(); save_exr_to_stream(buf, hdr.astype(np.float32), False)
        (folder/'hdr.exr').write_bytes(buf.getvalue())
        restored = load_exr_from_stream(io.BytesIO(buf.getvalue()))
        assert isinstance(restored,np.ndarray) and restored.shape == hdr.shape
        exr_error = float(np.max(np.abs(restored-hdr.astype(np.float32))))
        assert exr_error == 0, exr_error
        # Fixed display mapping, never native LDR.
        rgb = np.maximum(hdr[:,:,:3].astype(np.float32),0)
        display = np.rint(255*(rgb/(1+rgb))**(1/2.2)).astype(np.uint8)
        Image.fromarray(display).save(folder/'display.png')
        stage.GetRootLayer().Export(str(folder/'scene_after.usdc'))
        # Compare layer text: crate byte layout is not a state identity proof.
        saved = Usd.Stage.Open(str(folder/'scene.usdc'))
        state_unchanged = saved.GetRootLayer().ExportToString() == stage.GetRootLayer().ExportToString()
        record.update(hdr_dtype=str(hdr.dtype), hdr_min=float(hdr.min()), hdr_max=float(hdr.max()),
                      exr_roundtrip_max_error=exr_error,
                      native_instance_source='instance_id_segmentation: native renderer IDs; vendor marks this annotator hidden/development',
                      standard_instance_diagnostic='instance_segmentation retained separately; prim-path mapping empty on this runtime; not a qualified source',
                      reference_time=reference_time,
                      native_time_before=time_before, native_time_after=time_after,
                      state_unchanged=state_unchanged,
                      timeline_after=dict(time=omni.timeline.get_timeline_interface().get_current_time(), playing=omni.timeline.get_timeline_interface().is_playing()),
                      native_frame_id=None, synchronisation='Synchronous annotator copies after completed native graph step; rpFabricTime plus immutable scene, no invented per-annotator frame ID',
                      declaration_sha256=sha(BASE/'declarations/capture_declaration.json'),
                      files_sha256={p.name:sha(p) for p in folder.iterdir() if p.is_file()},
                      status='captured_pending_independent_validation')
        save(folder/'bundle.json', record)
        assert state_unchanged, 'Scene state changed during capture'
        assert record['timeline_before'] == record['timeline_after'], 'Timeline changed'
        finish_attempt(folder, 'captured_pending_independent_validation')
        result.update(passed=True, folder=str(folder), native_time=time_before)
    except BaseException:
        result['error'] = traceback.format_exc(); print(result['error'], flush=True)
        if folder:
            save(folder/'failure.json', result); finish_attempt(folder, 'failed', result['error'])
    finally:
        for a in reversed(list(annos.values())):
            try: a.detach(rp)
            except Exception as e: result.setdefault('cleanup_errors',[]).append(str(e))
        if rp:
            path = rp.path; rp.destroy()
            result['product_destroyed'] = not bool(ctx.get_stage().GetPrimAtPath(path))
        if ctx.get_stage() is not None: await ctx.close_stage_async()
        result['stage_closed'] = ctx.get_stage() is None
        result['passed'] = bool(result['passed'] and result.get('product_destroyed') and result['stage_closed'] and not result.get('cleanup_errors'))
    return result


async def main():
    app = omni.kit.app.get_app(); result = dict(passed=False, captures=[])
    try:
        while not app.is_app_ready(): await app.next_update_async()
        window = get_active_viewport_window()
        if window: window.destroy()
        for _ in range(2): await app.next_update_async()
        settings = carb.settings.get_settings()
        assert not settings.get('/app/extensions/registryEnabled')
        settings.set('/rtx/pathtracing/spp', 1); settings.set('/rtx/pathtracing/totalSpp', 64)
        settings.set('/rtx/pathtracing/optixDenoiser/enabled',False)
        settings.set('/rtx/post/histogram/enabled',False)
        for row in json.loads((BASE/'baseline/source_before.json').read_text())['files']:
            assert sha(REPO/row['path']) == row['sha256'], row['path']
        save(OUT/'ready.json',dict(app_ready=True))
        batch = os.environ['ANNOTATION_CAPTURE_BATCH']
        reserve = batch == 'diagnostics'
        if reserve:
            items = [dict(id='flat_fiducial_dry_'+v, fixture='fiducial_visible',view=v, block='diagnostic') for v in ('nadir','oblique')]
        elif batch == 'absent_retry':
            items = DECL['dry'][10:12]
        else:
            indices = {'dry01':(0,6), 'dry02':(6,12), 'dry03':(12,16)}[batch]
            items = DECL['dry'][indices[0]:indices[1]]
        assert len(items) <= 6
        for item in items:
            prior = json.loads(LEDGER.read_text())['attempts']
            is_retry = any(x['declaration_id']==item['id'] for x in prior)
            r = await asyncio.wait_for(capture(item,reserve or is_retry), timeout=90)
            result['captures'].append(r); save(OUT/'progress.json',result)
            if not r['passed']: raise RuntimeError('Dependent captures stopped after failure')
        result['passed'] = True
    except BaseException:
        result['error'] = traceback.format_exc(); print(result['error'],flush=True)
    finally:
        save(OUT/'result.json',result); app.post_quit(0 if result['passed'] else 1)


asyncio.ensure_future(main())
