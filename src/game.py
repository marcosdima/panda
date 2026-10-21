from direct.showbase.ShowBase import ShowBase

from .globals import Globals
from .scenes import Scene
from src.services.initializers import initialize_services


class Game(ShowBase):
    def __init__(self) -> None:
        super().__init__()

        # Set globals.
        self.globals = Globals()

        # Initialize core services in Service Locator.
        initialize_services()

        # Set scenes.
        self.scenes: dict[int, Scene] = {}
        self.main_scene: Scene | None = None

    
    def add_scene(self, scene: Scene, set_as_main: bool = False) -> None:
        ''' Add a scene to the game. '''
        self.scenes[scene.id] = scene
        if set_as_main:
            self.set_main_scene(scene.id)


    def set_main_scene(self, scene_id: int) -> None:
        ''' Set the main scene by its ID. '''
        if scene_id in self.scenes:
            # Stop the current main scene if exists.
            if self.main_scene is not None:
                self.main_scene.on_stop()

            # Start the new main scene.
            self.main_scene = self.scenes[scene_id]
            self.main_scene.on_start()



