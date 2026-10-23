"""Headless tests for ProximitySensorHandler (no window, no Bullet)."""

import math

import pytest
from panda3d.core import NodePath

from src.entities.entity import Entity
from src.handlers import ProximitySensorHandler as ExportedProximitySensorHandler
from src.handlers.sensors import ProximitySensorHandler
from src.scenes import Scene
from src.utils.position import world_position

DT = 1.0 / 60.0


@pytest.fixture
def scene():
    """Started scene, stopped (and its entities freed) after the test."""
    active = Scene()
    active.on_start()
    yield active
    active.on_stop()


def _entity(scene: Scene, name: str, position: tuple[float, float, float]) -> Entity:
    entity = Entity(name)
    entity.node.setPos(*position)
    scene.add_entity(entity)
    return entity


def _sensor(
    scene: Scene, **kwargs
) -> tuple[Entity, ProximitySensorHandler]:
    entity = Entity("Sensor")
    entity.node.setPos(0.0, 0.0, 0.0)
    handler = ProximitySensorHandler(scene=scene, **kwargs)
    entity.add_handler(handler)
    scene.add_entity(entity)
    return entity, handler


def _record(handler: ProximitySensorHandler) -> list[tuple[str, Entity, float]]:
    events: list[tuple[str, Entity, float]] = []
    handler.on_enter.add_callback(
        lambda entity, distance: events.append(("enter", entity, distance))
    )
    handler.on_stay.add_callback(
        lambda entity, distance: events.append(("stay", entity, distance))
    )
    handler.on_exit.add_callback(
        lambda entity, distance: events.append(("exit", entity, distance))
    )
    return events


def test_enter_stay_and_exit_sequence(scene):
    sensor_entity, handler = _sensor(scene, radius=5.0)
    target = _entity(scene, "Target", (3.0, 0.0, 0.0))
    events = _record(handler)

    sensor_entity.update(DT)
    assert events == [("enter", target, pytest.approx(3.0))]

    events.clear()
    sensor_entity.update(DT)
    assert events == [("stay", target, pytest.approx(3.0))]

    target.node.setPos(6.0, 0.0, 0.0)
    events.clear()
    sensor_entity.update(DT)
    assert events == [("exit", target, pytest.approx(6.0))]
    assert handler.sensed_entities == []


def test_exit_radius_provides_hysteresis(scene):
    sensor_entity, handler = _sensor(scene, radius=3.0, exit_radius=6.0)
    target = _entity(scene, "Target", (2.0, 0.0, 0.0))
    events = _record(handler)

    sensor_entity.update(DT)
    assert [kind for kind, _entity_, _distance in events] == ["enter"]

    # Beyond the enter radius but inside the exit radius: still sensed.
    target.node.setPos(5.0, 0.0, 0.0)
    events.clear()
    sensor_entity.update(DT)
    assert [kind for kind, _entity_, _distance in events] == ["stay"]
    assert handler.is_in_range(target)

    # Beyond the exit radius: leaves.
    target.node.setPos(6.5, 0.0, 0.0)
    events.clear()
    sensor_entity.update(DT)
    assert [kind for kind, _entity_, _distance in events] == ["exit"]


def test_exit_radius_does_not_widen_the_entry_gate(scene):
    """A fresh candidate inside the hysteresis band is not sensed until it enters."""
    sensor_entity, handler = _sensor(scene, radius=3.0, exit_radius=6.0)
    target = _entity(scene, "Target", (5.0, 0.0, 0.0))
    events = _record(handler)

    sensor_entity.update(DT)

    assert events == []
    assert not handler.is_in_range(target)
    assert handler.sensed_entities == []

    target.node.setPos(2.5, 0.0, 0.0)
    sensor_entity.update(DT)

    assert [kind for kind, _entity_, _distance in events] == ["enter"]


def test_sensed_entities_nearest_first(scene):
    sensor_entity, handler = _sensor(scene, radius=10.0)
    far = _entity(scene, "Far", (4.0, 0.0, 0.0))
    near = _entity(scene, "Near", (1.0, 0.0, 0.0))
    middle = _entity(scene, "Middle", (2.0, 0.0, 0.0))

    sensor_entity.update(DT)

    assert handler.sensed_entities == [near, middle, far]
    assert handler.nearest is near


