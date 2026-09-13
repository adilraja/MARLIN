import importlib.util
import math
from pathlib import Path
import sys
import types
import unittest

BASE = Path(__file__).resolve().parents[1]
PACKAGE = '_hidef_test_package'
if PACKAGE not in sys.modules:
    package = types.ModuleType(PACKAGE)
    package.__path__ = [str(BASE)]
    sys.modules[PACKAGE] = package
module = __import__(PACKAGE + '.hidef_camera', fromlist=['configuration'])


class HiDefTests(unittest.TestCase):
    def test_nominal_not_actual_oblique_gsd(self):
        c = module.configuration(downsample=1)
        self.assertAlmostEqual(c.gsd_m_px*100, 2.003649635)
        self.assertGreater(min(c.local_gsd(c.image_width_px/2,c.image_height_px/2)), 2.2)

    def test_pose_is_cross_track_tilt_not_optical_roll(self):
        for roll in module.ROLLS:
            c = module.configuration(roll)
            right,up,forward = c.basis()
            self.assertGreater(forward[0], 0)
            self.assertLess(forward[1], 0)
            self.assertGreater(math.degrees(math.acos(-forward[1])), 30)
            for a in (right,up,forward):
                self.assertAlmostEqual(sum(x*x for x in a),1)
            self.assertAlmostEqual(sum(x*y for x,y in zip(right,up)),0)

    def test_preview_preserves_footprint_not_sampling(self):
        full,preview = module.configuration(downsample=1),module.configuration(downsample=4)
        for u,v in ((.1,.1),(.5,.5),(.9,.9)):
            a=full.ray_plane(u*6576,v*2192)
            b=preview.ray_plane(u*1644,v*548)
            self.assertLess(math.dist(a,b),1e-9)
        self.assertAlmostEqual(preview.gsd_m_px/full.gsd_m_px,4)

    def test_projection_roundtrip(self):
        for roll in module.ROLLS:
            c=module.configuration(roll)
            for u,v in ((100,100),(800,250),(1500,450)):
                self.assertLess(math.dist(c.project(c.ray_plane(u,v)),(u,v)),1e-8)

    def test_provenance_and_native_sensitivity(self):
        c=module.configuration(aperture_basis='manufacturer_roi_hypothesis')
        self.assertAlmostEqual(c.metadata()['effective_sensor_mm'][0],36.168)
        self.assertIn('unresolved',c.metadata()['acquisition_mode'])
        self.assertEqual(c.metadata()['reference_resolution'],[6576,2192])
        with self.assertRaises(ValueError):
            module.configuration(roll_deg=0)


if __name__ == '__main__':
    unittest.main()
