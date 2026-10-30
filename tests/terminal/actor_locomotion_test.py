"""Headless test: ActorAnimationHandler locomotion FSM drives clip selection."""

from types import SimpleNamespace

import pytest
from panda3d.core import Vec3

from src.handlers.graphics.actor import ActorAnimationHandler
from src.handlers.physics.character import CharacterControllerHandler

CLIPS = ["Idle_A", "Walking_A", "Running_A", "Jump_Idle"]


class FakeControls:
    def __init__(self, names):
        self.names = list(names)
        self.looped: list[str] = []

    def getNumAnims(self):
        return len(self.names)

    def getAnimName(self, i):
        return self.names[i]

    def findAnim(self, name):
        if name not in self.names:
            return None
        return SimpleNamespace(loop=lambda restart: self.looped.append(name))


def make(clips=CLIPS):
    h = ActorAnimationHandler.kaykit_rig_medium("Knight")
    h.anim_controls = FakeControls(clips)
    ctrl = SimpleNamespace(
        visual_node=None,
        linear_velocity=Vec3(0, 0, 0),
        is_sprinting=False,
        controller_node=object(),
        is_on_ground=True,
    )
    h.entity = SimpleNamespace(
        get_handler=lambda cls: ctrl if cls is CharacterControllerHandler else None
    )
    return h, ctrl


def step(h, dt=0.05):
    h.on_update(dt)
    return h.locomotion.state, h.current_animation


def test_idle_walk_run_jump_sequence():
    h, c = make()
    assert step(h) == ("Idle", "Idle_A")
    c.linear_velocity = Vec3(0, 2, 0)
    assert step(h) == ("Walk", "Walking_A")
    c.is_sprinting = True
    assert step(h) == ("Run", "Running_A")
    c.is_on_ground = False
    assert step(h, 0.05)[0] == "Run"  # below air_threshold
    assert step(h, 0.2) == ("Jump", "Jump_Idle")
    c.is_on_ground = True
    c.linear_velocity = Vec3(0, 0, 0)
    assert step(h) == ("Idle", "Idle_A")


def test_clip_fallbacks_and_missing_jump():
    h, c = make(["Idle_A", "Running_A"])
    c.linear_velocity = Vec3(0, 2, 0)
    assert step(h) == ("Walk", "Running_A")  # Walk falls back to Run
    c.is_on_ground = False
    assert step(h, 0.5) == ("Walk", "Running_A")  # no Jump clip: ground logic


def test_manual_override_is_reconciled_and_no_clips_is_safe():
    h, _c = make()
    step(h)
    h.loop_animation("Walking_A")
    assert step(h) == ("Idle", "Idle_A")
    h2, _ = make([])
    assert step(h2) == ("Idle", None)


def test_run_falls_back_to_walk_and_moving_to_idle():
    h, c = make(["Idle_A", "Walking_A"])
    c.linear_velocity = Vec3(0, 2, 0)
    c.is_sprinting = True
    assert step(h) == ("Run", "Walking_A")
    h2, c2 = make(["Idle_A"])
    c2.linear_velocity = Vec3(0, 2, 0)
    assert step(h2) == ("Walk", "Idle_A")


def test_cleanup_resets_state():
    h, c = make()
    c.linear_velocity = Vec3(0, 2, 0)
    c.is_sprinting = True
    assert step(h)[0] == "Run"
    h._cleanup_nodes()
    assert h.locomotion.state == "Idle"


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__]))
