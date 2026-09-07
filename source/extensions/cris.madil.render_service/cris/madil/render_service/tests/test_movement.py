import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from movement import (
    move_toward,
    natural_swim_attitude,
    normalize_heading,
    turn_toward,
)


class MovementTests(unittest.TestCase):
    def test_normalize_heading_wraps_both_directions(self):
        self.assertEqual(normalize_heading(370), 10.0)
        self.assertEqual(normalize_heading(-10), 350.0)

    def test_move_toward_does_not_overshoot(self):
        self.assertEqual(move_toward(0, 3, 5), 3.0)
        self.assertEqual(move_toward(10, 0, 2), 8.0)

    def test_move_toward_treats_negative_delta_as_zero(self):
        self.assertEqual(move_toward(2, 10, -1), 2.0)

    def test_turn_toward_uses_shortest_path_across_zero(self):
        self.assertEqual(turn_toward(350, 10, 5), 355.0)
        self.assertEqual(turn_toward(10, 350, 5), 5.0)

    def test_turn_toward_stops_at_target(self):
        self.assertEqual(turn_toward(358, 2, 10), 2.0)

    def test_natural_attitude_pitches_into_vertical_motion(self):
        ascending_pitch, _ = natural_swim_attitude(5, 10, 0, 16, 12)
        descending_pitch, _ = natural_swim_attitude(-5, 10, 0, 16, 12)

        self.assertLess(ascending_pitch, 0.0)
        self.assertGreater(descending_pitch, 0.0)

    def test_natural_attitude_clamps_turn_bank(self):
        _, bank = natural_swim_attitude(0, 10, 100, 16, 12)

        self.assertEqual(bank, -12)


if __name__ == "__main__":
    unittest.main()
