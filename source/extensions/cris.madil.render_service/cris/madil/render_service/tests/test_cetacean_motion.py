"""Checks for gallery locomotion profiles and deformation math."""

import math
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cetacean_motion import (
    GALLERY_MOTION_PROFILES,
    inferred_model_forward_heading,
    tail_flex_envelope,
    vertical_wave_offset,
)


class CetaceanMotionTests(unittest.TestCase):
    def test_every_gallery_species_has_a_motion_profile(self):
        expected = {
            "bottlenose_dolphin",
            "cuvier_whale",
            "frasers_dolphin",
            "humpback_whale",
            "manatee",
            "model_61a_-_bottlenose_dolphin",
            "pantropical_spotted_dolphin",
            "pilot_whale",
            "pygmy_sperm_whale",
            "sperm_whale",
            "steno_dolphin",
        }
        self.assertEqual(set(GALLERY_MOTION_PROFILES), expected)

    def test_only_rigged_digital_life_asset_uses_skeletal_backend(self):
        skeletal = {
            species
            for species, profile in GALLERY_MOTION_PROFILES.items()
            if profile["backend"] == "skeletal"
        }
        self.assertEqual(
            skeletal,
            {"model_61a_-_bottlenose_dolphin"},
        )

    def test_torso_stays_rigid_and_tail_reaches_full_envelope(self):
        self.assertEqual(tail_flex_envelope(0.2, 0.35), 0.0)
        self.assertEqual(tail_flex_envelope(0.35, 0.35), 0.0)
        self.assertAlmostEqual(tail_flex_envelope(1.0, 0.35), 1.0)

    def test_wave_is_dorsoventral_and_periodic(self):
        values = [
            vertical_wave_offset(
                1.0,
                phase,
                body_length=10.0,
                amplitude_ratio=0.1,
                wave_cycles=1.0,
                flex_start=0.3,
            )
            for phase in (0.0, math.pi / 2.0, math.tau)
        ]
        self.assertAlmostEqual(values[0], 0.0, places=7)
        self.assertAlmostEqual(values[1], 1.0, places=7)
        self.assertAlmostEqual(values[2], 0.0, places=7)

    def test_forward_heading_accounts_for_opposite_tail_ends(self):
        self.assertEqual(inferred_model_forward_heading(1, True), 0.0)
        self.assertEqual(inferred_model_forward_heading(1, False), 180.0)

    def test_forward_heading_handles_horizontal_x_aligned_assets(self):
        self.assertEqual(inferred_model_forward_heading(0, True), 270.0)
        self.assertEqual(inferred_model_forward_heading(0, False), 90.0)


if __name__ == "__main__":
    unittest.main()
