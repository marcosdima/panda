from typing import Literal

from src.scenes import Scene
from .events import TestEvents


TARGET: Literal["events"] = "events"


class Tests:
    def __init__(self):
        self.__target: Scene | None = None

        if TARGET == "events":
            self.__target = TestEvents()   

        
    def get_target(self) -> Scene | None:
        return self.__target
    

__all__ = [
    "Tests",
]
