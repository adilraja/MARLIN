"""Independent analytic expectations for clipping, empty results and near rejection."""
import unittest
import numpy as np
import reference as ref


class GeometryContract(unittest.TestCase):
    def test_clipped_triangle_has_real_image_intersection(self):
        poly=ref.clip_polygon([[-10,100],[10,100],[10,120]])
        self.assertAlmostEqual(poly[:,0].min(),0)
        self.assertAlmostEqual(poly[:,0].max(),10)
        self.assertAlmostEqual(poly[:,1].max(),120)

    def test_fully_offscreen_is_empty(self):
        self.assertEqual(len(ref.clip_polygon([[528,100],[550,100],[540,120]])),0)

    def test_half_open_box_and_empty(self):
        mask=np.zeros((384,512),dtype=bool)
        self.assertIsNone(ref.tight_box(mask))
        mask[20:23,10:14]=True
        self.assertEqual(ref.tight_box(mask),[10,20,14,23])

    def test_near_plane_crossing_is_explicitly_rejected(self):
        with self.assertRaisesRegex(ValueError,'Near/far'):
            ref.project(np.array([[0,0,-.5],[1,0,-2],[0,1,-2]]),np.eye(4),np.eye(4))

    def test_direct_box_empty_geometry_is_null(self):
        self.assertIsNone(ref.geometry_box(np.empty((0,3)),np.empty((0,3),dtype=int),np.eye(4),np.eye(4)))

    def test_ray_plane_known_pinhole(self):
        origin=np.array([0,1,0]);dirs=np.array([[0,-1,0],[2,-1,0]])
        corners=np.array([[-.5,0,-.5],[.5,0,-.5],[.5,0,.5],[-.5,0,.5]])
        old_h,old_w=ref.H,ref.W
        try:
            ref.H=1;ref.W=2
            hit,depth=ref.plane_hit(corners,origin,dirs)
            self.assertEqual(hit.tolist(),[[True,False]])
            self.assertEqual(depth.tolist(),[[1,1]])
        finally:ref.H=old_h;ref.W=old_w


if __name__=='__main__':unittest.main()
