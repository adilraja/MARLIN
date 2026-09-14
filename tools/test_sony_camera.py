"""Sony independent pinhole, map and USD tests; run with Blender Python."""
import importlib
from dataclasses import replace
import sys
from pathlib import Path
import unittest
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_hidef_marine import BASE, Usd
if Usd is not None:
    from pxr import Gf

camera = importlib.import_module('_marine_test.sony_camera')
geometry = importlib.import_module('_marine_test.calibration_geometry')
maps = importlib.import_module('_marine_test.hidef_maps')


class SonyTests(unittest.TestCase):
    def test_native_geometry_independent_targets(self):
        c = camera.configuration(1)
        self.assertAlmostEqual(c.gsd_m_px*100, .6628787878788, places=10)
        a, b = c.ray_plane(0, 0), c.ray_plane(9504, 6336)
        self.assertAlmostEqual(b[0]-a[0], 63)
        self.assertAlmostEqual(b[2]-a[2], 42)
        self.assertLess(abs(c.gsd_m_px*100-.6629), .00003)

    def test_preview_preserves_footprint_not_native_sampling(self):
        a, b = camera.configuration(1), camera.configuration(8)
        self.assertEqual((b.image_width_px,b.image_height_px),(1188,792))
        for u,v in ((0,0),(.5,.5),(1,1)):
            np.testing.assert_allclose(a.ray_plane(u*9504,v*6336),b.ray_plane(u*1188,v*792))
        self.assertAlmostEqual(b.gsd_m_px/a.gsd_m_px, 8)

    def test_directional_maps_and_area(self):
        c = camera.configuration()
        values = maps.maps_chunk(maps.geometry_inputs(c),0,100,102)
        for key in ('gsd_width_cm_px','gsd_height_cm_px'):
            np.testing.assert_allclose(values[key][np.isfinite(values[key])],5.30303030303,rtol=1e-9)
        np.testing.assert_allclose(values['anisotropy_height_over_width'][np.isfinite(values['anisotropy_height_over_width'])],1,rtol=1e-9)
        np.testing.assert_allclose(values['effective_pixel_area_cm2'],5.30303030303**2,rtol=1e-8)

    def test_provenance_and_profile_isolation(self):
        c = camera.configuration()
        m = c.metadata()
        self.assertFalse(m['scientific_camera_calibrated'])
        self.assertIn('unresolved',m['acquisition_mode'])
        self.assertIn('assumed',m['pose_convention'])
        for changes in ({'pitch_deg':30},{'roll_deg':7.77},{'focal_length_mm':150},{'downsample':4}):
            with self.assertRaises(ValueError):
                replace(c,**changes)

    @unittest.skipIf(Usd is None, 'USD available in Blender')
    def test_usd_camera_matches_rays_without_changing_stage(self):
        c = camera.configuration()
        stage = Usd.Stage.CreateInMemory()
        cam = geometry.build_camera(stage,c,'/Sony/Camera',(5,0,-7))
        vp = cam.GetCamera(0).frustum.ComputeViewMatrix()*cam.GetCamera(0).frustum.ComputeProjectionMatrix()
        for u,v in ((.5,.5),(594,396),(1187.5,791.5)):
            point=c.ray_plane(u,v)
            ndc=vp.Transform(Gf.Vec3d((point[0]+5)/.01,point[1]/.01,(point[2]-7)/.01))
            self.assertAlmostEqual((ndc[0]+1)*594,u,places=3)
            self.assertAlmostEqual((1-ndc[1])*396,v,places=3)
        self.assertFalse(stage.GetPrimAtPath('/World'))


if __name__=='__main__':
    unittest.main(argv=[sys.argv[0]])
