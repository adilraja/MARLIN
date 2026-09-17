"""Capture/UI projection separation tests using Blender's USD runtime."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import importlib
import unittest
from types import SimpleNamespace
from test_hidef_marine import camera, Usd, Gf
from pxr import UsdGeom, UsdRender

geometry=importlib.import_module('_marine_test.calibration_geometry')
projection=importlib.import_module('_marine_test.capture_projection')


class ProjectionTests(unittest.TestCase):
    def test_explicit_product_ignores_ui_buffer_but_rejects_product_resize(self):
        stage,c,view,product=self.setup_case()
        view.resolution=(1280,720)
        record=projection.record_product_projection(stage,'/Render/Product','/Camera',(1644,548),view.time)
        self.assertEqual(record['render_product']['resolution'],[1644,548])
        product.GetResolutionAttr().Set(Gf.Vec2i(1280,720))
        with self.assertRaisesRegex(ValueError,'differs from request'):
            projection.record_product_projection(stage,'/Render/Product','/Camera',(1644,548),view.time)

    def test_explicit_product_rejects_wrong_camera_and_pixel_aspect(self):
        stage,c,view,product=self.setup_case()
        product.GetCameraRel().SetTargets(['/WrongCamera'])
        with self.assertRaises(ValueError):
            projection.record_product_projection(stage,'/Render/Product','/Camera',(1644,548),view.time)
        product.GetCameraRel().SetTargets(['/Camera'])
        product.CreatePixelAspectRatioAttr(2)
        with self.assertRaises(ValueError):
            projection.record_product_projection(stage,'/Render/Product','/Camera',(1644,548),view.time)

    def setup_case(self):
        stage=Usd.Stage.CreateInMemory()
        config=camera.configuration(7.7675)
        geometry.build_camera(stage,config,'/Camera')
        product=UsdRender.Product.Define(stage,'/Render/Product')
        product.CreateCameraRel().SetTargets(['/Camera'])
        product.CreateResolutionAttr(Gf.Vec2i(1644,548))
        view=SimpleNamespace(camera_path='/Camera',resolution=(1644,548),time=Usd.TimeCode.Default(),
            render_product_path='/Render/Product',view=Gf.Matrix4d(1),projection=Gf.Matrix4d(1))
        return stage,config,view,product

    def test_ui_aspect_cannot_change_image_projection(self):
        stage,c,view,_=self.setup_case()
        for ui_y_scale in (1,11.755952,19.592697,25):
            view.projection=Gf.Matrix4d(1)
            view.projection[1,1]=ui_y_scale
            record=projection.record_projection(stage,view)
            self.assertAlmostEqual(record['capture_projection_matrix'][1][1],25)
            self.assertEqual(record['ui_projection_matrix'][1][1],ui_y_scale)
            vp=Gf.Matrix4d(record['capture_view_matrix'])*Gf.Matrix4d(record['capture_projection_matrix'])
            for u,v in ((.5,.5),(822,274),(1643.5,547.5)):
                ndc=vp.Transform(Gf.Vec3d(*(x/.01 for x in c.ray_plane(u,v))))
                self.assertAlmostEqual((ndc[0]+1)*822,u,places=6)
                self.assertAlmostEqual((1-ndc[1])*274,v,places=6)

    def test_reject_mismatched_product(self):
        stage,c,view,product=self.setup_case()
        product.GetResolutionAttr().Set(Gf.Vec2i(1024,768))
        with self.assertRaises(ValueError): projection.record_projection(stage,view)
        product.GetResolutionAttr().Set(Gf.Vec2i(1644,548))
        product.GetCameraRel().SetTargets(['/WrongCamera'])
        with self.assertRaises(ValueError): projection.record_projection(stage,view)

    def test_reject_crop_and_pixel_aspect(self):
        stage,c,view,product=self.setup_case()
        product.CreatePixelAspectRatioAttr(2)
        with self.assertRaises(ValueError): projection.record_projection(stage,view)
        product.GetPixelAspectRatioAttr().Set(1)
        product.CreateDataWindowNDCAttr(Gf.Vec4f(.1,0,1,1))
        with self.assertRaises(ValueError): projection.record_projection(stage,view)

    def test_reject_aperture_aspect(self):
        stage,c,view,product=self.setup_case()
        UsdGeom.Camera(stage.GetPrimAtPath('/Camera')).GetVerticalApertureAttr().Set(24)
        with self.assertRaises(ValueError): projection.record_projection(stage,view)


if __name__=='__main__':
    unittest.main(argv=[sys.argv[0]])
