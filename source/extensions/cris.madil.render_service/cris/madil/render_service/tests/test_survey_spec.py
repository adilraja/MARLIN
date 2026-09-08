import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from survey_spec import (CameraConfig, PROJECT_ROOT, asset_inventory, condition_seed,
                         load_spec, nadir_altitude_m, nadir_gsd_cm_px,
                         projected_length_pixels, validate_split_records)


class SurveySpecTests(unittest.TestCase):
    def test_reference_config_and_missing_camera_fields(self):
        spec = load_spec()
        camera = CameraConfig(**spec['cameras']['hidef'])
        self.assertEqual(camera.image_size_px, [6576, 2192])
        self.assertEqual(camera.readiness_gaps(), ['pixel_pitch_um', 'pose_convention'])

    def test_physical_calculations_and_bird_height(self):
        # Hypothetical pinhole with 5 um pitch and 100 mm lens at 100 m.
        self.assertAlmostEqual(nadir_gsd_cm_px(100, 100, 5), 0.5)
        self.assertAlmostEqual(nadir_gsd_cm_px(100, 100, 5, 20), 0.4)
        self.assertAlmostEqual(nadir_altitude_m(0.4, 100, 5, 20), 100)
        self.assertAlmostEqual(projected_length_pixels(1, 0.5), 200)
        for height in (-1, 100, math.nan, math.inf):
            with self.assertRaises(ValueError):
                nadir_gsd_cm_px(100, 100, 5, height)
        with self.assertRaises(ValueError):
            nadir_altitude_m(1, 100, 0)

    def test_invalid_camera_inputs(self):
        camera = load_spec()['cameras']['hidef']
        for field, value in [('pixel_pitch_um', 0), ('altitude_m', math.nan),
                             ('image_size_px', [1.5, 10]), ('pitch_deg', 90)]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                CameraConfig(**{**camera, field: value})

    def test_gsd_independent_repeatable_seed(self):
        self.assertEqual(condition_seed(42, 'scene'), condition_seed(42, 'scene'))
        self.assertNotEqual(condition_seed(42, 'scene'), condition_seed(42, 'other'))

    def test_each_split_identity_prevents_leakage(self):
        first = dict(split='train', scene_id='s1', asset_instance_id='a1', sequence_id='q1', condition_id='c1')
        other = dict(split='test', scene_id='s2', asset_instance_id='a2', sequence_id='q2', condition_id='c2')
        validate_split_records([first, other])
        for field in ('scene_id', 'asset_instance_id', 'sequence_id', 'condition_id'):
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_split_records([first, {**other, field: first[field]}])

    def test_inventory_and_provenance(self):
        assets = asset_inventory()
        self.assertEqual(len(assets), 11)
        self.assertEqual(sum(a['available'] for a in assets), 6)
        self.assertFalse(any(a['render_ready'] for a in assets))
        birds = [a for a in assets if a['kind'] == 'avian']
        self.assertEqual(len(birds), 7)
        self.assertEqual(len({a['group_id'] for a in birds}), 6)
        for asset in assets:
            if asset['available']:
                self.assertTrue((PROJECT_ROOT / asset['source_path']).is_file())
                self.assertTrue((PROJECT_ROOT / asset['provenance']['license_path']).is_file())

    def test_reject_changed_environment_or_oblique_geometry(self):
        for section, key, value in [('environment', 'sun_glint', True),
                                    ('randomisation', 'strategy', 'independent'),
                                    ('splits', 'ratios', {'train': 0.8, 'validation': 0.2, 'test': 0.2})]:
            spec = load_spec()
            spec[section][key] = value
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'spec.json'
                path.write_text(json.dumps(spec))
                with self.assertRaises(ValueError):
                    load_spec(path)


if __name__ == '__main__':
    unittest.main()
