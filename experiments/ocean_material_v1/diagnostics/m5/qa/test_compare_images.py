"""Synthetic checks for the measurement tool; these are not M5 renderer results."""
import unittest

import numpy as np

from compare_images import metrics


class Measurements(unittest.TestCase):
    def setUp(self):
        self.zero = np.zeros((384, 512, 3), dtype=np.uint8)

    def test_exact_match(self):
        result = metrics(self.zero, self.zero.copy())
        self.assertTrue(result['image_tolerance_passed'])
        self.assertEqual(result['comparisons']['full_rgb']['maximum_absolute_difference_8bit'], 0)

    def test_inclusive_mean_limit(self):
        self.assertTrue(metrics(self.zero, self.zero + 1)['image_tolerance_passed'])
        self.assertFalse(metrics(self.zero, self.zero + 2)['image_tolerance_passed'])

    def test_uint8_subtraction_does_not_wrap(self):
        result = metrics(self.zero, self.zero + 255)
        self.assertEqual(result['comparisons']['full_rgb']['mean_absolute_difference_8bit'], 255)
        self.assertFalse(result['image_tolerance_passed'])

    def test_p99_can_fail_with_mean_below_limit(self):
        candidate = self.zero.copy()
        candidate[96:100, 128:384] = 9
        result = metrics(self.zero, candidate)
        roi = result['comparisons']['fixed_central_roi']
        self.assertLess(roi['mean_absolute_difference_8bit'], 1)
        self.assertEqual(roi['p99_absolute_difference_8bit'], 9)
        self.assertFalse(result['image_tolerance_passed'])

    def test_peripheral_changes_do_not_disappear_in_roi(self):
        candidate = self.zero.copy()
        candidate[:96] = 8
        result = metrics(self.zero, candidate)
        self.assertTrue(result['comparisons']['fixed_central_roi']['passed'])
        self.assertFalse(result['comparisons']['full_rgb']['passed'])
        self.assertFalse(result['image_tolerance_passed'])

    def test_refuses_resized_inputs(self):
        with self.assertRaises(ValueError):
            metrics(self.zero, np.zeros((192, 256, 3), dtype=np.uint8))

    def test_refuses_non_display_values(self):
        with self.assertRaises(ValueError):
            metrics(self.zero.astype(float), self.zero.astype(float))


if __name__ == '__main__':
    unittest.main()
