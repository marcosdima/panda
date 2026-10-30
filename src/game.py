from direct.showbase.ShowBase import ShowBase

from src.services.initializers import initialize_services

from .globals import GlobalClock, Globals
from .scenes import Scene


class Game(ShowBase):
    UPDATE_TASK_NAME = "game_scene_update"
    UPDATE_TASK_SORT = -5
    POST_UPDATE_TASK_NAME = "game_post_update"
    POST_UPDATE_TASK_SORT = 1

    def __init__(self) -> None:
        super().__init__()

        # Set globals.
        self.globals = Globals()

        # Initialize core services in Service Locator.
        initialize_services()

        # Set scenes.
        self.scenes: dict[int, Scene] = {}
        self.main_scene: Scene | None = None

        # Centralized per-frame scene update (runs before scene-specific tasks).
        self.paused: bool = False
        self._update_task = self.taskMgr.add(
            self._update_main_scene, self.UPDATE_TASK_NAME, sort=self.UPDATE_TASK_SORT
        )
        self._post_update_task = self.taskMgr.add(
            self._post_update_main_scene,
            self.POST_UPDATE_TASK_NAME,
            sort=self.POST_UPDATE_TASK_SORT,
        )

    def add_scene(self, scene: Scene, set_as_main: bool = False) -> None:
        """Add a scene to the game."""
        self.scenes[scene.id] = scene
        if set_as_main:
            self.set_main_scene(scene.id)

    def set_main_scene(self, scene_id: int) -> None:
        """Set the main scene by its ID."""
        if scene_id in self.scenes:
            # Stop the current main scene if exists.
            if self.main_scene is not None:
                self.main_scene.on_stop()

            # Start the new main scene.
            self.main_scene = self.scenes[scene_id]
            self.main_scene.on_start()

    def set_paused(self, paused: bool) -> None:
        """Pause or resume the per-frame update and physics simulation of the main scene."""
        self.paused = bool(paused)
        from src.utils import bus

        from .globals.physics import Physics

        Physics.set_paused(self.paused)
        bus.publish("game_paused", self.paused)

    def toggle_paused(self) -> bool:
        """Toggle the paused state of the game and return the new state."""
        self.set_paused(not self.paused)
        return self.paused

    def _update_main_scene(self, task) -> int:
        """Dispatch on_update(dt) to the active scene unless the game is paused."""
        scene = self.main_scene
        if not self.paused and scene is not None and scene.is_started:
            scene.on_update(GlobalClock.get_dt())
        return task.cont

    def _post_update_main_scene(self, task) -> int:
        """Dispatch on_post_update(dt) to the active scene unless the game is paused."""
        scene = self.main_scene
        if not self.paused and scene is not None and scene.is_started:
            scene.on_post_update(GlobalClock.get_dt())
        return task.cont
