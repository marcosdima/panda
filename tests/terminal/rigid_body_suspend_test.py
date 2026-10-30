"""Headless tests for rigid body suspension and collision-group resolution."""

from __future__ import annotations

import sys

import pytest
from panda3d.bullet import BulletBoxShape
from panda3d.core import NodePath, Vec3

from src.entities.entity import Entity
from src.globals.physics import Physics
from src.handlers.physics import (
    CharacterControllerHandler,
    CollisionGroup,
    RigidBodyHandler,
    resolve_collision_group,
)
from src.utils.position import world_position

DT = 1.0 / 60.0
_CREATED_ENTITIES: list[Entity] = []
_CREATED_NODES: list[NodePath] = []


@pytest.fixture(autouse=True)
def isolated_physics_world():
    """Give every test a pristine Bullet world and a guaranteed teardown."""
    world = Physics.get_world()
    bodies_before = [world.getRigidBody(i) for i in range(world.getNumRigidBodies())]

    _CREATED_ENTITIES.clear()
    _CREATED_NODES.clear()

    yield

    for entity in _CREATED_ENTITIES:
        if not entity.is_freed:
            entity.free()
    for node in _CREATED_NODES:
        if not node.isEmpty():
            node.removeNode()

    for index in range(world.getNumRigidBodies() - 1, -1, -1):
        body = world.getRigidBody(index)
        if not any(body is known for known in bodies_before):
            world.removeRigidBody(body)

    _CREATED_ENTITIES.clear()
    _CREATED_NODES.clear()


def _entity(name: str, z: float = 10.0) -> Entity:
    entity = Entity(name)
    entity.node.setPos(0.0, 0.0, z)
    _CREATED_ENTITIES.append(entity)
    return entity


def _carrier(name: str, position: Vec3 = Vec3(5.0, 0.0, 3.0)) -> NodePath:
    node = NodePath(name)
    node.setPos(position)
    _CREATED_NODES.append(node)
    return node


def _step(entity: Entity, frames: int = 1) -> None:
    world = Physics.get_world()
    for _ in range(frames):
        entity.update(DT)
        world.doPhysics(DT)


def test_suspend_detaches_body_and_freezes_simulation() -> None:
    """A suspended dynamic body leaves the world and stops falling."""
    world = Physics.get_world()
    entity = _entity("SuspendFreeze", z=10.0)
    rigid = entity.add_handler(RigidBodyHandler(shape=BulletBoxShape(Vec3(0.5, 0.5, 0.5)), mass=1.0))
    entity.start()

    _step(entity, 10)
    assert rigid.body_node in world.getRigidBodies()
    assert world_position(entity).z < 10.0

    rigid.suspend()
    rigid.suspend()  # idempotent
    assert rigid.is_suspended is True
    assert rigid.body_node not in world.getRigidBodies()

    frozen = world_position(entity)
    _step(entity, 60)
    assert (world_position(entity) - frozen).length() < 1e-4

    rigid.resume()
    rigid.resume()  # idempotent
    assert rigid.is_suspended is False
    assert rigid.body_node in world.getRigidBodies()

    entity.stop()


def test_suspend_clears_motion_and_forces_by_default() -> None:
    """A carried body does not resume with the velocity it had when picked up."""
    entity = _entity("SuspendMotion", z=20.0)
    rigid = entity.add_handler(RigidBodyHandler(shape=BulletBoxShape(Vec3(0.5, 0.5, 0.5)), mass=1.0))
    entity.start()

    rigid.linear_velocity = Vec3(3.0, 0.0, -4.0)
    rigid.apply_force(Vec3(10.0, 0.0, 0.0))
    rigid.suspend()

    assert rigid.linear_velocity.length() < 1e-6
    rigid.resume()
    assert rigid.linear_velocity.length() < 1e-6

    entity.stop()


def test_suspend_can_preserve_motion() -> None:
    """preserve_motion=True keeps the velocity across suspend/resume."""
    entity = _entity("SuspendPreserve", z=20.0)
    rigid = entity.add_handler(RigidBodyHandler(shape=BulletBoxShape(Vec3(0.5, 0.5, 0.5)), mass=1.0))
    entity.start()

    rigid.linear_velocity = Vec3(2.0, 0.0, 0.0)
    rigid.suspend(preserve_motion=True)
    assert abs(rigid.linear_velocity.x - 2.0) < 1e-6
    rigid.resume()
    assert abs(rigid.linear_velocity.x - 2.0) < 1e-6

    entity.stop()


