"""Headless tests for Game's centralized scene update dispatch (no ShowBase window)."""
import pytest

from src.game import Game
from src.scenes import Scene


class SpyScene(Scene):
    def __init__(self):
        super().__init__()
        self.updates: list[float] = []

    def on_update(self, dt: float) -> None:
        super().on_update(dt)
        self.updates.append(dt)


class FakeTask:
    cont = 1


def make_game() -> Game:
    """Build a Game without initializing ShowBase."""
    game = Game.__new__(Game)
    game.scenes = {}
    game.main_scene = None
    game.paused = False
    return game


def tick(game: Game) -> int:
    return game._update_main_scene(FakeTask())


def test_update_dispatches_to_started_main_scene():
    game, scene = make_game(), SpyScene()
    game.add_scene(scene, set_as_main=True)
    assert tick(game) == FakeTask.cont
    assert len(scene.updates) == 1


def test_update_skipped_when_paused_and_resumes():
    game, scene = make_game(), SpyScene()
    game.add_scene(scene, set_as_main=True)
    game.set_paused(True)
    tick(game)
    assert scene.updates == []
    game.set_paused(False)
    tick(game)
    assert len(scene.updates) == 1


def test_update_ignores_missing_or_stopped_scene():
    game, scene = make_game(), SpyScene()
    assert tick(game) == FakeTask.cont
    game.add_scene(scene)
    game.main_scene = scene  # not started
    tick(game)
    assert scene.updates == []


def test_switching_scene_stops_previous_and_updates_only_new():
    game, a, b = make_game(), SpyScene(), SpyScene()
    game.add_scene(a, set_as_main=True)
    game.add_scene(b, set_as_main=True)
    assert not a.is_started and b.is_started
    tick(game)
    assert a.updates == [] and len(b.updates) == 1


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__]))
