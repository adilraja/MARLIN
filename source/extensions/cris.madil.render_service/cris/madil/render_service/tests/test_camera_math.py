import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from camera_math import (
    chase_camera_targets,
    damp_point,
    damping_alpha,
    documentary_camera_transition,
    horizontal_distance,
    move_point_with_acceleration,
)


class CameraMathTests(unittest.TestCase):
    def test_damping_is_frame_rate_independent(self):
        full_step = damping_alpha(3.0, 1.0)
        half_step = damping_alpha(3.0, 0.5)

        self.assertAlmostEqual(
            1.0 - full_step,
            (1.0 - half_step) ** 2,
        )

    def test_damp_point_moves_toward_target(self):
        result = damp_point((0.0, 0.0, 0.0), (10.0, 5.0, -2.0), 2.0, 0.1)

        self.assertGreater(result[0], 0.0)
        self.assertLess(result[0], 10.0)
        self.assertGreater(result[1], 0.0)
        self.assertLess(result[2], 0.0)

    def test_chase_camera_sits_behind_heading_zero(self):
        camera, target = chase_camera_targets(
            target_position=(0.0, -20.0, 0.0),
            forward=(0.0, 0.0, 1.0),
            distance=600.0,
            height=180.0,
            side_offset=0.0,
            look_ahead=150.0,
            look_height=15.0,
        )

        self.assertEqual(camera, (0.0, 160.0, -600.0))
        self.assertEqual(target, (0.0, -5.0, 150.0))

    def test_chase_camera_normalizes_horizontal_forward(self):
        camera, _ = chase_camera_targets(
            target_position=(1.0, 2.0, 3.0),
            forward=(10.0, 50.0, 0.0),
            distance=100.0,
            height=20.0,
            side_offset=0.0,
            look_ahead=0.0,
            look_height=0.0,
        )

        self.assertEqual(camera, (-99.0, 22.0, 3.0))

    def test_horizontal_error_ignores_wave_height(self):
        self.assertEqual(
            horizontal_distance((1.0, -100.0, 2.0), (4.0, 500.0, 6.0)),
            5.0,
        )

    def test_documentary_camera_holds_then_delays(self):
        self.assertEqual(
            documentary_camera_transition(
                "HOLD", 3.0, 100.0, 4.0, 30.0, 0.8, 12.0, 1.2
            ),
            "HOLD",
        )
        self.assertEqual(
            documentary_camera_transition(
                "HOLD", 4.0, 100.0, 4.0, 30.0, 0.8, 12.0, 1.2
            ),
            "DELAY",
        )

    def test_documentary_camera_runs_full_state_cycle(self):
        self.assertEqual(
            documentary_camera_transition(
                "DELAY", 0.8, 50.0, 4.0, 30.0, 0.8, 12.0, 1.2
            ),
            "CATCH_UP",
        )
        self.assertEqual(
            documentary_camera_transition(
                "CATCH_UP", 2.0, 10.0, 4.0, 30.0, 0.8, 12.0, 1.2
            ),
            "SETTLE",
        )
        self.assertEqual(
            documentary_camera_transition(
                "SETTLE", 1.2, 5.0, 4.0, 30.0, 0.8, 12.0, 1.2
            ),
            "HOLD",
        )

    def test_accelerated_motion_respects_acceleration_and_no_overshoot(self):
        position, velocity = move_point_with_acceleration(
            current=(0.0, 0.0, 0.0),
            target=(10.0, 0.0, 0.0),
            velocity=(0.0, 0.0, 0.0),
            max_speed=20.0,
            acceleration=2.0,
            dt=1.0,
        )

        self.assertEqual(velocity, (2.0, 0.0, 0.0))
        self.assertEqual(position, (2.0, 0.0, 0.0))

        position, velocity = move_point_with_acceleration(
            current=(9.9, 0.0, 0.0),
            target=(10.0, 0.0, 0.0),
            velocity=(10.0, 0.0, 0.0),
            max_speed=20.0,
            acceleration=2.0,
            dt=1.0,
        )

        self.assertEqual(position, (10.0, 0.0, 0.0))
        self.assertEqual(velocity, (0.0, 0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
