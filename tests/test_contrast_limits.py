import math
import sys
import unittest

from cyto_studio.utilities import safe_contrast_limits


class ContrastLimitsTests(unittest.TestCase):
    def test_blank_channel_remains_safe_when_brightness_changes(self):
        for brightness in (0, 0.0001, 0.2, 1, 3):
            with self.subTest(brightness=brightness):
                self.assertEqual(safe_contrast_limits([0, 0], brightness), [0, 1])

    def test_normal_range_preserves_brightness(self):
        self.assertEqual(safe_contrast_limits([0, 30000], 0.2), [0, 6000])
        self.assertEqual(safe_contrast_limits([-5, 10], 0.5), [-5, 5])

    def test_brightness_cannot_collapse_or_reverse_range(self):
        self.assertEqual(safe_contrast_limits([5, 10], 0.2), [5, 10])
        self.assertEqual(safe_contrast_limits([0, 10], 0), [0, 10])

    def test_degenerate_and_nonfinite_limits_are_valid(self):
        cases = ([5, 5], [-5, -5], [10, 5], [float('nan'), float('nan')],
                 [0, float('inf')], [float('-inf'), 10],
                 [sys.float_info.max, sys.float_info.max])
        for value_range in cases:
            with self.subTest(value_range=value_range):
                lower, upper = safe_contrast_limits(value_range)
                self.assertTrue(math.isfinite(lower))
                self.assertTrue(math.isfinite(upper))
                self.assertLess(lower, upper)

    def test_nonfinite_brightness_uses_original_range(self):
        for brightness in (float('nan'), float('inf')):
            self.assertEqual(safe_contrast_limits([0, 10], brightness), [0, 10])


if __name__ == '__main__':
    unittest.main()
