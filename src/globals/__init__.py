from .clock import GlobalClock
from .tasks import Tasks
from .loader import GlobalLoader
from .physics import Physics
from .camera import Camera


class Globals:
    def __init__(self):
        self.clock = GlobalClock()
        self.tasks = Tasks()
        self.global_loader = GlobalLoader()
        self.physics = Physics()
        self.camera = Camera()


__all__ = [
    "Globals",

    "GlobalClock",
    "Tasks",
    "GlobalLoader",
    "Camera",
    "Physics",
]