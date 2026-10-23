"""Components package for reusable optional entity behaviour.

``HealthHandler`` (entity health, damage and death) and ``SpawnerHandler``
(runtime entity spawning) are the gameplay components in the package; both
stay fully functional headless. ``PauseHandler`` (``src/handlers/pause/``)
and the camera overlay components are UI-oriented; they degrade gracefully
headless.
"""

from .camera_control import CameraControlComponent
from .camera_settings import CameraSettingsComponent
from .health_handler import HealthHandler
from .spawner_handler import SpawnerHandler

__all__ = [
    "CameraControlComponent",
    "CameraSettingsComponent",
    "HealthHandler",
    "SpawnerHandler",
]
