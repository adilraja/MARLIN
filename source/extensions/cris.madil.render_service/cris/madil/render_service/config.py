"""Portable paths and shared configuration for MARLIN."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[6]
DEFAULT_DOLPHIN_ASSET = str(
    PROJECT_ROOT
    / "assets"
    / "cetaceans"
    / "bottlenose_dolphin"
    / "usd"
    / "bottlenose_dolphin.usd"
)

DEFAULT_DOLPHIN_SWIM_ANIMATION = str(
    PROJECT_ROOT
    / "assets"
    / "cetaceans"
    / "bottlenose_dolphin"
    / "animation"
    / "swim_cycle.json"
)
