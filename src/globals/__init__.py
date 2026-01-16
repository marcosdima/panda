from .clock import GlobalClock
from .tasks import Tasks
from .loader import GlobalLoader


class Globals:
    def __init__(self) -> None:
        self.clock = GlobalClock()
        self.tasks = Tasks()
        self.global_loader = GlobalLoader()


__all__ = [
    "Globals",

    "GlobalClock",
    "Tasks",
    "GlobalLoader",
]