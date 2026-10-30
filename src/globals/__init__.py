from .camera import Camera
from .clock import GlobalClock
from .lights import GlobalLights
from .loader import GlobalLoader
from .physics import Physics
from .tasks import Tasks


class Globals:
    def __init__(self) -> None:
        self.clock = GlobalClock()
        self.tasks = Tasks()
        self.global_loader = GlobalLoader()
        self.physics = Physics()
        self.camera = Camera()
        self.lights = GlobalLights()

        # Setup default lighting
        GlobalLights.setup_default_lights()

        # Register core services in Service Locator
        from src.services.initializers import initialize_services

        initialize_services()


__all__ = [
    "Camera",
    "GlobalClock",
    "GlobalLights",
    "GlobalLoader",
    "Globals",
    "Physics",
    "Tasks",
]
