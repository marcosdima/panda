"""Headless tests for SpawnerHandler (no window)."""

import pytest
from panda3d.bullet import BulletBoxShape
from panda3d.core import Vec3

from src.entities.entity import Entity
from src.globals.physics import Physics
from src.handlers.components.spawner_handler import SpawnerHandler
from src.handlers.physics import CollisionGroup, RigidBodyHandler, TriggerZoneHandler
from src.scenes import Scene

DT = 1.0 / 60.0

# Entities and scenes created by the running test, torn down by the fixture.
_CREATED_ENTITIES: list[Entity] = []
_CREATED_SCENES: list[Scene] = []


@pytest.fixture(autouse=True)
def isolated_physics_world():
    """Give every test a pristine Bullet world and a guaranteed teardown.

    The Bullet world is a process-wide singleton, so a test that fails before
    its cleanup would leak rigid bodies and ghosts into the following tests
    and inflate their trigger events. This fixture removes whatever the test
    added, so a failure can never cascade.
    """
    world = Physics.get_world()
    bodies_before = [world.getRigidBody(i) for i in range(world.getNumRigidBodies())]
    ghosts_before = [world.getGhost(i) for i in range(world.getNumGhosts())]

    _CREATED_ENTITIES.clear()
    _CREATED_SCENES.clear()

    yield

    for scene in _CREATED_SCENES:
        scene.on_stop()
    for entity in _CREATED_ENTITIES:
        if not entity.is_freed:
            entity.free()

    for index in range(world.getNumRigidBodies() - 1, -1, -1):
        body = world.getRigidBody(index)
        if not any(body is known for known in bodies_before):
            world.removeRigidBody(body)
    for index in range(world.getNumGhosts() - 1, -1, -1):
        ghost = world.getGhost(index)
        if not any(ghost is known for known in ghosts_before):
            world.removeGhost(ghost)

    _CREATED_ENTITIES.clear()
    _CREATED_SCENES.clear()


def _new_scene() -> Scene:
    """Create a started scene tracked by the teardown fixture."""
    scene = Scene()
    _CREATED_SCENES.append(scene)
    scene.on_start()
    return scene


def _track(entity: Entity) -> Entity:
    """Register an entity for teardown."""
    _CREATED_ENTITIES.append(entity)
    return entity


def _make_zone_entity(name: str) -> Entity:
    entity = Entity(name)
    entity.add_handler(TriggerZoneHandler(shape=BulletBoxShape(Vec3(2.0, 2.0, 2.0))))
    return _track(entity)


def _make_static_target(name: str) -> Entity:
    entity = Entity(name)
    entity.add_handler(
        RigidBodyHandler(
            shape=BulletBoxShape(Vec3(0.5, 0.5, 0.5)),
            mass=0.0,
            collision_group=CollisionGroup.DEFAULT,
        )
    )
    return _track(entity)


class _Factory:
    """Callable factory that records how many entities it built."""

    def __init__(self) -> None:
        self.call_count: int = 0
        self.names: list[str] = []

    def __call__(self) -> Entity:
        self.call_count += 1
        entity = Entity(f"Spawned-{self.call_count}")
        self.names.append(entity.name)
        return _track(entity)


def _leave_zone(target: Entity) -> None:
    """Move the target body outside the trigger volume."""
    target.get_handler(RigidBodyHandler).body_np.setPos(0.0, 0.0, 20.0)


def _enter_zone(target: Entity) -> None:
    """Move the target body back inside the trigger volume."""
    target.get_handler(RigidBodyHandler).body_np.setPos(0.0, 0.0, 0.0)


def _cycle_enter(world, spawner_entity: Entity, target: Entity) -> None:
    """Leave the zone and come back, producing one fresh ``on_enter`` edge.

    ``TriggerZoneHandler.on_enter`` is edge-triggered: a body that stays
    inside the volume never fires it again, so extra spawns require a real
    exit followed by a new entry.
    """
    _leave_zone(target)
    world.doPhysics(DT)
    spawner_entity.update(DT)
    _enter_zone(target)
    world.doPhysics(DT)
    spawner_entity.update(DT)


