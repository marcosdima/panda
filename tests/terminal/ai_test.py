"""Headless tests for AIPatrolHandler (no window, no Bullet world)."""

import pytest
from panda3d.core import NodePath, Vec3

from src.entities.entity import Entity
from src.handlers.ai import AIPatrolHandler, PatrolState
from src.handlers.input.base import InputHandler
from src.handlers.physics.groups import LineOfSight


def make_npc(**kwargs):
    entity = Entity("Npc")
    inp = InputHandler()
    entity.add_handler(inp)
    kwargs.setdefault("line_of_sight", lambda a, b: True)
    ai = AIPatrolHandler(**kwargs)
    entity.add_handler(ai)
    entity.start()
    return entity, inp, ai


def step(entity, inp, ai, dt=0.1, speed=0.0):
    """Tick the entity, then integrate the commanded velocity like a controller would."""
    entity.update(dt)
    entity.node.setPos(
        entity.node.getPos()
        + Vec3(inp.move_vector.x, inp.move_vector.y, 0) * speed * dt
    )


def test_moves_toward_waypoint():
    entity, inp, ai = make_npc(waypoints=[Vec3(10, 0, 0)])
    entity.update(0.1)
    assert inp.move_vector.x == pytest.approx(
        1.0
    ) and inp.move_vector.y == pytest.approx(0.0)
    assert ai.state == PatrolState.PATROL


def test_no_waypoints_idles():
    entity, inp, ai = make_npc()
    entity.update(0.1)
    assert inp.move_vector.length() == 0.0


def test_arrive_waits_then_advances_loop():
    entity, inp, ai = make_npc(waypoints=[Vec3(0, 0, 0), Vec3(5, 0, 0)], wait_time=0.5)
    entity.update(0.1)  # already at waypoint 0 -> advance + wait
    assert ai.state == PatrolState.WAIT
    assert inp.move_vector.length() == 0.0
    for _ in range(6):
        entity.update(0.1)
    assert ai.state == PatrolState.PATROL
    assert ai.current_waypoint == Vec3(5, 0, 0)


def test_full_patrol_cycle_loops_and_ping_pong():
    pts = [Vec3(0, 0, 0), Vec3(4, 0, 0), Vec3(4, 4, 0)]
    entity, inp, ai = make_npc(waypoints=pts, wait_time=0.0)
    visited = []
    for _ in range(300):
        step(entity, inp, ai, speed=5.0)
        wp = ai.current_waypoint
        if not visited or visited[-1] != wp:
            visited.append(wp)
    # NPC starts on waypoint 0, so the first target is already waypoint 1.
    assert visited[:4] == [pts[1], pts[2], pts[0], pts[1]]

    entity, inp, ai = make_npc(waypoints=pts, wait_time=0.0, ping_pong=True)
    order = []
    for _ in range(400):
        step(entity, inp, ai, speed=5.0)
        wp = ai.current_waypoint
        if not order or order[-1] != wp:
            order.append(wp)
    assert order[:5] == [pts[1], pts[2], pts[1], pts[0], pts[1]]


def test_chase_and_lose_target():
    target = Entity("Player")
    target.node.setPos(5, 0, 0)
    entity, inp, ai = make_npc(
        waypoints=[Vec3(-10, 0, 0)], target=target, sight_range=8.0
    )
    entity.update(0.1)
    assert ai.state == PatrolState.CHASE
    assert inp.move_vector.x == pytest.approx(1.0)
    assert inp.is_action_down("sprint")

    target.node.setPos(50, 0, 0)  # beyond lose_range (12)
    entity.update(0.1)
    assert ai.state == PatrolState.PATROL
    assert not inp.is_action_down("sprint")
    assert inp.move_vector.x == pytest.approx(-1.0)


def test_line_of_sight_blocks_detection():
    target = Entity("Player")
    target.node.setPos(3, 0, 0)
    entity, inp, ai = make_npc(
        waypoints=[Vec3(-10, 0, 0)], target=target, line_of_sight=lambda a, b: False
    )
    entity.update(0.1)
    assert ai.state == PatrolState.PATROL


def test_freed_target_stops_chase():
    target = Entity("Player")
    target.node.setPos(3, 0, 0)
    entity, inp, ai = make_npc(waypoints=[Vec3(-10, 0, 0)], target=target)
    entity.update(0.1)
    assert ai.state == PatrolState.CHASE
    target.free()
    entity.update(0.1)
    assert ai.state == PatrolState.PATROL


def test_stop_clears_input():
    entity, inp, ai = make_npc(waypoints=[Vec3(10, 0, 0)])
    entity.update(0.1)
    ai.on_stop()
    assert inp.move_vector.length() == 0.0


# --- line of sight ------------------------------------------------------


def tagged_node(entity=None):
    """Build a raycast hit node, optionally tagged with the owning entity."""
    np = NodePath("hit")
    if entity is not None:
        np.setPythonTag("entity", entity)
    return np


