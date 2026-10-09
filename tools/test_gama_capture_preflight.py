"""GPU headroom collection boundary; no Kit runtime or renderer is started."""
import importlib
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
package = types.ModuleType('_gama_preflight_test')
package.__path__ = [str(ROOT / 'source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge')]
sys.modules[package.__name__] = package
paired = importlib.import_module(package.__name__ + '.paired_v2')


class CapturePreflightTests(unittest.TestCase):
    def test_collects_unreachable_helpers_before_unchanged_headroom_check(self):
        events = []
        runtime = object.__new__(paired.KitRuntime)
        record = {'free_mib': 900}
        runtime.marine = types.SimpleNamespace(gpu_preflight=lambda: events.append('headroom') or record)
        retained = {'cache': object(), 'original_stage': object()}
        with patch.object(paired, '_recovery_caches', [retained]), patch.object(
                paired.gc, 'collect', side_effect=lambda: events.append('collect')):
            self.assertIs(runtime.preflight(), record)
            self.assertEqual(paired._recovery_caches, [retained])
        self.assertEqual(events, ['collect', 'headroom'])

    def test_insufficient_headroom_still_refuses_capture(self):
        runtime = object.__new__(paired.KitRuntime)
        def refuse():
            raise ValueError('Insufficient GPU headroom before capture')
        runtime.marine = types.SimpleNamespace(gpu_preflight=refuse)
        with patch.object(paired.gc, 'collect') as collect, self.assertRaisesRegex(ValueError, 'Insufficient GPU'):
            runtime.preflight()
        collect.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
