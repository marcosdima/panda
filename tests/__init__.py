from typing import Literal, TypeAlias


from src.scenes import Scene
from .events import TestEvents
from .entities import TestEntities


TargetType: TypeAlias = Literal[
    'events',
    'entities',
] | None


#TARGET: TargetType = 'entities' # Change this to run different test suites.
TARGET: TargetType = None


class Tests:
    def __init__(self):
        self.__target: Scene | None = None

        if TARGET == 'events':
            self.__target = TestEvents()   
        elif TARGET == 'entities':
            self.__target = TestEntities()

        
    def get_target(self) -> Scene | None:
        return self.__target
    

__all__ = [
    'Tests',
]
