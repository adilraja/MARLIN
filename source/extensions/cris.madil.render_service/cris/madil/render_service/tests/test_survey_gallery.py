"""Check display fitting without requiring the Kit runtime."""
import ast
import math
from pathlib import Path
import unittest

tree = ast.parse((Path(__file__).resolve().parents[1] / 'survey_gallery.py').read_text())
function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'inspection_transform')
namespace = {'math': math}
exec(compile(ast.Module(body=[function], type_ignores=[]), '<inspection_transform>', 'exec'), namespace)
fit = namespace['inspection_transform']


class SurveyGalleryTests(unittest.TestCase):
    def test_offset_model_fits_center_and_maximum_extent(self):
        minimum, maximum = (10, -2, 20), (14, 0, 21)
        target = (1200, 800, -1200)
        scale, position = fit(minimum, maximum, target, 700)
        self.assertEqual(scale, 175)
        center = [position[i] + scale * (minimum[i] + maximum[i]) / 2 for i in range(3)]
        self.assertEqual(center, list(target))

    def test_invalid_bounds_fail(self):
        for minimum, maximum in [((0,0,0),(0,0,0)), ((1,0,0),(0,1,1)), ((math.inf,0,0),(1,1,1))]:
            with self.assertRaises(ValueError):
                fit(minimum, maximum, (0,800,0), 700)