def test_sensor_ignores_itself(scene):
    sensor_entity, handler = _sensor(scene, radius=5.0)
    events = _record(handler)

    sensor_entity.update(DT)

    assert events == []
    assert handler.sensed_entities == []


def test_predicate_filters_candidates(scene):
    sensor_entity, handler = _sensor(
        scene, radius=10.0, predicate=lambda entity: entity.name.startswith("NPC")
    )
    _entity(scene, "Scenery", (1.0, 0.0, 0.0))
    npc = _entity(scene, "NPC-Guard", (2.0, 0.0, 0.0))

    sensor_entity.update(DT)

    assert handler.sensed_entities == [npc]


def test_freed_candidate_is_ignored(scene):
    sensor_entity, handler = _sensor(scene, radius=10.0)
    target = _entity(scene, "Target", (1.0, 0.0, 0.0))
    events = _record(handler)

    target.free()  # free() leaves the scene registry entry in place
    sensor_entity.update(DT)

    assert events == []
    assert handler.sensed_entities == []


def test_freed_sensed_entity_emits_exit(scene):
    sensor_entity, handler = _sensor(scene, radius=10.0)
    target = _entity(scene, "Target", (2.0, 0.0, 0.0))
    events = _record(handler)

    sensor_entity.update(DT)
    events.clear()

    target.free()
    sensor_entity.update(DT)

    assert events == [("exit", target, pytest.approx(2.0))]
    assert handler.sensed_entities == []


def test_queries_skip_a_freed_entity_before_the_next_update(scene):
    """Queries report liveness immediately, not only after the next scan."""
    sensor_entity, handler = _sensor(scene, radius=10.0)
    target = _entity(scene, "Target", (2.0, 0.0, 0.0))
    events = _record(handler)

    sensor_entity.update(DT)
    assert handler.sensed_entities == [target]

    target.free()

    assert handler.sensed_entities == []
    assert handler.nearest is None
    assert not handler.is_in_range(target)

    # The next scan reports the exit once, with the last measured distance.
    events.clear()
    sensor_entity.update(DT)
    assert events == [("exit", target, pytest.approx(2.0))]


def test_clear_from_an_exit_callback_stops_pending_events(scene):
    """``clear()`` inside a callback aborts the rest of the frame's events."""
    sensor_entity, handler = _sensor(scene, radius=5.0)
    first = _entity(scene, "First", (1.0, 0.0, 0.0))
    second = _entity(scene, "Second", (2.0, 0.0, 0.0))
    exits: list[str] = []

    def on_exit(entity: Entity, _distance: float) -> None:
        exits.append(entity.name)
        handler.clear()

    handler.on_exit.add_callback(on_exit)
    sensor_entity.update(DT)

    first.node.setPos(9.0, 0.0, 0.0)
    second.node.setPos(9.0, 0.0, 0.0)
    sensor_entity.update(DT)

    assert exits == ["First"], "clear() must abort the remaining exit events"
    assert handler.sensed_entities == []


def test_clear_drops_sensed_set_without_events(scene):
    sensor_entity, handler = _sensor(scene, radius=10.0)
    _entity(scene, "Target", (2.0, 0.0, 0.0))
    events = _record(handler)

    sensor_entity.update(DT)
    events.clear()

    handler.clear()

    assert handler.sensed_entities == []
    assert events == []

    # Still inside the radius: the next update re-enters.
    sensor_entity.update(DT)
    assert [kind for kind, _entity_, _distance in events] == ["enter"]


def test_stop_clears_without_exit_events(scene):
    sensor_entity, handler = _sensor(scene, radius=10.0)
    _entity(scene, "Target", (2.0, 0.0, 0.0))
    events = _record(handler)

    sensor_entity.update(DT)
    events.clear()

    sensor_entity.stop()

    assert handler.sensed_entities == []
    assert events == []


