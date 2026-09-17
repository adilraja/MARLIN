"""CPU regression tests; run with a Python environment containing NumPy."""
import ast
import importlib
from pathlib import Path
import sys
import tempfile
import types
import unittest
import numpy as np
try:
    from pxr import Usd, UsdGeom, Gf
except ImportError:
    Usd = None

BASE = Path(__file__).resolve().parents[1]/'source/extensions/cris.madil.render_service/cris/madil/render_service'
package = types.ModuleType('_marine_test')
package.__path__ = [str(BASE)]
sys.modules[package.__name__] = package
camera = importlib.import_module('_marine_test.hidef_camera')
maps = importlib.import_module('_marine_test.hidef_maps')


class MarineTests(unittest.TestCase):
    @unittest.skipIf(Usd is None,'Requires USD Python (available in Blender)')
    def test_replay_reads_disk_not_dirty_cached_layer(self):
        from pxr import Sdf
        tree=ast.parse((BASE/'hidef_marine.py').read_text())
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='open_snapshot')
        namespace={'Usd':Usd,'Sdf':Sdf}
        exec(compile(ast.Module(body=[function],type_ignores=[]),'open_snapshot','exec'),namespace)
        with tempfile.TemporaryDirectory() as directory:
            path=str(Path(directory)/'scene.usdc')
            source=Usd.Stage.CreateNew(path)
            geometry=importlib.import_module('_marine_test.calibration_geometry')
            geometry.build_camera(source,camera.configuration(7.7675,1),'/Camera')
            source.GetRootLayer().Save()
            original_bytes=Path(path).read_bytes()
            original_text=source.GetRootLayer().ExportToString()
            # Simulate viewport edits to the already cached disk layer.
            source.DefinePrim('/Render/UnexpectedProduct')
            UsdGeom.Camera(source.GetPrimAtPath('/Camera')).GetHorizontalApertureAttr().Set(1)
            cached=Usd.Stage.Open(path)
            self.assertTrue(cached.GetPrimAtPath('/Render'))
            fresh=namespace['open_snapshot'](path)
            self.assertFalse(fresh.GetPrimAtPath('/Render'))
            self.assertEqual(UsdGeom.Camera(fresh.GetPrimAtPath('/Camera')).GetHorizontalApertureAttr().Get(),36)
            out=Path(directory)/'copy.usdc'
            fresh.GetRootLayer().Export(str(out))
            self.assertEqual(fresh.GetRootLayer().ExportToString(),original_text)
            self.assertEqual(Path(path).read_bytes(),original_bytes)
            fresh.DefinePrim('/Private')
            again=namespace['open_snapshot'](path)
            self.assertFalse(again.GetPrimAtPath('/Private'))

    @unittest.skipIf(Usd is None,'Requires USD Python (available in Blender)')
    def test_snapshot_freezes_samples_without_touching_source(self):
        tree=ast.parse((BASE/'hidef_marine.py').read_text())
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='freeze_stage')
        namespace={'Usd':Usd}
        exec(compile(ast.Module(body=[function],type_ignores=[]),'freeze_stage','exec'),namespace)
        source=Usd.Stage.CreateInMemory()
        prim=UsdGeom.Xform.Define(source,'/World/Animal')
        op=prim.AddTranslateOp()
        op.Set(Gf.Vec3d(0,1,2),0)
        op.Set(Gf.Vec3d(10,11,12),10)
        frozen,count=namespace['freeze_stage'](source,Usd.TimeCode(5))
        self.assertEqual(count,1)
        attr=frozen.GetPrimAtPath('/World/Animal').GetAttribute('xformOp:translate')
        self.assertEqual(attr.GetNumTimeSamples(),0)
        self.assertEqual(tuple(attr.Get()),(5,6,7))
        self.assertEqual(tuple(attr.Get(20)),(5,6,7))
        self.assertEqual(op.GetAttr().GetNumTimeSamples(),2)

    @unittest.skipIf(Usd is None,'Requires USD Python (available in Blender)')
    def test_translated_camera_matches_pixel_rays(self):
        geometry=importlib.import_module('_marine_test.calibration_geometry')
        for roll in (7.77,23.17):
            c=camera.configuration(roll)
            center=c.ray_plane(822,274)
            translation=(12-center[0],0,-30-center[2])
            stage=Usd.Stage.CreateInMemory()
            cam=geometry.build_camera(stage,c,'/Camera',translation)
            frustum=cam.GetCamera(0).frustum
            vp=frustum.ComputeViewMatrix()*frustum.ComputeProjectionMatrix()
            for u,v in ((.5,.5),(822.5,274.5),(1643.5,547.5)):
                point=c.ray_plane(u,v)
                ndc=vp.Transform(Gf.Vec3d(*((p+t)/.01 for p,t in zip(point,translation))))
                self.assertAlmostEqual((ndc[0]+1)*822,u,places=3)
                self.assertAlmostEqual((1-ndc[1])*274,v,places=3)

    def test_maps_match_independent_pixel_rays(self):
        for roll in (7.77,23.17):
            c = camera.configuration(roll)
            values = maps.maps_chunk(maps.geometry_inputs(c),roll,100,102)
            import math
            for col in (0,800,1642):
                p=c.ray_plane(col+.5,100.5)
                self.assertAlmostEqual(values['gsd_width_cm_px'][0,col],100*math.dist(p,c.ray_plane(col+1.5,100.5)),places=8)
                self.assertAlmostEqual(values['gsd_height_cm_px'][0,col],100*math.dist(p,c.ray_plane(col+.5,101.5)),places=8)

    def test_export_shape_mask_area_and_translation(self):
        c=camera.configuration()
        with tempfile.TemporaryDirectory() as d:
            result=maps.export_maps(Path(d),c,(12,0,-30))
            with np.load(Path(d)/result['file']) as data:
                self.assertEqual(data['gsd_width_cm_px'].shape,(548,1644))
                self.assertTrue(np.isnan(data['gsd_width_cm_px'][:,-1]).all())
                self.assertTrue(np.isnan(data['gsd_height_cm_px'][-1,:]).all())
                area=data['effective_pixel_area_cm2']
                self.assertTrue(np.isfinite(area).all())
                self.assertTrue((area>0).all())
                self.assertGreater(np.nanmin(data['gsd_width_cm_px']),8)
                self.assertGreater(np.nanmin(data['gsd_height_cm_px']),10)
            corner=c.ray_plane(0,0)
            np.testing.assert_allclose(result['footprint']['corners_xz_m'][0],[corner[0]+12,corner[2]-30])
            self.assertEqual((Path(d)/'gsd_width_cm_px.png').read_bytes()[:8],b'\x89PNG\r\n\x1a\n')

    def test_no_unscoped_setting_writes_or_engine_release(self):
        for name in ('hidef_marine.py','calibration_capture.py'):
            tree=ast.parse((BASE/name).read_text())
            calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call)]
            # Writes must use recorded/preset dictionaries through the shared
            # restoration helper, apart from the explicit display-options key.
            for call in calls:
                if isinstance(call.func,ast.Attribute):
                    self.assertNotIn(call.func.attr,('new_stage','open_stage','release_all_hydra_engines'))
                    if call.func.attr in ('set','destroy_item'):
                        self.assertIn(ast.unparse(call.args[0]),('display_key','key'))
                        if ast.unparse(call.args[0])=='key' and call.func.attr=='set':
                            self.assertEqual(ast.unparse(call.args[1]),'value')

    def test_restore_reapplies_saved_values_and_preserves_unrelated_settings(self):
        tree=ast.parse((BASE/'hidef_marine.py').read_text())
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='restore_settings')
        values={'/rtx/fog/enabled':True,'unrelated':42,'missing_before':123}
        fake=types.SimpleNamespace(get=values.get,set=values.__setitem__,destroy_item=values.pop)
        namespace={'carb':types.SimpleNamespace(settings=types.SimpleNamespace(get_settings=lambda:fake))}
        exec(compile(ast.Module(body=[function],type_ignores=[]),'restore_settings','exec'),namespace)
        namespace['restore_settings']({'/rtx/fog/enabled':False,'missing_before':None})
        self.assertEqual(values,{'/rtx/fog/enabled':False,'unrelated':42})

    def test_capture_gate_precedes_controller_updates(self):
        for filename,name in (('ocean.py','_update_animated_ocean'),
                              ('cetacean_gallery.py','_update_gallery_swimming'),
                              ('cetacean.py','_update_cetacean_swimming'),
                              ('camera.py','_update_chase_camera'),('petrel_api.py','_update')):
            tree=ast.parse((BASE/filename).read_text())
            function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
            statements=[n for n in function.body if not isinstance(n,ast.Expr)]
            self.assertIsInstance(statements[0],ast.ImportFrom)
            self.assertEqual(ast.unparse(statements[1].test),'capture_state.paused')
            self.assertIsInstance(statements[1].body[0],ast.Return)


if __name__=='__main__':
    unittest.main(argv=[sys.argv[0]])
