"""Host-independent scope and preset regressions; live rendering needs Kit QA."""
import ast
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'gentle_environment.py'
TREE = ast.parse(SOURCE.read_text())


class GentleEnvironmentTests(unittest.TestCase):
    def test_gentle_waves_and_diffuse_sky(self):
        preset = next(ast.literal_eval(n.value) for n in TREE.body
                      if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'PRESET' for t in n.targets))
        self.assertGreater(preset['wave_height'], 0)
        self.assertLessEqual(preset['wave_height'], 20)
        self.assertGreater(preset['speed'], 0)
        self.assertEqual(preset['sun_intensity'], 0)
        self.assertEqual(preset['sky_color'], (1, 1, 1))

    def test_no_actor_camera_or_exposure_control(self):
        source = SOURCE.read_text()
        for forbidden in ('start_gallery_swimming', 'shutdown_gallery_swimming',
                          'camera_path =', 'exposureBias', 'filmIso', 'rendermode'):
            self.assertNotIn(forbidden, source)

    def test_restore_scope_excludes_animals(self):
        paths = next(ast.literal_eval(n.value) for n in TREE.body
                     if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'PATHS' for t in n.targets))
        self.assertEqual(paths, ('/World/Ocean', '/World/Looks/OceanWater', '/World/Environment'))

    def test_phase_reset_and_stage_guard_documented(self):
        source = SOURCE.read_text()
        self.assertIn("_saved['stage'] != stage", source)
        self.assertIn('phase restart', source)


if __name__ == '__main__':
    unittest.main()
