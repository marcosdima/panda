"""Helper to register core services at engine start‑up.

Typical usage in ``src/game.py``::

    from src.services.initializers import initialize_services
    initialize_services()
"""

from src.services import services
# Import the concrete global singletons (they will be thin wrappers after modification)
from src.globals.physics import Physics
from src.globals.loader import GlobalLoader
from src.globals.camera import Camera
from src.globals.lights import GlobalLights
from src.globals.tasks import Tasks
from src.globals.clock import GlobalClock

def initialize_services() -> None:
    """Register core engine services.

    This function should be called once after the ``ShowBase`` instance is
    created and all global objects are instantiated.
    """
    services.register("physics", Physics)
    services.register("loader", GlobalLoader)
    services.register("camera", Camera)
    services.register("lights", GlobalLights)
    services.register("tasks", Tasks)
    services.register("clock", GlobalClock)
