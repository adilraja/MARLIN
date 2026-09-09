import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from calibration_geometry import CalibrationConfig, build_stage

try:
    from pxr import Gf, Usd, UsdGeom
except ImportError:
    Usd = None


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((Path(__file__).resolve().parents[4]/'config/calibration_target_v1.json').read_text())

    def test_expected_projection(self):
        c = CalibrationConfig(**self.data)
        self.assertEqual(c.expected_size_px, (200,100))
        self.assertEqual(c.metadata()['expected_bbox_xywh_px'], [412,334,200,100])
        self.assertAlmostEqual(c.gsd_m_px*100, 1)

    def test_missing_invalid_and_cropped_inputs(self):
        d = dict(self.data)
        del d['meters_per_scene_unit']
        with self.assertRaises(TypeError):
            CalibrationConfig(**d)
        for field, value in [('meters_per_scene_unit',0), ('focal_length_mm',float('nan')),
                              ('image_width_px',1024.5), ('target_width_m',100), ('target_height_m',0.001)]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                CalibrationConfig(**{**self.data,field:value})

    @unittest.skipIf(Usd is None, 'Requires pxr; run in Blender')
    def test_authored_usd_projection_in_both_unit_conventions(self):
        for unit in (0.01,1):
            c = CalibrationConfig(**{**self.data, 'meters_per_scene_unit':unit})
            stage = Usd.Stage.CreateInMemory()
            camera = build_stage(stage,c)
            frustum = camera.GetCamera(0).frustum
            vp = frustum.ComputeViewMatrix()*frustum.ComputeProjectionMatrix()
            points = UsdGeom.Mesh(stage.GetPrimAtPath('/Calibration/Target_00')).GetPointsAttr().Get()
            projected = [vp.Transform(Gf.Vec3d(p)) for p in points]
            xs = [(p[0]+1)*c.image_width_px/2 for p in projected]
            ys = [(1-p[1])*c.image_height_px/2 for p in projected]
            for actual, expected in zip((min(xs),min(ys),max(xs)-min(xs),max(ys)-min(ys)),c.metadata()['expected_bbox_xywh_px']):
                self.assertAlmostEqual(actual,expected,places=3)
            self.assertEqual(UsdGeom.GetStageMetersPerUnit(stage),unit)

    def test_oblique_ray_projection_and_gsd(self):
        for roll in (7.77,23.17):
            c = CalibrationConfig(**{**self.data,'target_width_m':1,'pitch_deg':30,'roll_deg':roll})
            self.assertEqual(len(c.targets()),9)
            for t in c.targets():
                for a,b in zip(c.project(t['center_world_m']),t['sample_image_px']):
                    self.assertAlmostEqual(a,b,places=8)
            gsd = [t['local_gsd_xy_cm_px'] for t in c.targets()]
            self.assertGreater(max(v[0] for v in gsd)-min(v[0] for v in gsd),0.01)
        c = CalibrationConfig(**{**self.data,'pitch_deg':30,'roll_deg':0})
        gx,gy = c.local_gsd(512,384)
        import math
        self.assertAlmostEqual(gx,1/math.cos(math.radians(30)),places=6)
        self.assertAlmostEqual(gy,1/math.cos(math.radians(30))**2,places=6)

    @unittest.skipIf(Usd is None, 'Requires pxr; run in Blender')
    def test_oblique_authored_camera_matches_independent_projection(self):
        for roll in (7.77,23.17):
            c = CalibrationConfig(**{**self.data,'target_width_m':1,'pitch_deg':30,'roll_deg':roll})
            stage = Usd.Stage.CreateInMemory()
            camera = build_stage(stage,c)
            frustum = camera.GetCamera(0).frustum
            vp = frustum.ComputeViewMatrix()*frustum.ComputeProjectionMatrix()
            for t in c.targets():
                points = UsdGeom.Mesh(stage.GetPrimAtPath('/Calibration/'+t['id'])).GetPointsAttr().Get()
                for point,expected in zip(points,t['expected_polygon_px']):
                    ndc = vp.Transform(Gf.Vec3d(point))
                    pixel = ((ndc[0]+1)*512,(1-ndc[1])*384)
                    for a,b in zip(pixel,expected):
                        self.assertAlmostEqual(a,b,places=3)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CalibrationTests))
    if not result.wasSuccessful():
        raise RuntimeError('Calibration tests failed')