def install_raycast(monkeypatch, result, calls=None):
    """Replace the Bullet raycast used by the LOS check and return its holder.

    The holder is a single-slot list so a test can change what the next
    raycast returns (e.g. wall first, then nothing).
    """
    holder = [result]

    def fake_raycast(from_pos, to_pos, mask=None, step_physics=True):
        if calls is not None:
            calls.append((Vec3(from_pos), Vec3(to_pos), mask, step_physics))
        return holder[0]

    monkeypatch.setattr("src.handlers.ai.patrol.Physics.raycast_closest", fake_raycast)
    return holder


def make_observer(target=None, **kwargs):
    """NPC using the real Bullet raycast for line of sight."""
    kwargs["line_of_sight"] = None
    entity, inp, ai = make_npc(target=target, **kwargs)
    return entity, inp, ai


def test_los_without_hit_is_visible(monkeypatch):
    calls = []
    install_raycast(monkeypatch, None, calls)
    target = Entity("Player")
    target.node.setPos(3, 0, 0)
    entity, inp, ai = make_observer(target=target)
    assert ai.can_see_target() is True
    assert len(calls) == 1


def test_los_target_body_hit_does_not_block(monkeypatch):
    target = Entity("Player")
    target.node.setPos(3, 0, 0)
    install_raycast(monkeypatch, (Vec3(3, 0, 1), tagged_node(target)))
    entity, inp, ai = make_observer(target=target)
    assert ai.can_see_target() is True


def test_los_observer_body_hit_does_not_block(monkeypatch):
    target = Entity("Player")
    target.node.setPos(3, 0, 0)
    entity, inp, ai = make_observer(target=target)
    install_raycast(monkeypatch, (Vec3(0, 0, 1), tagged_node(entity)))
    assert ai.can_see_target() is True


def test_los_world_geometry_hit_blocks(monkeypatch):
    target = Entity("Player")
    target.node.setPos(3, 0, 0)
    install_raycast(monkeypatch, (Vec3(1.5, 0, 1), tagged_node()))
    entity, inp, ai = make_observer(target=target)
    assert ai.can_see_target() is False


def test_los_other_entity_hit_blocks(monkeypatch):
    target = Entity("Player")
    target.node.setPos(3, 0, 0)
    other = Entity("Crate")
    install_raycast(monkeypatch, (Vec3(1.5, 0, 1), tagged_node(other)))
    entity, inp, ai = make_observer(target=target)
    assert ai.can_see_target() is False


def test_los_ignores_arrive_radius(monkeypatch):
    target = Entity("Player")
    target.node.setPos(3, 0, 0)
    install_raycast(monkeypatch, (Vec3(1.5, 0, 1), tagged_node()))
    entity, inp, ai = make_observer(target=target, arrive_radius=50.0)
    assert ai.can_see_target() is False


def test_los_uses_default_query_mask(monkeypatch):
    calls = []
    install_raycast(monkeypatch, None, calls)
    target = Entity("Player")
    target.node.setPos(3, 0, 0)
    entity, inp, ai = make_observer(target=target)
    assert ai.obstacle_mask == LineOfSight.QUERY_MASK
    ai.can_see_target()
    assert calls[0][2] == LineOfSight.QUERY_MASK


def test_injected_line_of_sight_takes_precedence(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("the raycast must not run when a callable is injected")

    monkeypatch.setattr("src.handlers.ai.patrol.Physics.raycast_closest", boom)
    target = Entity("Player")
    target.node.setPos(3, 0, 0)
    entity, inp, ai = make_npc(target=target, line_of_sight=lambda a, b: False)
    assert ai.can_see_target() is False


def test_line_of_sight_source_can_be_toggled_at_runtime(monkeypatch):
    holder = install_raycast(monkeypatch, (Vec3(1.5, 0, 1), tagged_node()))
    target = Entity("Player")
    target.node.setPos(3, 0, 0)
    entity, inp, ai = make_npc(target=target, line_of_sight=lambda a, b: True)
    assert ai.can_see_target() is True

    ai.line_of_sight = None
    assert ai.can_see_target() is False

    holder[0] = None
    assert ai.can_see_target() is True


def test_chase_requires_visible_target(monkeypatch):
    holder = install_raycast(monkeypatch, (Vec3(1.5, 0, 1), tagged_node()))
    target = Entity("Player")
    target.node.setPos(3, 0, 0)
    entity, inp, ai = make_observer(waypoints=[Vec3(-10, 0, 0)], target=target)
    entity.update(0.1)
    assert ai.state == PatrolState.PATROL

    holder[0] = None  # wall disappears
    entity.update(0.1)
    assert ai.state == PatrolState.CHASE
    assert inp.move_vector.x == pytest.approx(1.0)


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__]))