def test_spawn_on_enter_adds_entity_to_scene():
    world = Physics.get_world()
    scene = _new_scene()

    factory = _Factory()
    spawner_entity = _make_zone_entity("Spawner")
    spawner_entity.add_handler(
        SpawnerHandler(entity_factory=factory, scene=scene, spawn_on_enter=True)
    )
    scene.add_entity(spawner_entity)

    target_entity = _make_static_target("Target")
    target_entity.node.setPos(0.0, 0.0, 0.0)
    scene.add_entity(target_entity)

    world.doPhysics(DT)
    spawner_entity.update(DT)

    assert factory.call_count == 1, (
        f"Expected exactly one spawn, got {factory.call_count}"
    )
    spawner_handler = spawner_entity.get_handler(SpawnerHandler)
    assert spawner_handler is not None
    assert len(spawner_handler.spawned_entities) == 1
    assert spawner_handler.spawn_count == 1
    assert scene.get_entity(spawner_handler.spawned_entities[0].id) is not None


def test_max_spawns_stops_further_spawns():
    world = Physics.get_world()
    scene = _new_scene()

    factory = _Factory()
    spawner_entity = _make_zone_entity("Spawner")
    spawner_entity.add_handler(
        SpawnerHandler(
            entity_factory=factory,
            scene=scene,
            spawn_on_enter=True,
            max_spawns=2,
        )
    )
    scene.add_entity(spawner_entity)

    target_entity = _make_static_target("Target")
    target_entity.node.setPos(0.0, 0.0, 0.0)
    scene.add_entity(target_entity)

    world.doPhysics(DT)
    spawner_entity.update(DT)
    assert factory.call_count == 1

    # Two further enter edges: the second one is allowed, the third is not.
    _cycle_enter(world, spawner_entity, target_entity)
    assert factory.call_count == 2

    _cycle_enter(world, spawner_entity, target_entity)
    assert factory.call_count == 2, "max_spawns must block every spawn past the cap"

    spawner_handler = spawner_entity.get_handler(SpawnerHandler)
    assert spawner_handler.spawn_count == 2
    assert len(spawner_handler.spawned_entities) == 2


def test_cooldown_ignores_enters_within_window():
    world = Physics.get_world()
    scene = _new_scene()

    factory = _Factory()
    spawner_entity = _make_zone_entity("Spawner")
    spawner_entity.add_handler(
        SpawnerHandler(
            entity_factory=factory,
            scene=scene,
            spawn_on_enter=True,
            cooldown=0.5,
        )
    )
    scene.add_entity(spawner_entity)

    target_entity = _make_static_target("Target")
    target_entity.node.setPos(0.0, 0.0, 0.0)
    scene.add_entity(target_entity)

    world.doPhysics(DT)
    spawner_entity.update(DT)
    assert factory.call_count == 1

    # Re-enter immediately: cooldown must block further spawns.
    _cycle_enter(world, spawner_entity, target_entity)
    assert factory.call_count == 1, "Cooldown must suppress re-enters"

    # Advance past the cooldown window (the spawner ticks it down on update).
    for _ in range(int(0.5 / DT) + 1):
        world.doPhysics(DT)
        spawner_entity.update(DT)

    # Re-enter after the window: a new spawn is allowed.
    _cycle_enter(world, spawner_entity, target_entity)
    assert factory.call_count == 2


def test_spawn_on_enter_false_only_spawns_manually():
    world = Physics.get_world()
    scene = _new_scene()

    factory = _Factory()
    spawner_entity = _make_zone_entity("Spawner")
    spawner_entity.add_handler(
        SpawnerHandler(
            entity_factory=factory,
            scene=scene,
            spawn_on_enter=False,
        )
    )
    scene.add_entity(spawner_entity)

    target_entity = _make_static_target("Target")
    target_entity.node.setPos(0.0, 0.0, 0.0)
    scene.add_entity(target_entity)

    world.doPhysics(DT)
    spawner_entity.update(DT)
    assert factory.call_count == 0, (
        "No spawn without manual call when spawn_on_enter=False"
    )

    spawner_handler = spawner_entity.get_handler(SpawnerHandler)
    spawned = spawner_handler.spawn()
    assert spawned is not None
    assert factory.call_count == 1
    assert scene.get_entity(spawned.id) is not None


