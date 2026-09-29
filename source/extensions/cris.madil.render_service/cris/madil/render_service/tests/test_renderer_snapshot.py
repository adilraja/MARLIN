"""Exercise renderer snapshots without importing Kit or touching live settings."""
import ast
import copy
import math
from pathlib import Path
from types import SimpleNamespace
import unittest


SOURCE = Path(__file__).resolve().parents[1]
TREE = ast.parse((SOURCE / 'hidef_marine.py').read_text())


def literal_assignment(filename, name):
    tree = ast.parse((SOURCE / filename).read_text())
    return next(ast.literal_eval(node.value) for node in tree.body
                if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == name
                        for target in node.targets))


class MemorySettings:
    def __init__(self, values):
        self.values = copy.deepcopy(values)
        self.writes = []

    def get(self, key):
        return copy.deepcopy(self.values.get(key))

    def set(self, key, value):
        self.writes.append(('set', key))
        self.values[key] = copy.deepcopy(value)

    def destroy_item(self, key):
        self.writes.append(('destroy', key))
        self.values.pop(key, None)


def isolated_functions(settings):
    """Compile actual pure functions and replay guard, omitting Kit imports."""
    names = {'settings_record', 'restore_settings', 'same_settings'}
    nodes = [node for node in TREE.body
             if (isinstance(node, ast.FunctionDef) and node.name in names)
             or (isinstance(node, ast.Assign)
                 and any(isinstance(target, ast.Name) and target.id == 'SETTING_KEYS'
                         for target in node.targets))]
    namespace = {
        'math': math,
        'carb': SimpleNamespace(settings=SimpleNamespace(get_settings=lambda: settings)),
        'UNDERWATER_FOG_SETTING_PATHS': literal_assignment(
            'underwater_cue.py', 'UNDERWATER_FOG_SETTING_PATHS'),
        'UNDERWATER_CUE_REQUESTED_SETTING': literal_assignment(
            'underwater_cue.py', 'UNDERWATER_CUE_REQUESTED_SETTING'),
        'RTX_WATER_SETTINGS': literal_assignment('water_material.py', 'RTX_WATER_SETTINGS'),
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE / 'hidef_marine.py'), 'exec'), namespace)

    run = next(node for node in TREE.body
               if isinstance(node, ast.AsyncFunctionDef) and node.name == '_run')
    replay = next(node for node in run.body
                  if isinstance(node, ast.If)
                  and ast.unparse(node.test) == 'replay_id is not None')
    start = next(index for index, node in enumerate(replay.body)
                 if isinstance(node, ast.Assign)
                 and any(isinstance(target, ast.Name) and target.id == 'saved_settings'
                         for target in node.targets))
    # Execute the production assignments and rejection guard, not a duplicate.
    guard = replay.body[start:start + 3]
    omission = next(node for node in replay.body
                    if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Subscript)
                            and ast.unparse(target) == "extra['renderer_settings_unverified_against_original_capture']"
                            for target in node.targets))
    template = ast.parse('def check_replay(before, saved):\n    extra = {}\n    return extra\n')
    template.body[0].body[1:1] = guard + [omission]
    exec(compile(ast.fix_missing_locations(template), str(SOURCE / 'hidef_marine.py'), 'exec'), namespace)
    return SimpleNamespace(**namespace)


class RendererSnapshotTests(unittest.TestCase):
    def test_sampling_color_and_effect_settings_are_recorded_without_defaults(self):
        settings = MemorySettings({'/rtx/pathtracing/optixDenoiser/enabled': False,
                                   '/rtx/post/tonemap/colorMode': 0})
        functions = isolated_functions(settings)
        record = functions.settings_record()
        for key in ('/rtx/pathtracing/adaptiveSampling/enabled',
                    '/rtx/pathtracing/optixDenoiser/enabled',
                    '/rtx/post/aa/op', '/rtx/post/tonemap/colorMode',
                    '/rtx/post/tonemap/ocio/cfgFilePath',
                    '/rtx/post/colorcorr/enabled', '/rtx/post/motionblur/enabled',
                    '/exts/cris.madil.render_service/underwaterCue/enabled'):
            self.assertIn(key, record)
        self.assertIs(record['/rtx/pathtracing/optixDenoiser/enabled'], False)
        self.assertEqual(record['/rtx/post/tonemap/colorMode'], 0)
        self.assertIsNone(record['/rtx/post/tonemap/ocio/cfgFilePath'])
        self.assertEqual(settings.writes, [])

    def test_roundtrip_restores_vectors_false_zero_and_absent_options(self):
        original = {'/rtx/post/colorcorr/gain': [1.0, 0.9, 1.1],
                    '/rtx/post/histogram/enabled': False,
                    '/rtx/post/tonemap/exposureBias': 0.0,
                    '/rtx/pathtracing/totalSpp': 512,
                    '/unrelated/setting': 'leave alone'}
        settings = MemorySettings(original)
        functions = isolated_functions(settings)
        before = functions.settings_record()
        settings.values.update({'/rtx/post/colorcorr/gain': [2, 2, 2],
                                '/rtx/post/histogram/enabled': True,
                                '/rtx/post/tonemap/exposureBias': 3,
                                '/rtx/pathtracing/totalSpp': 16,
                                '/rtx/post/tonemap/ocio/cfgFilePath': 'temporary.ocio'})
        functions.restore_settings(before)
        self.assertEqual(settings.values, original)
        self.assertTrue(functions.same_settings(before, functions.settings_record()))
        self.assertIn(('destroy', '/rtx/post/tonemap/ocio/cfgFilePath'), settings.writes)
        settings.writes.clear()
        functions.restore_settings(before)
        self.assertEqual(settings.writes, [])

    def test_legacy_replay_verifies_saved_subset_and_reports_omissions(self):
        functions = isolated_functions(MemorySettings({}))
        current = {'old': 1.0, 'new_sampling': False, 'new_color': None}
        saved = {'renderer_settings': {'old': 1.0}}
        result = functions.check_replay(current, saved)
        self.assertEqual(result['renderer_settings_unverified_against_original_capture'],
                         ['new_color', 'new_sampling'])
        with self.assertRaisesRegex(ValueError, 'Renderer settings differ'):
            functions.check_replay({**current, 'old': 2.0}, saved)
        # A legacy key that disappears from the current recorder is not ignored.
        with self.assertRaisesRegex(ValueError, 'Renderer settings differ'):
            functions.check_replay({}, saved)

    def test_replay_of_replay_retains_original_uncertainty(self):
        functions = isolated_functions(MemorySettings({}))
        current = {'old': 1.0, 'new_sampling': False}
        saved = {'renderer_settings': current,
                 'renderer_settings_unverified_against_original_capture': ['new_sampling']}
        result = functions.check_replay(current, saved)
        self.assertEqual(result['renderer_settings_unverified_against_original_capture'], ['new_sampling'])
        result = functions.check_replay(current, {'renderer_settings': current})
        self.assertEqual(result['renderer_settings_unverified_against_original_capture'], [])

    def test_preservation_check_stays_strict_for_current_keysets_and_types(self):
        functions = isolated_functions(MemorySettings({}))
        self.assertFalse(functions.same_settings({'old': 1, 'new': False}, {'old': 1}))
        self.assertFalse(functions.same_settings({'enabled': False}, {'enabled': 0}))
        self.assertTrue(functions.same_settings({'vector': [0.2, 1.0]},
                                               {'vector': (0.20000000298023224, 1.0)}))
        self.assertFalse(functions.same_settings({'exposure': 1.0}, {'exposure': 1.01}))


if __name__ == '__main__':
    unittest.main()
