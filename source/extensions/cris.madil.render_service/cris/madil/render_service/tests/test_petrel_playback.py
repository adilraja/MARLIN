"""Run with Blender's Python for the installed pxr runtime."""
import importlib.util
from pathlib import Path
import unittest

try:
    from pxr import Usd, UsdGeom, UsdSkel
except ImportError:
    Usd = None


@unittest.skipIf(Usd is None, 'Requires pxr (run in Blender)')
class PetrelPlaybackTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('petrel_playback', Path(__file__).resolve().parents[1] / 'petrel_playback.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.module = module
        self.stage = Usd.Stage.CreateInMemory()
        for name in ('PetrelRigTest', 'OtherBird'):
            UsdGeom.Xform.Define(self.stage, '/World/Cetaceans/' + name).GetPrim().GetReferences().AddReference(str(module.ASSET))
        self.original = self.stage.GetRootLayer().ExportToString()
        self.player = module.PetrelPlayback(self.stage)

    def tearDown(self):
        self.player.close()

    def rotations(self, time=0):
        return self.player.output.GetRotationsAttr().Get(time)

    def test_loop_pause_speed_and_timeline_independence(self):
        initial = self.rotations()
        self.player.advance(0.5)
        self.assertNotEqual(initial, self.rotations())
        self.assertEqual(self.rotations(0), self.rotations(999))
        self.player.control('pause')
        held = self.rotations()
        self.player.advance(10)
        self.assertEqual(held, self.rotations())
        self.assertEqual(self.player.phase, 0.5)
        self.player.control('resume', speed=2)
        self.player.advance(0.75)
        self.assertAlmostEqual(self.player.phase, 0)
        self.assertEqual(initial, self.rotations())

    def test_smooth_transition_and_reversal(self):
        self.player.advance(0.5)
        before = self.rotations()
        self.player.control(mode='glide', transition_seconds=1)
        self.assertEqual(before, self.rotations())
        self.player.advance(0.5)
        self.assertAlmostEqual(self.player.blend, 0.5)
        self.player.control(mode='flap', transition_seconds=1)
        self.assertAlmostEqual(self.player.blend, 0.5)
        self.player.advance(1)
        self.assertEqual(self.player.blend, 1)
        self.player.control(mode='glide', transition_seconds=0)
        self.assertEqual(self.rotations(), self.player.clip.GetRotationsAttr().Get(self.player.first))

    def test_isolation_cleanup_and_no_time_samples(self):
        self.player.advance(1.5)
        self.assertEqual(self.stage.GetRootLayer().ExportToString(), self.original)
        self.assertEqual(self.player.output.GetRotationsAttr().GetTimeSamples(), [])
        self.assertTrue(self.player.is_valid())
        self.player.close()
        self.assertFalse(self.stage.GetPrimAtPath(self.player.animation_path))
        self.assertEqual(list(self.stage.GetSessionLayer().subLayerPaths), [])
        self.assertEqual(self.stage.GetRootLayer().ExportToString(), self.original)

    def test_validation(self):
        for args in ({'speed': float('nan')}, {'speed': 0}, {'mode': 'dive'}, {'transition_seconds': float('inf')}):
            with self.assertRaises(ValueError):
                self.player.control(**args)
        for dt in (-1, float('nan')):
            with self.assertRaises(ValueError):
                self.player.advance(dt)
        with self.assertRaises(ValueError):
            self.module.PetrelPlayback(self.stage, '../Ocean')

    def test_pose_export_rejected(self):
        path = '/World/Cetaceans/StaticBird'
        UsdGeom.Xform.Define(self.stage, path).GetPrim().GetReferences().AddReference(str(self.module.ASSET.parent / 'wings_up.usd'))
        with self.assertRaisesRegex(ValueError, 'static pose'):
            self.module.PetrelPlayback(self.stage, 'StaticBird')

    def test_removed_target_and_independent_instances(self):
        second = self.module.PetrelPlayback(self.stage, 'OtherBird')
        try:
            self.player.advance(0.5)
            self.assertEqual(second.phase, 0)
            self.assertNotEqual(self.rotations(), second.output.GetRotationsAttr().Get())
            self.stage.RemovePrim('/World/Cetaceans/PetrelRigTest')
            self.assertFalse(self.player.is_valid())
            self.assertTrue(second.is_valid())
            self.player.close()
            self.assertTrue(second.is_valid())
        finally:
            second.close()


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PetrelPlaybackTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise RuntimeError('Petrel playback tests failed')
