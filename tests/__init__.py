from typing import Literal, TypeAlias


from src.scenes import Scene
from .terminal.events import TestEvents
from .terminal.entities import TestEntities
from .terminal.character_controller import TestCharacterController
from .terminal.camera_handler import TestCameraHandler
from .terminal.actor_animation import TestActorAnimation
from .terminal.physics_handlers import TestPhysicsHandlers
from .terminal.model_handler import TestModelHandler
from .terminal.scene_tasks_test import TestSceneTasks
from .panda import *


TargetType: TypeAlias = Literal[
    'events',
    'entities',
    'controllers',
    'camera',
    'animation',
    'physics',
    'models',
    'character',
    'physics_handlers',
    'triggers',
    'model_handler',
    'camera_fp',
    'scene_tasks',
    'ai',
    'follow',
    'proximity',
] | None


TARGET: TargetType = 'camera_fp' # Change this to run different test suites.
#TARGET: TargetType = None


class Tests:
    def __init__(self) -> None:
        self.__target: Scene | None = None

        if TARGET == 'events':
            self.__target = TestEvents()
        elif TARGET == 'entities':
            self.__target = TestEntities()
        elif TARGET == 'controllers':
            self.__target = TestCharacterController()
        elif TARGET == 'camera':
            self.__target = TestCameraHandler()
        elif TARGET == 'animation':
            self.__target = TestActorAnimation()
        elif TARGET == 'physics':
            self.__target = TestPhysics()
        elif TARGET == 'models':
            self.__target = TestModels()
        elif TARGET == 'character':
            self.__target = TestCharacterSandbox()
        elif TARGET == 'physics_handlers':
            self.__target = TestPhysicsHandlers()
        elif TARGET == 'triggers':
            self.__target = TestTriggersSandbox()
        elif TARGET == 'model_handler':
            self.__target = TestModelHandler()
        elif TARGET == 'camera_fp':
            self.__target = TestFirstPersonCameraSandbox()
        elif TARGET == 'scene_tasks':
            self.__target = TestSceneTasks()
        elif TARGET == 'ai':
            self.__target = TestAISandbox()
        elif TARGET == 'follow':
            self.__target = TestFollowSandbox()
        elif TARGET == 'proximity':
            self.__target = TestProximitySandbox()


    def get_target(self) -> Scene | None:
        return self.__target


__all__ = [
    'Tests',
]
