from typing import Literal, TypeAlias


from src.scenes import Scene
from .terminal.events import TestEvents
from .terminal.entities import TestEntities
from .panda import *


TargetType: TypeAlias = Literal[
    'events',
    'entities',
    'physics',
    'models',
    'areas',
] | None


TARGET: TargetType = 'areas' # Change this to run different test suites.
#TARGET: TargetType = None


class Tests:
    def __init__(self):
        self.__target: Scene | None = None

        if TARGET == 'events':
            self.__target = TestEvents()   
        elif TARGET == 'entities':
            self.__target = TestEntities()
        elif TARGET == 'physics':
            self.__target = TestPhysics()
        elif TARGET == 'models':
            self.__target = TestModels()
        elif TARGET == 'areas':
            self.__target = TestAreas()
        
        
    def get_target(self) -> Scene | None:
        return self.__target
    

__all__ = [
    'Tests',
]
