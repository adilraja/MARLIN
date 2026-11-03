import ast
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ocean_enclosure import enclose,grid_topology,topology,validate,perimeter


class EnclosureTests(unittest.TestCase):
    def fixture(self,r):
        points=[(c, .2*math.sin(c*.3)*math.cos(z*.2),z) for z in range(r+1) for c in range(r+1)]
        normals=[(.1,.98,.1)]*len(points)
        return points,normals

    def test_closed_boundary_at_small_and_production_resolutions(self):
        for r in (2,8,128):
            p,n=self.fixture(r);out,cn,extent=enclose(p,n,r,-20)
            result=validate(out,topology(r),r)
            self.assertEqual(result['boundary_edges'],0)
            self.assertEqual(result['nonmanifold_edges'],0)
            self.assertEqual(result['same_direction_shared_edges'],0)
            self.assertEqual(len(out),(r+1)**2+4*r+1)
            self.assertEqual(len(topology(r)),r*r+8*r)
            self.assertEqual(extent[0][1],-20)

    def test_surface_and_corner_normals_were_copied_without_change(self):
        r=8;p,n=self.fixture(r);out,cn,_=enclose(p,n,r,-20)
        self.assertEqual(out[:len(p)],p)
        expected=[n[i] for face in grid_topology(r) for i in face]
        self.assertEqual(cn[:4*r*r],expected)
        self.assertEqual(topology(r)[:r*r],grid_topology(r))

    def test_skirt_shared_surface_indices_and_vertical_projection(self):
        r=8;p,n=self.fixture(r);out,_,_=enclose(p,n,r,-20)
        for index,v in enumerate(perimeter(r)):
            self.assertEqual((out[len(p)+index][0],out[len(p)+index][2]),(p[v][0],p[v][2]))

    def test_orientation_validator_rejected_reversed_bottom(self):
        p,n=self.fixture(8);out,_,_=enclose(p,n,8,-20);faces=topology(8);faces[-1]=list(reversed(faces[-1]))
        with self.assertRaises(ValueError):validate(out,faces,8)

    def test_unsafe_or_malformed_geometry_was_rejected(self):
        p,n=self.fixture(8)
        for bottom in (1,float('nan')):
            with self.assertRaises(ValueError):enclose(p,n,8,bottom)
        with self.assertRaises(ValueError):enclose(p[:-1],n,8,-20)


if __name__=='__main__':unittest.main()
