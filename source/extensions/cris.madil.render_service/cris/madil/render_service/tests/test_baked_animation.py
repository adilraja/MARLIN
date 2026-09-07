import json
import unittest
from pathlib import Path


class BakedDolphinAnimationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        project_root = Path(__file__).resolve().parents[7]
        animation_path = (
            project_root
            / "assets/cetaceans/bottlenose_dolphin/animation/swim_cycle.json"
        )
        cls.animation = json.loads(animation_path.read_text(encoding="utf-8"))

    def test_authored_cycle_contains_full_rig_and_frame_range(self):
        self.assertEqual(self.animation["name"], "Swim Cycle")
        self.assertEqual(
            self.animation["transform_space"],
            "rest_relative",
        )
        self.assertEqual(len(self.animation["bone_names"]), 20)
        self.assertEqual(len(self.animation["frames"]), 31)
        self.assertEqual(self.animation["fps"], 24.0)

    def test_tail_joints_change_during_cycle(self):
        tail_index = self.animation["bone_names"].index("spine.007_12")
        rotations = {
            tuple(frame["rotations"][tail_index])
            for frame in self.animation["frames"]
        }

        self.assertGreater(len(rotations), 2)


if __name__ == "__main__":
    unittest.main()