def test_clear_spawned_frees_all_tracked_entities():
    world = Physics.get_world()
    scene = _new_scene()

    factory = _Factory()
    spawner_entity = _make_zone_entity("Spawner")
    spawner_entity.add_handler(
        SpawnerHandler(entity_factory=factory, scene=scene, spawn_on_enter=True)
    )
    scene.add_entity(spawner_entity)

    target_entity = _make_static_target("Target")
    target_entity.node.setPos(0.0, 0.0, 0.0)
    scene.add_entity(target_entity)

    world.doPhysics(DT)
    spawner_entity.update(DT)
    assert factory.call_count == 1

    spawner_handler = spawner_entity.get_handler(SpawnerHandler)
    spawned = spawner_handler.spawned_entities[0]
    assert scene.get_entity(spawned.id) is spawned
    assert not spawned.is_freed

    spawner_handler.clear_spawned()
    assert spawned.is_freed
    assert spawner_handler.spawned_entities == []
    assert spawned.id not in scene.entities


def test_on_stop_frees_tracked_spawns():
    world = Physics.get_world()
    scene = _new_scene()

    factory = _Factory()
    spawner_entity = _make_zone_entity("Spawner")
    spawner_entity.add_handler(
        SpawnerHandler(entity_factory=factory, scene=scene, spawn_on_enter=True)
    )
    scene.add_entity(spawner_entity)

    target_entity = _make_static_target("Target")
    target_entity.node.setPos(0.0, 0.0, 0.0)
    scene.add_entity(target_entity)

    world.doPhysics(DT)
    spawner_entity.update(DT)
    assert factory.call_count == 1

    spawner_handler = spawner_entity.get_handler(SpawnerHandler)
    spawned = spawner_handler.spawned_entities[0]
    assert not spawned.is_freed

    spawner_entity.stop()  # on_stop frees tracked spawns
    assert spawned.is_freed
    assert spawner_handler.spawned_entities == []


def test_on_detach_frees_tracked_spawns_without_start():
    """``on_detach`` frees tracked spawns even when the entity never started.

    ``Entity.free`` skips ``on_stop`` for an entity that was never started,
    so ``on_detach`` is the only cleanup hook that runs in that path and it
    must free the spawns the handler is still tracking.
    """
    scene = _new_scene()

    factory = _Factory()
    spawner_entity = _make_zone_entity("Spawner")
    spawner_handler = SpawnerHandler(
        entity_factory=factory,
        scene=scene,
        spawn_on_enter=False,
    )
    spawner_entity.add_handler(spawner_handler)

    # The spawner entity is deliberately kept out of the scene so it is never
    # started: this test targets the detach-only cleanup path.
    assert not spawner_entity.is_started

    spawned = spawner_handler.spawn()
    assert spawned is not None
    assert factory.call_count == 1
    assert scene.get_entity(spawned.id) is spawned
    assert not spawned.is_freed

    spawner_entity.free()  # on_detach runs, on_stop never does

    assert spawned.is_freed, "on_detach must free the tracked spawns"
    assert spawned.id not in scene.entities
    assert spawner_handler.spawned_entities == []


def test_max_spawns_budget_survives_stop_start():
    """The ``max_spawns`` budget is not restored by a stop -> start cycle.

    ``on_stop`` frees the tracked spawns but keeps the spawn counter, so a
    restarted spawner stays capped by the entities it already produced.
    """
    world = Physics.get_world()
    scene = _new_scene()

    factory = _Factory()
    spawner_entity = _make_zone_entity("Spawner")
    spawner_handler = SpawnerHandler(
        entity_factory=factory,
        scene=scene,
        spawn_on_enter=True,
        max_spawns=2,
    )
    spawner_entity.add_handler(spawner_handler)

    target_entity = _make_static_target("Target")
    target_entity.node.setPos(0.0, 0.0, 0.0)
    scene.add_entity(target_entity)

    # The spawner drives its own lifecycle here, so the stop -> start
    # transition under test is explicit.
    spawner_entity.start()
    assert spawner_entity.is_started

    # First enter edge: the target already sits inside the volume.
    world.doPhysics(DT)
    spawner_entity.update(DT)
    assert factory.call_count == 1
    assert spawner_handler.spawn_count == 1

    # Second enter edge: leave the volume and come back.
    _leave_zone(target_entity)
    world.doPhysics(DT)
    spawner_entity.update(DT)
    _enter_zone(target_entity)
    world.doPhysics(DT)
    spawner_entity.update(DT)
    assert factory.call_count == 2
    assert spawner_handler.spawn_count == 2

    # The budget is exhausted: further spawns are refused.
    assert spawner_handler.spawn() is None
    assert spawner_handler.spawn_count == 2
    assert factory.call_count == 2

    # Stopping frees the tracked spawns but keeps the spawn counter.
    spawner_entity.stop()
    assert spawner_handler.spawned_entities == []
    assert spawner_handler.spawn_count == 2

    # Restarting must not hand out a fresh budget.
    spawner_entity.start()
    assert spawner_handler.spawn_count == 2
    assert spawner_handler.spawn() is None
    assert spawner_handler.spawn_count == 2

    # The automatic path stays blocked as well.
    world.doPhysics(DT)
    spawner_entity.update(DT)
    assert spawner_handler.spawn_count == 2
    assert factory.call_count == 2