def test_detach_clears_sensed_set(scene):
    sensor_entity, handler = _sensor(scene, radius=10.0)
    _entity(scene, "Target", (2.0, 0.0, 0.0))
    events = _record(handler)

    sensor_entity.update(DT)
    events.clear()

    assert sensor_entity.remove_handler(handler)

    assert handler.sensed_entities == []
    assert events == []


def test_free_of_a_never_started_entity_clears_the_sensed_set(scene):
    """``free()`` skips ``on_stop`` for a never-started entity but still detaches."""
    sensor = Entity("Sensor")
    handler = ProximitySensorHandler(radius=10.0, scene=scene)
    sensor.add_handler(handler)
    target = _entity(scene, "Target", (2.0, 0.0, 0.0))
    events = _record(handler)

    handler.on_update(DT)  # never started, so the hook is called directly
    assert handler.sensed_entities == [target]

    sensor.free()

    assert handler.sensed_entities == []
    assert [kind for kind, _entity_, _distance in events] == ["enter"]


def test_scene_none_is_inert(scene):
    entity = Entity("Sensor")
    handler = ProximitySensorHandler(radius=5.0)  # no scene
    entity.add_handler(handler)
    scene.add_entity(entity)
    events = _record(handler)

    _entity(scene, "Target", (1.0, 0.0, 0.0))
    entity.update(DT)

    assert handler.sensed_entities == []
    assert events == []


def test_assigning_a_new_scene_clears_the_sensed_set(scene):
    sensor_entity, handler = _sensor(scene, radius=10.0)
    _entity(scene, "Target", (2.0, 0.0, 0.0))
    events = _record(handler)

    sensor_entity.update(DT)
    assert len(handler.sensed_entities) == 1

    handler.scene = None

    assert handler.scene is None
    assert handler.sensed_entities == []
    assert [kind for kind, _entity_, _distance in events] == ["enter"]


def test_distance_to_and_is_in_range(scene):
    sensor_entity, handler = _sensor(scene, radius=5.0)
    target = _entity(scene, "Target", (3.0, 4.0, 0.0))

    sensor_entity.update(DT)

    assert handler.distance_to(target) == pytest.approx(5.0)
    assert handler.is_in_range(target)

    target.free()
    assert handler.distance_to(target) is None


def test_distance_matches_world_position(scene):
    """Distance is measured from the same authoritative position the helper reports."""
    sensor_entity, handler = _sensor(scene, radius=5.0)
    target = _entity(scene, "Target", (0.0, 0.0, 0.0))
    target.node.setPos(2.0, 0.0, 0.0)

    position = world_position(target)
    assert (position.x, position.y, position.z) == pytest.approx((2.0, 0.0, 0.0))
    assert handler.distance_to(target) == pytest.approx(2.0)


def test_world_position_resolves_parented_nodes_headless():
    """Without ``render``, positions resolve against the top-most ancestor."""
    root = NodePath("Root")
    root.setPos(10.0, 0.0, 0.0)
    child = Entity("Child")
    try:
        child.node.reparentTo(root)
        child.node.setPos(2.0, 0.0, 0.0)

        position = world_position(child)

        assert (position.x, position.y, position.z) == pytest.approx((12.0, 0.0, 0.0))
    finally:
        child.free()
        if not root.isEmpty():
            root.removeNode()


@pytest.mark.parametrize("radius", [0.0, -1.0, math.inf, math.nan])
def test_invalid_radius_is_rejected(radius):
    with pytest.raises(ValueError):
        ProximitySensorHandler(radius=radius)


def test_exit_radius_below_radius_is_rejected():
    with pytest.raises(ValueError):
        ProximitySensorHandler(radius=5.0, exit_radius=4.0)


def test_setters_validate_the_hysteresis_window():
    handler = ProximitySensorHandler(radius=5.0, exit_radius=8.0)

    handler.radius = 6.0
    handler.exit_radius = 6.0
    assert handler.radius == pytest.approx(6.0)
    assert handler.exit_radius == pytest.approx(6.0)

    with pytest.raises(ValueError):
        handler.radius = 9.0
    with pytest.raises(ValueError):
        handler.exit_radius = 5.0


def test_exported_from_handlers_package():
    assert ExportedProximitySensorHandler is ProximitySensorHandler


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__]))
