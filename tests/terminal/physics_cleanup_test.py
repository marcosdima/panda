"""Headless tests for Physics cleanup and diagnostics."""

import builtins

if getattr(builtins, "base", None) is None:
    from direct.showbase.ShowBase import ShowBase

    ShowBase(windowType="none")

import pytest
from panda3d.bullet import BulletRigidBodyNode

from src.globals.physics import Physics


def _reset() -> None:
    Physics.clear_all()


def test_clear_all_empty() -> None:
    _reset()
    result = Physics.clear_all()
    assert result == {"bodies": 0, "ghosts": 0, "constraints": 0}
    dump = Physics.debug_dump()
    assert dump["bodies"] == 0
    assert dump["ghosts"] == 0
    assert dump["constraints"] == 0
    assert dump["orphan_nodes"] == 0
    _reset()


def test_clear_all_removes_bodies() -> None:
    _reset()
    for i in range(5):
        Physics.create_body(f"body_{i}", mass=1.0)
    assert Physics.debug_dump()["bodies"] == 5
    result = Physics.clear_all()
    assert result["bodies"] == 5
    assert Physics.debug_dump()["bodies"] == 0
    assert len(Physics.get_world().getRigidBodies()) == 0
    _reset()


def test_clear_all_removes_ghosts() -> None:
    _reset()
    for i in range(4):
        Physics.create_ghost(f"ghost_{i}")
    assert Physics.debug_dump()["ghosts"] == 4
    result = Physics.clear_all()
    assert result["ghosts"] == 4
    assert Physics.debug_dump()["ghosts"] == 0
    assert len(Physics.get_world().getGhosts()) == 0
    _reset()


def test_clear_all_idempotent() -> None:
    _reset()
    Physics.create_body("body", mass=1.0)
    Physics.create_ghost("ghost")
    first = Physics.clear_all()
    assert first["bodies"] == 1
    assert first["ghosts"] == 1
    second = Physics.clear_all()
    assert second == {"bodies": 0, "ghosts": 0, "constraints": 0}
    _reset()


def test_debug_dump_counts() -> None:
    _reset()
    Physics.create_body("body_a", mass=1.0)
    Physics.create_body("body_b", mass=2.0)
    Physics.create_ghost("ghost_a")
    dump = Physics.debug_dump()
    assert dump["bodies"] == 2
    assert dump["ghosts"] == 1
    assert dump["constraints"] == 0
    assert dump["orphan_nodes"] == 0
    _reset()


def test_orphan_detection() -> None:
    _reset()
    world = Physics.get_world()
    orphan = BulletRigidBodyNode("orphan_body")
    world.attachRigidBody(orphan)
    dump = Physics.debug_dump()
    assert dump["bodies"] == 0
    assert dump["orphan_nodes"] >= 1
    result = Physics.clear_all()
    assert result["bodies"] >= 1
    assert Physics.debug_dump()["orphan_nodes"] == 0
    assert len(world.getRigidBodies()) == 0
    _reset()


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__]))
