import unittest

from underwater_cue import (
    DEFAULT_UNDERWATER_FOG_SETTINGS,
    UNDERWATER_CUE_REQUESTED_SETTING,
    UNDERWATER_FOG_SETTING_PATHS,
    UnderwaterCueParameters,
    underwater_fog_settings,
)


class UnderwaterCueTests(unittest.TestCase):
    def test_underwater_cue_uses_marlin_y_up_axis(self):
        settings = underwater_fog_settings(UnderwaterCueParameters())

        self.assertTrue(settings["/rtx/fog/enabled"])
        self.assertFalse(settings["/rtx/fog/fogZup/enabled"])
        self.assertEqual(settings["/rtx/fog/fogStartHeight"], 0.0)

    def test_underwater_cue_defaults_are_subtle_and_blue_green(self):
        settings = underwater_fog_settings(UnderwaterCueParameters())
        color = settings["/rtx/fog/fogColor"]

        self.assertGreater(color[2], color[1])
        self.assertGreater(color[1], color[0])
        self.assertLess(settings["/rtx/fog/fogHeightDensity"], 1.0)
        self.assertGreater(settings["/rtx/fog/fogHeightDensity"], 0.0)
        self.assertLess(settings["/rtx/fog/fogDistanceDensity"], 1.0)
        self.assertGreater(settings["/rtx/fog/fogDistanceDensity"], 0.0)

    def test_underwater_cue_maps_every_reported_setting(self):
        settings = underwater_fog_settings(
            UnderwaterCueParameters(enabled=False, surface_height=12.5)
        )

        self.assertEqual(tuple(settings), UNDERWATER_FOG_SETTING_PATHS)
        self.assertFalse(settings["/rtx/fog/enabled"])
        self.assertEqual(settings["/rtx/fog/fogStartHeight"], 12.5)

    def test_runtime_ownership_setting_is_extension_scoped(self):
        self.assertEqual(
            UNDERWATER_CUE_REQUESTED_SETTING,
            "/exts/cris.madil.render_service/underwaterCue/enabled",
        )

    def test_marlin_startup_profile_is_enabled_by_default(self):
        self.assertEqual(
            DEFAULT_UNDERWATER_FOG_SETTINGS,
            underwater_fog_settings(UnderwaterCueParameters()),
        )
        self.assertTrue(
            DEFAULT_UNDERWATER_FOG_SETTINGS["/rtx/fog/enabled"]
        )


if __name__ == "__main__":
    unittest.main()
