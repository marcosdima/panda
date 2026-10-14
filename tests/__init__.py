from typing import Literal, TypeAlias


from src.scenes import Scene
from .terminal.events import TestEvents
from .terminal.entities import TestEntities
from .terminal.character_controller import TestCharacterController
from .panda import *
from .panda.character_sandbox import TestCharacterSandbox


TargetType: TypeAlias = Literal[
    'events',
    'entities',
    'controllers',
    'physics',
    'models',
    'areas',
    'character',
] | None


TARGET: TargetType = 'character' # Change this to run different test suites.
#TARGET: TargetType = None


class Tests:
    def __init__(self):
        self.__target: Scene | None = None

        if TARGET == 'events':
            self.__target = TestEvents()   
        elif TARGET == 'entities':
            self.__target = TestEntities()
        elif TARGET == 'controllers':
            self.__target = TestCharacterController()
        elif TARGET == 'physics':
            self.__target = TestPhysics()
        elif TARGET == 'models':
            self.__target = TestModels()
        elif TARGET == 'areas':
            self.__target = TestAreas()
        elif TARGET == 'character':
            self.__target = TestCharacterSandbox()
        
        
    def get_target(self) -> Scene | None:
        return self.__target
    

__all__ = [
    'Tests',
]
