"""Exercise verifier rejection paths without importing Blender/Kit/NumPy.

Compile the actual small, pure evidence validators from the verifier AST; the
USD import and module-level runtime initialization are deliberately excluded.
"""
import ast
import copy
from pathlib import Path
import types
import unittest


PATH = Path(__file__).with_name('verify_m3_reconstruction.py')
names = {'EXPECTED_SCENE_IDS', 'EXPECTED_PREVIEW_NAMES', '_named_records',
         'validate_replay_coverage', 'validate_preview_coverage', 'validate_scene'}
tree = ast.parse(PATH.read_text())
nodes = [node for node in tree.body
         if (isinstance(node, ast.FunctionDef) and node.name in names)
         or (isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in names for target in node.targets))]
namespace = {}
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(PATH), 'exec'), namespace)
validate_replay = namespace['validate_replay_coverage']
validate_preview = namespace['validate_preview_coverage']


def replay_fixture():
    index = [{'scene_id': name} for name in sorted(namespace['EXPECTED_SCENE_IDS'])]
    entries = []
    for name in sorted(namespace['EXPECTED_SCENE_IDS']):
        runs = []
        for attempt in (0, 1):
            run = {'attempt': attempt}
            for phase in ('immediate', 'after_wait'):
                run[phase] = {'ok': True, 'checkpoint_id': f'checkpoint_{name}_{attempt}_{phase}'}
            runs.append(run)
        entries.append({'scene_id': name, 'runs': runs})
    return index, {'results': entries}


def preview_fixture():
    gallery = {'animals': [{'name': name} for name in sorted(namespace['EXPECTED_PREVIEW_NAMES'])]}
    return {'passed': True, 'swim_started': True, 'gallery_loaded_count': 11,
            'before': {'gallery': copy.deepcopy(gallery)},
            'after': {'gallery': copy.deepcopy(gallery)}}


class ReconstructionContractTests(unittest.TestCase):
    def test_complete_evidence_in_any_order_passes(self):
        index, live = replay_fixture()
        live['results'].reverse()
        for entry in live['results']:
            entry['runs'].reverse()
        self.assertEqual(set(validate_replay(index, live)), namespace['EXPECTED_SCENE_IDS'])
        self.assertTrue(validate_preview(preview_fixture()))

    def test_empty_missing_duplicate_or_unknown_replay_scenes_rejected(self):
        for mutation in ('empty', 'missing', 'duplicate', 'unknown'):
            index, live = replay_fixture()
            if mutation == 'empty': live['results'] = []
            elif mutation == 'missing': live['results'].pop()
            elif mutation == 'duplicate': live['results'][-1] = copy.deepcopy(live['results'][0])
            else: live['results'][-1]['scene_id'] = 'harbour_porpoise_0001'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_replay(index, live)

    def test_index_coverage_and_uniqueness_rejected(self):
        for mutation in ('empty', 'missing', 'duplicate', 'unknown'):
            index, live = replay_fixture()
            if mutation == 'empty': index = []
            elif mutation == 'missing': index.pop()
            elif mutation == 'duplicate': index[-1] = copy.deepcopy(index[0])
            else: index[-1]['scene_id'] = 'european_storm_petrel_0001'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_replay(index, live)

    def test_missing_duplicate_and_boolean_attempts_rejected(self):
        for mutation in ('missing', 'duplicate', 'boolean', 'wrong_number'):
            index, live = replay_fixture()
            runs = live['results'][0]['runs']
            if mutation == 'missing': runs.pop()
            elif mutation == 'duplicate': runs[-1]['attempt'] = 0
            elif mutation == 'boolean': runs[0]['attempt'] = False
            else: runs[-1]['attempt'] = 2
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_replay(index, live)

    def test_missing_failed_or_reused_checkpoint_rejected(self):
        for mutation in ('missing', 'failed', 'duplicate', 'not_object'):
            index, live = replay_fixture()
            run = live['results'][0]['runs'][0]
            if mutation == 'missing': del run['after_wait']
            elif mutation == 'failed': run['after_wait']['ok'] = False
            elif mutation == 'duplicate': run['after_wait'] = copy.deepcopy(run['immediate'])
            else: run['after_wait'] = None
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_replay(index, live)

    def test_preview_requires_all_default_animals_in_both_phases(self):
        for phase in ('before', 'after'):
            for mutation in ('empty', 'missing', 'duplicate', 'unknown'):
                report = preview_fixture()
                animals = report[phase]['gallery']['animals']
                if mutation == 'empty': animals.clear()
                elif mutation == 'missing': animals.pop()
                elif mutation == 'duplicate': animals[-1] = copy.deepcopy(animals[0])
                else: animals[-1]['name'] = 'Different_Animal'
                with self.subTest(phase=phase, mutation=mutation), self.assertRaises(ValueError):
                    validate_preview(report)

    def test_preview_success_and_exact_integer_count_required(self):
        for key, value in (('passed', False), ('swim_started', False),
                           ('gallery_loaded_count', 10), ('gallery_loaded_count', 11.0),
                           ('gallery_loaded_count', True)):
            report = preview_fixture()
            report[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_preview(report)

    def test_extra_visibility_or_material_relationship_is_rejected(self):
        def prim(attributes, relationships):
            return types.SimpleNamespace(
                GetPath=lambda: '/World/Target', GetTypeName=lambda: 'Mesh',
                GetAuthoredAttributes=lambda: [types.SimpleNamespace(GetName=lambda n=n: n) for n in attributes],
                GetAuthoredRelationships=lambda: [types.SimpleNamespace(GetName=lambda n=n: n) for n in relationships])
        namespace['UsdGeom'] = types.SimpleNamespace(GetStageMetersPerUnit=lambda stage: .01,
                                                   GetStageUpAxis=lambda stage: 'Y')
        expected = types.SimpleNamespace(Traverse=lambda: [prim([], [])])
        for attrs, rels in ((['visibility'], []), ([], ['material:binding'])):
            actual = types.SimpleNamespace(Traverse=lambda: [prim(attrs, rels)])
            with self.subTest(attributes=attrs, relationships=rels), self.assertRaisesRegex(ValueError, 'set changed'):
                namespace['validate_scene'](expected, actual)


if __name__ == '__main__':
    unittest.main()