def test_resume_adopts_transform_acquired_while_suspended() -> None:
    """A body carried to a new parent resumes from the new world transform."""
    world = Physics.get_world()
    entity = _entity("SuspendCarried", z=6.0)
    rigid = entity.add_handler(RigidBodyHandler(shape=BulletBoxShape(Vec3(0.5, 0.5, 0.5)), mass=1.0))
    entity.start()

    _step(entity, 5)
    rigid.suspend()

    carrier = _carrier("SuspendCarrier")
    entity.node.reparentTo(carrier)
    entity.node.setPos(0.0, 0.0, 0.0)  # snap into the carrier's socket
    rigid.rebase()
    assert rigid.body_node not in world.getRigidBodies()

    rigid.resume()
    assert rigid.body_node in world.getRigidBodies()
    start_z = world_position(entity).z
    _step(entity, 30)

    position = world_position(entity)
    assert abs(position.x - 5.0) < 1e-3, f"Expected carried x=5, got {position}"
    assert position.z < start_z - 0.5, f"Expected body to fall, got {position}"

    entity.stop()


def test_resume_without_suspend_is_noop() -> None:
    """Calling resume on an attached body leaves it attached."""
    world = Physics.get_world()
    entity = _entity("ResumeNoop", z=5.0)
    rigid = entity.add_handler(RigidBodyHandler(shape=BulletBoxShape(Vec3(0.5, 0.5, 0.5)), mass=1.0))
    entity.start()

    rigid.resume()
    assert rigid.is_suspended is False
    assert rigid.body_node in world.getRigidBodies()

    entity.stop()


def test_suspension_survives_stop_and_start() -> None:
    """A stopped suspended body does not silently re-enter the simulation."""
    world = Physics.get_world()
    entity = _entity("SuspendRestart", z=8.0)
    rigid = entity.add_handler(RigidBodyHandler(shape=BulletBoxShape(Vec3(0.5, 0.5, 0.5)), mass=1.0))
    entity.start()
    rigid.suspend()

    entity.stop()
    entity.start()

    assert rigid.is_suspended is True
    assert rigid.body_node not in world.getRigidBodies()

    rigid.resume()
    assert rigid.body_node in world.getRigidBodies()

    entity.stop()


def test_rebase_places_drifted_body_at_parent_origin() -> None:
    """A body that drifted from its entity node is re-centred by rebase()."""
    entity = _entity("RebaseDrift", z=20.0)
    rigid = entity.add_handler(RigidBodyHandler(shape=BulletBoxShape(Vec3(0.5, 0.5, 0.5)), mass=1.0))
    entity.start()
    assert rigid.body_np is not None

    rigid.body_np.setPos(10.0, 0.0, 0.0)  # simulate a body that drifted
    rigid.suspend()
    rigid.rebase()

    assert (rigid.body_np.getPos() - Vec3(0.0, 0.0, 0.0)).length() < 1e-6

    entity.stop()


def test_resolve_collision_group_prefers_physics_handlers() -> None:
    """The shared resolver matches rigid body, character and bare entities."""
    bare = _entity("GroupBare")
    assert resolve_collision_group(bare) == CollisionGroup.DEFAULT

    prop = _entity("GroupProp")
    prop.add_handler(
        RigidBodyHandler(
            shape=BulletBoxShape(Vec3(0.5, 0.5, 0.5)),
            mass=1.0,
            collision_group=CollisionGroup.PROP,
        )
    )
    assert resolve_collision_group(prop) == CollisionGroup.PROP

    npc = _entity("GroupNpc")
    npc.add_handler(CharacterControllerHandler(collision_group=CollisionGroup.ENEMY))
    assert resolve_collision_group(npc) == CollisionGroup.ENEMY

    both = _entity("GroupBoth")
    both.add_handler(
        RigidBodyHandler(
            shape=BulletBoxShape(Vec3(0.5, 0.5, 0.5)),
            mass=1.0,
            collision_group=CollisionGroup.INTERACTABLE,
        )
    )
    both.add_handler(CharacterControllerHandler(collision_group=CollisionGroup.ENEMY))
    assert resolve_collision_group(both) == CollisionGroup.INTERACTABLE


if __name__ == "__main__":
    sys.exit(pytest.main([__file__]))
