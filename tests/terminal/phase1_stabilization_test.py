"""Headless unit tests for Phase 1 core stabilization and the live sandbox inspector."""

from __future__ import annotations

import builtins
import math
import sys

import pytest
from direct.task.Task import TaskManager
from panda3d.bullet import BulletBoxShape
from panda3d.core import NodePath, Vec3

from src.entities.entity import Entity
from src.game import Game
from src.globals.physics import Physics
from src.handlers.ai import AIPatrolHandler
from src.handlers.graphics.actor import ActorAnimationHandler
from src.handlers.graphics.model import ModelHandler
from src.handlers.input.base import InputHandler
from src.handlers.physics import (
    CharacterControllerHandler,
    CharacterOrientationMode,
    CollisionGroup,
    RigidBodyHandler,
)
from src.utils import bus
from src.utils.position import world_position
from tests.__test import Test


class _FakeControl:
    def __init__(self, name: str, num_frames: int = 30, frame_rate: float = 30.0) -> None:
        self.name = name
        self._num_frames = num_frames
        self._frame_rate = frame_rate
        self.playing = False

    def getNumFrames(self) -> int:
        return self._num_frames

    def getFrameRate(self) -> float:
        return self._frame_rate

    def play(self) -> None:
        self.playing = True

    def loop(self, _restart: bool = True) -> None:
        self.playing = True

    def stop(self) -> None:
        self.playing = False

    def isPlaying(self) -> bool:
        return self.playing


class _FakeAnimCollection:
    def __init__(self, names: tuple[str, ...]) -> None:
        self._controls = {n: _FakeControl(n) for n in names}
        self._order = list(names)

    def getNumAnims(self) -> int:
        return len(self._order)

    def getAnimName(self, i: int) -> str:
        return self._order[i]

    def getAnim(self, i: int) -> _FakeControl:
        return self._controls[self._order[i]]

    def findAnim(self, name: str) -> _FakeControl | None:
        return self._controls.get(name)

    def stopAll(self) -> None:
        for c in self._controls.values():
            c.stop()


def test_world_position_and_model_sync_for_dynamic_rigid_body() -> None:
    """Dynamic RigidBodyHandler updates world_position(entity) and moves sibling ModelHandler."""
    world = Physics.get_world()

    entity = Entity("DynamicCrate")
    entity.node.setPos(2.0, 3.0, 5.0)

    # Attach ModelHandler BEFORE RigidBodyHandler (same order as create_static_prop)
    model_handler = ModelHandler(model_path="box", from_assets=False)
    entity.add_handler(model_handler)
    assert model_handler.model_np is not None
    assert model_handler.model_np.getParent() == entity.node

    rigid = RigidBodyHandler(shape=BulletBoxShape(Vec3(0.5, 0.5, 0.5)), mass=2.0)
    entity.add_handler(rigid)
    entity.start()

    # Sibling ModelHandler must now be parented to rigid.body_np so it moves with Bullet
    assert rigid.body_np is not None
    assert model_handler.model_np.getParent() == rigid.body_np

    initial_pos = world_position(entity)
    assert (initial_pos - Vec3(2.0, 3.0, 5.0)).length() < 1e-4

    for _ in range(30):
        entity.update(1.0 / 60.0)
        world.doPhysics(1.0 / 60.0)

    fallen_pos = world_position(entity)
    assert fallen_pos.z < 4.0, f"Expected dynamic body to fall below z=4.0, got {fallen_pos}"
    model_net_pos = model_handler.model_np.getNetTransform().getPos()
    assert (model_net_pos - fallen_pos).length() < 1e-4

    # Detaching RigidBodyHandler must restore model_np back under entity.node without destroying it
    entity.remove_handler(rigid)
    assert model_handler.model_np is not None and not model_handler.model_np.isEmpty()
    assert model_handler.model_np.getParent() == entity.node

    entity.stop()
    entity.free()