def test_subscription_is_symmetric_across_stop_start():
    """``on_start`` subscribes once and ``on_stop`` unsubscribes once.

    A leaked subscription would call ``_on_enter`` twice after a restart and
    produce two spawns from a single enter edge.
    """
    world = Physics.get_world()
    scene = _new_scene()

    factory = _Factory()
    spawner_entity = _make_zone_entity("Spawner")
    spawner_handler = SpawnerHandler(
        entity_factory=factory, scene=scene, spawn_on_enter=True
    )
    spawner_entity.add_handler(spawner_handler)
    scene.add_entity(spawner_entity)

    trigger = spawner_entity.get_handler(TriggerZoneHandler)
    assert trigger is not None
    assert len(trigger.on_enter) == 1, "on_start must subscribe exactly once"

    target_entity = _make_static_target("Target")
    target_entity.node.setPos(0.0, 0.0, 0.0)
    scene.add_entity(target_entity)

    world.doPhysics(DT)
    spawner_entity.update(DT)
    assert factory.call_count == 1

    spawner_entity.stop()
    assert len(trigger.on_enter) == 0, "on_stop must unsubscribe exactly once"

    spawner_entity.start()
    assert len(trigger.on_enter) == 1, "on_start must resubscribe exactly once"

    # One enter edge after the restart produces exactly one spawn.
    world.doPhysics(DT)
    spawner_entity.update(DT)
    assert factory.call_count == 2, "a single enter must not spawn twice"


def test_cooldown_resets_on_start():
    """A stop -> start cycle clears the remaining cooldown.

    Without the reset, the spawner would resume with the stale remainder and
    reject the first enter after restarting.
    """
    world = Physics.get_world()
    scene = _new_scene()

    factory = _Factory()
    spawner_entity = _make_zone_entity("Spawner")
    spawner_handler = SpawnerHandler(
        entity_factory=factory,
        scene=scene,
        spawn_on_enter=True,
        cooldown=1.0,
    )
    spawner_entity.add_handler(spawner_handler)
    scene.add_entity(spawner_entity)

    target_entity = _make_static_target("Target")
    target_entity.node.setPos(0.0, 0.0, 0.0)
    scene.add_entity(target_entity)

    world.doPhysics(DT)
    spawner_entity.update(DT)
    assert factory.call_count == 1
    assert spawner_handler.spawn() is None, "the cooldown window must be open"

    # Advance only a fraction of the cooldown window.
    for _ in range(10):
        world.doPhysics(DT)
        spawner_entity.update(DT)

    spawner_entity.stop()
    spawner_entity.start()

    # The trigger re-fires enter (it cleared its overlap state on stop); the
    # reset cooldown must allow the spawn immediately.
    world.doPhysics(DT)
    spawner_entity.update(DT)
    assert factory.call_count == 2, "on_start must clear the remaining cooldown"


def test_remove_handler_from_started_entity_frees_spawns():
    """Removing the handler from an active entity frees its spawns and unsubscribes."""
    world = Physics.get_world()
    scene = _new_scene()

    factory = _Factory()
    spawner_entity = _make_zone_entity("Spawner")
    spawner_handler = SpawnerHandler(
        entity_factory=factory, scene=scene, spawn_on_enter=True
    )
    spawner_entity.add_handler(spawner_handler)
    scene.add_entity(spawner_entity)

    target_entity = _make_static_target("Target")
    target_entity.node.setPos(0.0, 0.0, 0.0)
    scene.add_entity(target_entity)

    world.doPhysics(DT)
    spawner_entity.update(DT)
    assert factory.call_count == 1

    spawned = spawner_handler.spawned_entities[0]
    trigger = spawner_entity.get_handler(TriggerZoneHandler)
    assert trigger is not None

    assert spawner_entity.remove_handler(spawner_handler)

    assert spawned.is_freed, "detaching from a started entity must free tracked spawns"
    assert spawned.id not in scene.entities
    assert spawner_handler.spawned_entities == []
    assert len(trigger.on_enter) == 0


