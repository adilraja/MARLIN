import math
import unittest
from analyse_refraction import interface_point


class RefractionGeometryTests(unittest.TestCase):
    def test_equal_indices_gave_straight_line_intersection(self):
        p=interface_point([0,3,4],[0,-1,0],1,1)
        self.assertAlmostEqual(p[2],1)

    def test_nadir_had_no_lateral_bending(self):
        self.assertEqual(interface_point([0,3,0],[0,-1,0]),[0,0,0])

    def test_water_satisfied_snell_law(self):
        p=interface_point([0,3,4],[0,-1,0])
        sin_air=(4-p[2])/math.hypot(3,4-p[2])
        sin_water=p[2]/math.hypot(1,p[2])
        self.assertAlmostEqual(sin_air,1.333*sin_water,places=12)
        self.assertLess(p[2],1)

    def test_azimuth_symmetry_was_preserved(self):
        a=interface_point([4,3,0],[0,-1,0]);b=interface_point([0,3,4],[0,-1,0])
        self.assertAlmostEqual(a[0],b[2]);self.assertEqual(a[2],b[0])


if __name__=='__main__':unittest.main()
