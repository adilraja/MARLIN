import unittest
import numpy as np
from analyse_medium import BACKGROUNDS, TARGET, measure


class MeasurementTests(unittest.TestCase):
    def test_known_signal_and_contrast_with_distractor(self):
        a = np.full((384, 512, 4), .5)
        a[184:200, 248:264, :3] = [2.5, 1.5, 1]
        a[0:100, 0:100, :3] = 10000  # Outside all declared ROIs.
        result = measure(a)
        np.testing.assert_allclose(result['signal_rgb'], [2, 1, .5])
        np.testing.assert_allclose(result['michelson_rgb'], [2/3, .5, 1/3])

    def test_both_background_patches_contribute(self):
        a = np.ones((384, 512, 3))
        a[184:200, 190:206, :] = 0
        a[184:200, 306:322, :] = .5
        np.testing.assert_allclose(measure(a)['background_rgb'], [.25]*3)

    def test_invalid_size_or_nonfinite_rejected(self):
        with self.assertRaises(ValueError):
            measure(np.ones((383, 512, 4)))
        a = np.ones((384, 512, 4)); a[0, 0, 0] = np.nan
        with self.assertRaises(ValueError):
            measure(a)

    def test_black_frame_has_finite_zero_contrast(self):
        self.assertEqual(measure(np.zeros((384, 512, 3)))['michelson_rgb'], [0, 0, 0])


if __name__ == '__main__':
    unittest.main()