def test_spawn_without_scene_tracks_and_clears():
    """``scene=None`` still builds and tracks spawns, and cleanup frees them."""
    factory = _Factory()
    spawner_entity = _make_zone_entity("Spawner")
    spawner_handler = SpawnerHandler(entity_factory=factory, spawn_on_enter=False)
    spawner_entity.add_handler(spawner_handler)

    spawned = spawner_handler.spawn()
    assert spawned is not None
    assert not spawned.is_freed
    assert factory.call_count == 1
    assert spawner_handler.spawned_entities == [spawned]

    spawner_handler.clear_spawned()
    assert spawned.is_freed
    assert spawner_handler.spawned_entities == []


def test_clear_spawned_deregisters_a_spawn_freed_elsewhere():
    """A spawn freed elsewhere is still removed from the scene registry.

    ``Entity.free`` does not touch ``Scene.entities``, so without the explicit
    deregistration the stale entry would keep the freed entity referenced.
    """
    scene = _new_scene()

    factory = _Factory()
    spawner_entity = _make_zone_entity("Spawner")
    spawner_handler = SpawnerHandler(
        entity_factory=factory, scene=scene, spawn_on_enter=False
    )
    spawner_entity.add_handler(spawner_handler)

    spawned = spawner_handler.spawn()
    assert spawned is not None
    spawned_id = spawned.id
    assert scene.get_entity(spawned_id) is spawned

    spawned.free()
    assert scene.get_entity(spawned_id) is spawned, "free() leaves the registry entry"

    spawner_handler.clear_spawned()

    assert scene.get_entity(spawned_id) is None, (
        "clear_spawned must deregister stale spawns"
    )
    assert spawner_handler.spawned_entities == []


def test_freed_spawn_is_pruned_and_never_stops_recycled_entity():
    """A spawn freed elsewhere is skipped, even if its id is recycled.

    ``Entity.free`` recycles ids LIFO, so removing a stale tracked id from the
    scene would stop an unrelated live entity that inherited that id.
    """
    scene = _new_scene()

    factory = _Factory()
    spawner_entity = _make_zone_entity("Spawner")
    spawner_handler = SpawnerHandler(
        entity_factory=factory, scene=scene, spawn_on_enter=False
    )
    spawner_entity.add_handler(spawner_handler)

    first = spawner_handler.spawn()
    assert first is not None
    first_id = first.id
    assert scene.get_entity(first_id) is first

    # Freed elsewhere, e.g. by HealthHandler(auto_free_on_death=True).
    first.free()
    assert spawner_handler.spawned_entities == [], "dead spawns are not alive spawns"

    # The recycled id now belongs to an unrelated live entity.
    unrelated = _track(Entity("Unrelated"))
    assert unrelated.id == first_id, "entity ids are recycled LIFO"
    scene.add_entity(unrelated)

    spawner_handler.clear_spawned()

    assert not unrelated.is_freed, (
        "clear_spawned must not stop an entity that reused the id"
    )
    assert scene.get_entity(first_id) is unrelated


def test_disabled_spawner_ignores_enter_until_reenabled():
    """``set_enabled(False)`` pauses automatic spawning."""
    world = Physics.get_world()
    scene = _new_scene()

    factory = _Factory()
    spawner_entity = _make_zone_entity("Spawner")
    spawner_handler = SpawnerHandler(
        entity_factory=factory, scene=scene, spawn_on_enter=True
    )
    spawner_entity.add_handler(spawner_handler)
    scene.add_entity(spawner_entity)

    target_entity = _make_static_target("Target")
    target_entity.node.setPos(0.0, 0.0, 0.0)
    scene.add_entity(target_entity)

    world.doPhysics(DT)
    spawner_entity.update(DT)
    assert factory.call_count == 1

    spawner_handler.set_enabled(False)
    _cycle_enter(world, spawner_entity, target_entity)
    assert factory.call_count == 1, "a disabled spawner must ignore enter events"

    spawner_handler.set_enabled(True)
    _cycle_enter(world, spawner_entity, target_entity)
    assert factory.call_count == 2, "re-enabling restores automatic spawning"


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__]))
