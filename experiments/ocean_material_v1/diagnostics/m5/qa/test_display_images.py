"""Verify the fixed display conversion, independently of any renderer outcome."""
import unittest

import numpy as np

from display_images import convert


class FixedDisplay(unittest.TestCase):
    def test_declared_scale_gamma_and_rounding(self):
        data = np.full((384, 512, 3), 3000., dtype=float)
        expected = round(255 * .25 ** (1 / 2.2))
        result = convert(data)
        self.assertEqual(result.dtype, np.uint8)
        self.assertTrue(np.all(result == expected))

    def test_clips_without_per_image_normalization(self):
        data = np.zeros((384, 512, 3), dtype=float)
        data[0, 0] = [-1., 12000., 24000.]
        result = convert(data)
        self.assertEqual(result[0, 0].tolist(), [0, 255, 255])
        self.assertEqual(int(result[1, 1].max()), 0)

    def test_refuses_nonfinite_and_wrong_dimensions(self):
        with self.assertRaises(ValueError):
            convert(np.zeros((192, 256, 3)))
        with self.assertRaises(ValueError):
            convert(np.full((384, 512, 3), np.nan))


if __name__ == '__main__':
    unittest.main()
