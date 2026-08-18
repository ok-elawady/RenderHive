from __future__ import annotations

import unittest

from core.smooth_progress import SmoothProgressValue


class SmoothProgressValueTests(unittest.TestCase):
    def test_walks_through_every_integer_without_skipping(self):
        value = SmoothProgressValue()
        value.reset(1.0)
        value.set_target(100.0)
        seen = [value.display_percent]
        while not value.settled:
            value.tick(0.8)
            current = value.display_percent
            if current != seen[-1]:
                seen.append(current)
        self.assertEqual(seen, list(range(1, 101)))

    def test_never_moves_past_real_target(self):
        value = SmoothProgressValue()
        value.reset(1.0)
        value.set_target(25.0)
        for _ in range(1000):
            value.tick(0.5)
        self.assertEqual(value.current, 25.0)
        self.assertEqual(value.display_percent, 25)
        self.assertEqual(value.bar_value, 250)

    def test_target_is_monotonic_by_default(self):
        value = SmoothProgressValue(20.0, 20.0)
        value.set_target(60.0)
        value.set_target(30.0)
        self.assertEqual(value.target, 60.0)

    def test_bar_has_sub_percent_resolution(self):
        value = SmoothProgressValue(12.3, 12.3)
        self.assertEqual(value.display_percent, 12)
        self.assertEqual(value.bar_value, 123)


if __name__ == '__main__':
    unittest.main()
