import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
try:
    import numpy as np
    from bartlett_geometry import validate,nominal,basis,project,maps_chunk,footprint,footprint_gaps
except ImportError:
    np=None


@unittest.skipIf(np is None,'Run with NumPy-enabled Python')
class BartlettTests(unittest.TestCase):
    def setUp(self):
        self.c=json.loads((Path(__file__).resolve().parents[4]/'config/bartlett_geometry_v1.json').read_text())

    def test_paper_nominal_not_manufacturer_pitch(self):
        for v in nominal(self.c): self.assertAlmostEqual(v,2.0036,places=4)
        self.assertNotAlmostEqual(nominal(self.c)[0],2.013,places=3)

    def test_flat_nadir_spacing_area_and_invalid_boundaries(self):
        c={**self.c,'pitch_from_nadir_deg':0,'image_width_px':80,'image_height_px':32}
        m=maps_chunk(c,0,0,32)
        gx,gy=nominal(c)
        np.testing.assert_allclose(m['gsd_width_cm_px'][:,:-1],gx)
        np.testing.assert_allclose(m['gsd_height_cm_px'][:-1,:],gy)
        np.testing.assert_allclose(m['effective_pixel_area_cm2'],gx*gy)
        self.assertTrue(np.isnan(m['gsd_width_cm_px'][:,-1]).all())
        self.assertTrue(np.isnan(m['gsd_height_cm_px'][-1,:]).all())

    def test_basis_and_projection_against_scalar_intersection(self):
        for r in self.c['rolls_deg']:
            b=basis(30,r)
            np.testing.assert_allclose(b@b.T,np.eye(3),atol=1e-14)
            p=project(self.c,r,3288,1096)
            forward=b[2]
            expected=-549/forward[1]*forward[[0,2]]
            np.testing.assert_allclose(p,expected)
            self.assertGreater(p[0],0)
            self.assertAlmostEqual(p[1],-549*np.tan(np.deg2rad(30)))

    def test_chunking_and_directionality(self):
        c={**self.c,'image_width_px':80,'image_height_px':32}
        a=maps_chunk(c,23.1748,0,32)
        first,last=maps_chunk(c,23.1748,0,13),maps_chunk(c,23.1748,13,32)
        for name in a: np.testing.assert_allclose(a[name],np.vstack([first[name],last[name]]),equal_nan=True)
        self.assertFalse(np.allclose(a['gsd_width_cm_px'][:-1,:-1],a['gsd_height_cm_px'][:-1,:-1]))
        # Nonorthogonal projected directions: area is NOT width times height.
        self.assertGreater(np.max(np.abs(a['effective_pixel_area_cm2'][:-1,:-1]-a['gsd_width_cm_px'][:-1,:-1]*a['gsd_height_cm_px'][:-1,:-1])),0.01)

    def test_facing_edge_gaps_not_outer_corner_sections(self):
        fps=[footprint(self.c,r) for r in (-23.1748,-7.7675,7.7675,23.1748)]
        gaps=footprint_gaps(fps)
        self.assertEqual(len(gaps),3)
        for gap in gaps:
            self.assertGreater(gap['min_gap_m'],0)
            self.assertLess(gap['max_gap_m'],30)

    def test_bad_inputs(self):
        for key,value in [('camera_to_plane_m',0),('sensor_width_mm',float('nan')),('image_width_px',0),('pitch_from_nadir_deg',90)]:
            with self.assertRaises(ValueError): validate({**self.c,key:value})


if __name__=='__main__': unittest.main()
