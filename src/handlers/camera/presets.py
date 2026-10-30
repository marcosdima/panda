"""Standard Camera Presets and Configurations.

Defines standard camera presets for 3D games:
- ADVENTURE (Orbit): Third-person free look, centered behind character. Best for action/RPG/platformers.
- SHOOTER (Over-The-Shoulder): Offset to the right shoulder with closer distance. Best for TPS/shooters.
- ISOMETRIC (Strategy/ARPG): Angled overhead perspective (pitch -45 deg). Best for tactical/isometric games.
- OVERHEAD (Top-Down): High camera looking almost straight down (pitch -85 deg).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from panda3d.core import Vec3

from src.utils.handler_phase import HandlerPhase


class PresetName(str, Enum):
    phase = HandlerPhase.POST
    ADVENTURE = "adventure"
    SHOOTER = "shooter"
    ISOMETRIC = "isometric"
    OVERHEAD = "overhead"


@dataclass(frozen=True)
class CameraPreset:
    phase = HandlerPhase.POST
    """Immutable data configuration for a third-person camera perspective."""

    name: str
    distance: float
    pitch: float
    target_offset: Vec3
    shoulder_offset: Vec3 = Vec3(0.0, 0.0, 0.0)
    min_distance: float = 1.5
    max_distance: float = 25.0
    min_pitch: float = -89.0
    max_pitch: float = 89.0
    fov: float = 60.0
    yaw: float = 0.0


# Standard Action RPG / Adventure Orbit Camera
ADVENTURE_PRESET = CameraPreset(
    name="Adventure (Orbit)",
    distance=7.5,
    pitch=-15.0,
    target_offset=Vec3(0.0, 0.0, 1.2),
    shoulder_offset=Vec3(0.0, 0.0, 0.0),
    min_distance=2.0,
    max_distance=20.0,
)

# Over-The-Shoulder Shooter (TPS) Camera
SHOOTER_PRESET = CameraPreset(
    name="Over-The-Shoulder (Shooter)",
    distance=3.2,
    pitch=-10.0,
    target_offset=Vec3(0.0, 0.0, 1.2),
    shoulder_offset=Vec3(0.5, 0.0, 0.2),
    min_distance=1.2,
    max_distance=10.0,
)

# Isometric / ARPG / Tactical Camera (45 deg pitch)
ISOMETRIC_PRESET = CameraPreset(
    name="Isometric (Strategy)",
    distance=14.0,
    pitch=-45.0,
    target_offset=Vec3(0.0, 0.0, 1.0),
    shoulder_offset=Vec3(0.0, 0.0, 0.0),
    min_distance=5.0,
    max_distance=30.0,
)

# Top-Down / Overhead Tactical Camera
OVERHEAD_PRESET = CameraPreset(
    name="Top-Down (Overhead)",
    distance=16.0,
    pitch=-85.0,
    target_offset=Vec3(0.0, 0.0, 1.0),
    shoulder_offset=Vec3(0.0, 0.0, 0.0),
    min_distance=6.0,
    max_distance=35.0,
)

PRESETS_BY_NAME: dict[str, CameraPreset] = {
    PresetName.ADVENTURE: ADVENTURE_PRESET,
    PresetName.SHOOTER: SHOOTER_PRESET,
    PresetName.ISOMETRIC: ISOMETRIC_PRESET,
    PresetName.OVERHEAD: OVERHEAD_PRESET,
    "adventure": ADVENTURE_PRESET,
    "shooter": SHOOTER_PRESET,
    "shoulder": SHOOTER_PRESET,
    "tps": SHOOTER_PRESET,
    "isometric": ISOMETRIC_PRESET,
    "iso": ISOMETRIC_PRESET,
    "overhead": OVERHEAD_PRESET,
    "top_down": OVERHEAD_PRESET,
}
