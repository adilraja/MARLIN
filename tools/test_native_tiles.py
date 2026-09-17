"""Verify native tile rays and exact pixel coverage without allocating RTX."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import importlib
import unittest
import asyncio
import numpy as np
from test_hidef_marine import camera, Usd, Gf
geometry=importlib.import_module('_marine_test.calibration_geometry')
tiles=importlib.import_module('_marine_test.native_tiles')


class NativeTilesTests(unittest.TestCase):
    def test_owned_sdk_product_has_exact_dimensions_and_camera(self):
        from pxr import UsdRender
        sdk=importlib.import_module('_marine_test.sdk_tile_capture')
        stage=Usd.Stage.CreateInMemory()
        stage.DefinePrim('/Camera','Camera')
        product=sdk.create_tile_product(stage,'/Render/Test','/Camera',(854,306))
        self.assertEqual(tuple(product.GetResolutionAttr().Get()),(854,306))
        self.assertEqual([str(p) for p in product.GetCameraRel().GetTargets()],['/Camera'])
        self.assertEqual(product.GetPixelAspectRatioAttr().Get(),1)
        var=UsdRender.Var(stage.GetPrimAtPath(product.GetOrderedVarsRel().GetTargets()[0]))
        self.assertEqual(var.GetSourceNameAttr().Get(),'LdrColor')
        with self.assertRaisesRegex(RuntimeError,'already exists'):
            sdk.create_tile_product(stage,'/Render/Test','/Camera',(854,306))

    def test_resolution_reset_restarts_settling(self):
        class View:
            resolution=(854,306)
            fill_frame=False
            delivered=0
            async def wait_for_rendered_frames(self,frames):
                self.delivered+=frames
                if self.delivered==3:
                    self.resolution=(817,314)
        view=View()
        resets=asyncio.run(tiles.wait_for_fixed_resolution(view,(854,306),3))
        self.assertEqual(resets,1)
        self.assertEqual(view.delivered,6)
        self.assertEqual(view.resolution,(854,306))

    def test_unstable_resolution_fails_closed(self):
        class View:
            resolution=(854,306)
            fill_frame=False
            async def wait_for_rendered_frames(self,frames):
                self.resolution=(817,314)
        with self.assertRaisesRegex(ValueError,'will not remain fixed'):
            asyncio.run(tiles.wait_for_fixed_resolution(View(),(854,306),3,max_resets=2))

    def test_cores_cover_native_frame_once(self):
        coverage=np.zeros((2192,6576),dtype=np.uint8)
        for spec in tiles.tile_specs(6576,2192):
            x,y,r,s=spec['core'];a,b,c,d=spec['bounds']
            coverage[y:s,x:r]+=1
            self.assertEqual((c-a,d-b),(854,306))
        self.assertTrue((coverage==1).all())

    def test_tile_projection_matches_native_rays(self):
        for roll in (7.7675,23.1748):
            config=camera.configuration(roll,1)
            stage=Usd.Stage.CreateInMemory()
            cam=geometry.build_camera(stage,config,'/Camera')
            for spec in tiles.tile_specs(6576,2192):
                tiles.apply_tile(cam,(36,12),6576,2192,spec)
                frustum=cam.GetCamera(0).frustum
                vp=frustum.ComputeViewMatrix()*frustum.ComputeProjectionMatrix()
                a,b,c,d=spec['bounds']
                for u,v in ((a+.5,b+.5),((a+c)/2,(b+d)/2),(c-.5,d-.5)):
                    ndc=vp.Transform(Gf.Vec3d(*(x/.01 for x in config.ray_plane(u,v))))
                    self.assertLess(abs((ndc[0]+1)*(c-a)/2-(u-a)),.001)
                    self.assertLess(abs((1-ndc[1])*(d-b)/2-(v-b)),.001)

    def test_larger_guard_changes_neither_core_nor_native_rays(self):
        config=camera.configuration(7.7675,1)
        stage=Usd.Stage.CreateInMemory()
        cam=geometry.build_camera(stage,config,'/Camera')
        for small,large in zip(tiles.tile_specs(6576,2192),tiles.tile_specs(6576,2192,64)):
            self.assertEqual(small['core'],large['core'])
            self.assertEqual(large['resolution'],[950,402])
            tiles.apply_tile(cam,(36,12),6576,2192,large)
            vp=cam.GetCamera(0).frustum.ComputeViewMatrix()*cam.GetCamera(0).frustum.ComputeProjectionMatrix()
            a,b,c,d=large['bounds']
            u,v=small['bounds'][:2]
            ndc=vp.Transform(Gf.Vec3d(*(x/.01 for x in config.ray_plane(u+.5,v+.5))))
            self.assertLess(abs((ndc[0]+1)*(c-a)/2-(u+.5-a)),.001)
            self.assertLess(abs((1-ndc[1])*(d-b)/2-(v+.5-b)),.001)


if __name__=='__main__':
    unittest.main(argv=[sys.argv[0]])
