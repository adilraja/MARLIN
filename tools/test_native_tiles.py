"""Verify native tile rays and exact pixel coverage without allocating RTX."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import importlib
import unittest
import numpy as np
from test_hidef_marine import camera, Usd, Gf
geometry=importlib.import_module('_marine_test.calibration_geometry')
tiles=importlib.import_module('_marine_test.native_tiles')


class NativeTilesTests(unittest.TestCase):
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


if __name__=='__main__':
    unittest.main(argv=[sys.argv[0]])
