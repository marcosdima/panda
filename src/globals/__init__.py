from .clock import GlobalClock
from .tasks import Tasks
from .loader import GlobalLoader
from .physics import Physics


class Globals:
    def __init__(self) -> None:
        self.clock = GlobalClock()
        self.tasks = Tasks()
        self.global_loader = GlobalLoader()
        self.physics = Physics()


__all__ = [
    "Globals",

    "GlobalClock",
    "Tasks",
    "GlobalLoader",
    "Physics",
]