def test_npc_visual_rotation_without_camera_handler() -> None:
    """Camera-less NPCs rotate their visual_node to face their movement direction."""
    npc = Entity("PatrolNpc")
    visual_np = npc.node.attachNewNode("npc_visual")
    inp = InputHandler()
    controller = CharacterControllerHandler(
        walk_speed=4.0,
        visual_node=visual_np,
        turn_speed=0.0,  # instant snap
        orientation_mode=CharacterOrientationMode.MOVE_DIRECTION,
    )
    npc.add_handler(inp)
    npc.add_handler(controller)
    npc.start()

    # Move along +X -> heading should snap to -90 deg (270 deg)
    inp.set_move_vector(1.0, 0.0)
    npc.update(1.0 / 60.0)
    assert abs((visual_np.getH() % 360.0) - 270.0) < 1e-4

    # Move along -Y -> heading should snap to 180 deg
    inp.set_move_vector(0.0, -1.0)
    npc.update(1.0 / 60.0)
    assert abs((visual_np.getH() % 360.0) - 180.0) < 1e-4

    # Move along -X -> heading should snap to +90 deg
    inp.set_move_vector(-1.0, 0.0)
    npc.update(1.0 / 60.0)
    assert abs((visual_np.getH() % 360.0) - 90.0) < 1e-4

    # Live property setters for gravity and jump_speed push to BulletCharacterControllerNode
    controller.gravity = 22.5
    controller.jump_speed = 9.5
    assert math.isclose(controller.gravity, 22.5)
    assert math.isclose(controller.jump_speed, 9.5)

    npc.stop()
    npc.free()


def test_physics_pause_and_game_pause_event_and_collision_groups() -> None:
    """Game.set_paused syncs Physics.is_paused() and publishes 'game_paused' on bus."""
    assert CollisionGroup.INTERACTABLE.bitmask.getWord() == (1 << 4)
    assert CollisionGroup.PROP.bitmask.getWord() == (1 << 5)

    events: list[bool] = []
    bus.subscribe("game_paused", events.append)
    try:
        game = Game.__new__(Game)
        game.scenes = {}
        game.main_scene = None
        game.paused = False

        game.set_paused(True)
        assert game.paused is True
        assert Physics.is_paused() is True
        assert events == [True]

        # Physics._update_world must not advance dynamic bodies while paused
        entity = Entity("PausedDropper")
        entity.node.setPos(0.0, 0.0, 10.0)
        rigid = RigidBodyHandler(shape=BulletBoxShape(Vec3(0.5, 0.5, 0.5)), mass=1.0)
        entity.add_handler(rigid)
        entity.start()

        phys = Physics.get_instance()

        class _FakeTask:
            cont = 1

        phys._update_world(_FakeTask())  # type: ignore[arg-type]
        assert abs(world_position(entity).z - 10.0) < 1e-4

        # Toggle resume -> physics steps again
        assert game.toggle_paused() is False
        assert Physics.is_paused() is False
        assert events == [True, False]

        entity.stop()
        entity.free()
    finally:
        Physics.set_paused(False)
        bus.unsubscribe("game_paused", events.append)


def test_actor_one_shot_action_override() -> None:
    """play_action locks out locomotion clip reconciliation until the action finishes."""
    entity = Entity("ActionActor")
    inp = InputHandler()
    controller = CharacterControllerHandler(walk_speed=5.0)
    actor = ActorAnimationHandler(
        animations={},
        state_clips={"Idle": "Idle_A", "Walk": "Walking_A", "Run": "Running_A", "Jump": "Jump_Idle"},
        blend_duration=0.0,
    )
    entity.add_handler(inp)
    entity.add_handler(controller)
    entity.add_handler(actor)
    actor.anim_controls = _FakeAnimCollection(("Idle_A", "Walking_A", "Running_A", "Interact"))  # type: ignore[assignment]
    entity.start()

    assert actor.current_animation == "Idle_A"
    completed: list[str] = []

    assert actor.play_action("Interact", duration=0.20, on_complete=lambda: completed.append("done"))
    assert actor.is_playing_action is True
    assert actor.current_animation == "Interact"

    # Walking while action is playing updates locomotion state but keeps 'Interact' playing
    inp.set_move_vector(0.0, 1.0)
    entity.update(0.08)
    assert actor.locomotion.state == "Walk"
    assert actor.current_animation == "Interact"
    assert actor.is_playing_action is True
    assert completed == []

    # Advance past remaining action duration -> fires callback and transitions to Walking_A
    entity.update(0.15)
    assert actor.is_playing_action is False
    assert completed == ["done"]
    assert actor.current_animation == "Walking_A"

    entity.stop()
    entity.free()


