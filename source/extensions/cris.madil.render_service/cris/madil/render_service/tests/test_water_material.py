import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from water_material import (
    RTX_WATER_SETTINGS,
    OmniSurfaceWaterParameters,
    omnisurface_inputs,
)


class WaterMaterialTests(unittest.TestCase):
    def test_defaults_author_physical_water_transmission(self):
        data = OmniSurfaceWaterParameters()
        inputs = omnisurface_inputs(data)

        self.assertEqual(data.ior, 1.333)
        self.assertEqual(inputs["enable_specular_transmission"], ("bool", True))
        self.assertEqual(inputs["specular_transmission_weight"], ("float", 1.0))
        self.assertEqual(inputs["diffuse_reflection_weight"], ("float", 0.02))

    def test_absorption_and_scattering_are_authored(self):
        data = OmniSurfaceWaterParameters(
            transmission_depth=250.0,
            scattering_color=(0.01, 0.02, 0.03),
            scattering_anisotropy=0.2,
        )
        inputs = omnisurface_inputs(data)

        self.assertEqual(
            inputs["specular_transmission_scattering_depth"],
            ("float", 250.0),
        )
        self.assertEqual(
            inputs["specular_transmission_scattering_color"],
            ("color3f", (0.01, 0.02, 0.03)),
        )
        self.assertEqual(
            inputs["specular_transmission_scatter_anisotropy"],
            ("float", 0.2),
        )

    def test_thin_walled_remains_configurable_for_open_surface(self):
        inputs = omnisurface_inputs(
            OmniSurfaceWaterParameters(thin_walled=False)
        )
        self.assertEqual(inputs["thin_walled"], ("bool", False))

    def test_validation_settings_prevent_zero_bounce_refraction(self):
        self.assertTrue(RTX_WATER_SETTINGS["/rtx/translucency/enabled"])
        self.assertGreaterEqual(
            RTX_WATER_SETTINGS[
                "/rtx/pathtracing/maxSpecularAndTransmissionBounces"
            ],
            8,
        )
        self.assertGreaterEqual(
            RTX_WATER_SETTINGS["/rtx/rtpt/maxSpecularAndTransmissionBounces"],
            8,
        )


if __name__ == "__main__":
    unittest.main()
