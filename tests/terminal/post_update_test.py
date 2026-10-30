"""Headless tests for post-update pipeline (no ShowBase window)."""

from __future__ import annotations

import sys

import pytest

from src.entities.entity import Entity
from src.game import Game
from src.handlers.base import Handler
from src.scenes import Scene


class PostUpdateSpyHandler(Handler):
    def __init__(self, tag: str = "spy") -> None:
        super().__init__()
        self.tag = tag
        self.updates: list[tuple[str, float]] = []

    def on_update(self, dt: float) -> None:
        super().on_update(dt)
        self.updates.append(("update", dt))

    def on_post_update(self, dt: float) -> None:
        super().on_post_update(dt)
        self.updates.append(("post_update", dt))


class PostUpdateScene(Scene):
    def __init__(self) -> None:
        super().__init__()
        self.updates: list[float] = []
        self.post_updates: list[float] = []

    def on_update(self, dt: float) -> None:
        super().on_update(dt)
        self.updates.append(dt)

    def on_post_update(self, dt: float) -> None:
        if not self._started:
            return
        super().on_post_update(dt)
        self.post_updates.append(dt)


class FakeTask:
    cont = 1


def make_game() -> Game:
    game = Game.__new__(Game)
    game.scenes = {}
    game.main_scene = None
    game.paused = False
    return game


def tick(game: Game) -> int:
    return game._update_main_scene(FakeTask())


def tick_post(game: Game) -> int:
    return game._post_update_main_scene(FakeTask())


def test_handler_on_post_update_exists_and_entity_update_post_invokes_it():
    Entity.reset_ids()
    entity = Entity("PostUpdateEntity")
    spy = PostUpdateSpyHandler()
    entity.add_handler(spy)
    entity.on_start()

    entity.update_post(0.016)
    assert spy.updates == [("post_update", 0.016)]

    entity.update_post(0.033)
    assert spy.updates == [("post_update", 0.016), ("post_update", 0.033)]


def test_scene_on_post_update_propagates_to_entities():
    Entity.reset_ids()
    scene = PostUpdateScene()
    entity = Entity("SceneEntity")
    spy = PostUpdateSpyHandler()
    entity.add_handler(spy)
    scene.add_entity(entity)
    scene.on_start()

    scene.on_post_update(0.016)
    assert spy.updates == [("post_update", 0.016)]
    assert scene.post_updates == [0.016]


def test_game_post_update_task_registered_with_sort_1_after_physics_sort_0():
    make_game()
    assert hasattr(Game, "POST_UPDATE_TASK_NAME")
    assert hasattr(Game, "POST_UPDATE_TASK_SORT")
    assert Game.POST_UPDATE_TASK_NAME == "game_post_update"
    assert Game.POST_UPDATE_TASK_SORT == 1
    assert Game.UPDATE_TASK_NAME == "game_scene_update"
    assert Game.UPDATE_TASK_SORT == -5


def test_game_post_update_respects_pause_and_dispatches_to_started_scene():
    game, scene = make_game(), PostUpdateScene()
    game.add_scene(scene, set_as_main=True)
    assert tick_post(game) == FakeTask.cont
    assert len(scene.post_updates) == 1

    game.set_paused(True)
    scene.post_updates.clear()
    tick_post(game)
    assert scene.post_updates == []
    game.set_paused(False)
    scene.post_updates.clear()
    tick_post(game)
    assert len(scene.post_updates) == 1


def test_camera_handler_does_not_write_transform_in_on_update_but_writes_in_on_post_update():
    from panda3d.core import NodePath, Vec3

    from src.handlers.camera.first_person import FirstPersonCameraHandler

    entity = Entity("CamEntity")
    entity.node.setPos(0.0, 0.0, 0.0)
    cam_node = NodePath("fp_test_cam")
    cam_node.setPos(999.0, 999.0, 999.0)
    handler = FirstPersonCameraHandler(eye_offset=Vec3(0.0, 0.0, 1.7), camera=cam_node)
    entity.add_handler(handler)
    entity.on_start()
    handler.set_pointer_captured(False)

    # Clear position set by start/attach
    cam_node.setPos(123.0, 456.0, 789.0)
    handler.on_update(0.016)
    # Look is processed in the update phase, but the transform must not be
    # written there: the camera stays where it was until the post-update phase.
    pos_after_update = Vec3(cam_node.getPos())
    assert (pos_after_update - Vec3(123.0, 456.0, 789.0)).length() < 1e-6

    # Post update should apply transform
    handler.on_post_update(0.016)
    expected_eye = Vec3(0.0, 0.0, 1.7)
    assert (cam_node.getPos() - expected_eye).length() < 1e-4

    entity.on_stop()
    entity.free()


def test_entity_update_alias_does_not_call_post_update_twice():
    Entity.reset_ids()
    entity = Entity("AliasEntity")
    spy = PostUpdateSpyHandler()
    entity.add_handler(spy)
    entity.on_start()

    entity.update(0.016)
    assert spy.updates == [("update", 0.016)]
    entity.update_post(0.016)
    assert spy.updates == [("update", 0.016), ("post_update", 0.016)]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__]))