def test_scene_root_np_registered_bodies_and_pauseable_tasks() -> None:
    """Scene cleans up registered bodies and skips pauseable tasks when base.paused is True."""
    scene = Test()
    scene.on_start()
    assert scene.root_np is not None and not scene.root_np.isEmpty()

    old_root = scene.root_np
    child = scene.root_np.attachNewNode("temp_child")
    body = Physics.create_body("scene_temp_body", mass=0.0)
    scene.register_body("scene_temp_body")
    assert body in Physics.get_world().getRigidBodies()

    manager = TaskManager()

    class _FakeBase:
        def __init__(self) -> None:
            self.taskMgr = manager
            self.paused = False

    fake_base = _FakeBase()
    ticks: list[int] = []
    original_base = getattr(builtins, "base", None)
    builtins.base = fake_base
    try:
        scene.add_task("count_task", lambda task: (ticks.append(1), task.cont)[1])
        manager.step()
        assert len(ticks) == 1

        fake_base.paused = True
        manager.step()
        assert len(ticks) == 1, "Pauseable scene task must not run while base.paused is True"

        fake_base.paused = False
        manager.step()
        assert len(ticks) == 2

        scene.on_stop()
        assert old_root.isEmpty()
        assert not child.hasParent()
        assert scene.root_np.getNumChildren() == 0
        assert body not in Physics.get_world().getRigidBodies()
    finally:
        if original_base is not None:
            builtins.base = original_base
        else:
            delattr(builtins, "base")


def test_sandbox_inspector_live_field_editing_and_auto_discovery() -> None:
    """Test sandbox inspector discovers handler fields and mutates numeric/bool/action fields."""
    sandbox = Test()
    hero = Entity("InspectorHero")
    controller = CharacterControllerHandler(walk_speed=6.0, sprint_speed=12.0, gravity=14.0)
    ai = AIPatrolHandler(sight_range=8.0, chase_sprint=True)
    hero.add_handler(controller)
    hero.add_handler(ai)
    sandbox.add_entity(hero)
    sandbox.on_start()

    sandbox.custom_speed = 4.0  # type: ignore[attr-defined]
    sandbox.custom_flag = False  # type: ignore[attr-defined]
    action_log: list[str] = []

    sandbox.expose_field("Custom Speed", sandbox, "custom_speed", 1.0, 10.0, 0.5)
    sandbox.expose_toggle(
        "Custom Flag",
        lambda: sandbox.custom_flag,  # type: ignore[attr-defined]
        lambda v: setattr(sandbox, "custom_flag", bool(v)),
    )
    sandbox.expose_action("Trigger Action", lambda: action_log.append("triggered"))

    fields = sandbox.get_inspector_fields()
    labels = [f.label for f in fields]
    assert "Custom Speed" in labels
    assert "Custom Flag" in labels
    assert "Trigger Action" in labels
    assert "Walk Speed" in labels
    assert "Gravity" in labels
    assert "AI Sight Range" in labels

    # Mutate custom numeric field and clamp
    sandbox.set_field_value("Custom Speed", 7.5)
    assert math.isclose(sandbox.custom_speed, 7.5)  # type: ignore[attr-defined]
    sandbox.step_field_value("Custom Speed", 1)
    assert math.isclose(sandbox.custom_speed, 8.0)  # type: ignore[attr-defined]
    sandbox.set_field_value("Custom Speed", 999.0)
    assert math.isclose(sandbox.custom_speed, 10.0)  # type: ignore[attr-defined]

    # Mutate auto-discovered handler field
    sandbox.set_field_value("Walk Speed", 9.5)
    assert math.isclose(controller.walk_speed, 9.5)
    sandbox.set_field_value("Gravity", 25.0)
    assert math.isclose(controller.gravity, 25.0)

    # Toggle boolean and run action
    sandbox.step_field_value("Custom Flag", 1)
    assert sandbox.custom_flag is True  # type: ignore[attr-defined]
    sandbox.set_field_value("Trigger Action", None)
    assert action_log == ["triggered"]

    # Toggle sandbox pause state headlessly
    assert sandbox.toggle_sandbox_pause() is True
    assert sandbox.is_sandbox_paused is True
    assert Physics.is_paused() is True
    assert sandbox.toggle_sandbox_pause() is False
    assert sandbox.is_sandbox_paused is False
    assert Physics.is_paused() is False

    sandbox.on_stop()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__]))
