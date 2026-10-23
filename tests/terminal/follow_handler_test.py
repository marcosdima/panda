"""Headless tests for FollowHandler (no window)."""

import math

import pytest

from src.entities.entity import Entity
from src.handlers.ai.follow import FollowHandler
from src.handlers.input.action_map import SPRINT
from src.handlers.input.base import InputHandler
from src.handlers.physics import CharacterControllerHandler


def _make_entity(name: str) -> Entity:
    return Entity(name)


def _make_pair() -> tuple[Entity, Entity, InputHandler, FollowHandler]:
    follower = _make_entity("follower")
    target = _make_entity("target")
    ih = InputHandler()
    fh = FollowHandler(target=target)
    follower.add_handler(ih)
    follower.add_handler(fh)
    return follower, target, ih, fh


def _make_controlled_pair() -> tuple[
    Entity, Entity, InputHandler, FollowHandler, CharacterControllerHandler, CharacterControllerHandler
]:
    """Build a follower/target pair whose bodies are Bullet character controllers.

    The entity nodes stay at the origin while the controller nodes carry the
    real body transforms, which is exactly the situation the follow brain has
    to resolve: a ``CharacterControllerHandler`` moves its own Bullet node, so
    the entity node is not the authoritative position.
    """
    follower = _make_entity("follower")
    target = _make_entity("target")
    ih = InputHandler()
    fh = FollowHandler(target=target)
    follower_cc = CharacterControllerHandler()
    target_cc = CharacterControllerHandler()

    # Attach order matters: the brain writes the intent, the controller reads it.
    follower.add_handler(ih)
    follower.add_handler(fh)
    follower.add_handler(follower_cc)
    target.add_handler(target_cc)
    return follower, target, ih, fh, follower_cc, target_cc


def test_follow_points_toward_target():
    follower, target, ih, fh = _make_pair()
    follower.node.setPos(0, 0, 0)
    target.node.setPos(10, 0, 0)
    fh.on_start()
    fh.on_update(0.016)
    assert fh.state == "following"
    assert ih.move_vector.x > 0.9
    assert abs(ih.move_vector.y) < 1e-6


def test_stops_within_stop_radius():
    follower, target, ih, fh = _make_pair()
    follower.node.setPos(0, 0, 0)
    target.node.setPos(0.5, 0, 0)  # within stop_radius (1.5)
    fh.on_start()
    fh.on_update(0.016)
    assert fh.state == "stopped"
    assert ih.move_vector.length() < 1e-6


def test_stops_within_min_distance_when_no_stop_radius():
    follower, target, ih, fh = _make_pair()
    follower.node.setPos(0, 0, 0)
    target.node.setPos(1.0, 0, 0)  # within min_distance (1.5)
    fh.on_start()
    fh.on_update(0.016)
    assert fh.state == "stopped"
    assert ih.move_vector.length() < 1e-6


def test_out_of_range_beyond_max_distance():
    follower, target, ih, fh = _make_pair()
    follower.node.setPos(0, 0, 0)
    target.node.setPos(50, 0, 0)
    fh.max_distance = 10.0
    fh.on_start()
    fh.on_update(0.016)
    assert fh.state == "out_of_range"
    assert ih.move_vector.length() < 1e-6


def test_zero_intent_when_no_target():
    follower = _make_entity("follower")
    ih = InputHandler()
    fh = FollowHandler(target=None)
    follower.add_handler(ih)
    follower.add_handler(fh)
    follower.node.setPos(0, 0, 0)
    fh.on_start()
    fh.on_update(0.016)
    assert fh.state == "stopped"
    assert ih.move_vector.length() < 1e-6


def test_set_target_none_stops_following():
    follower, target, ih, fh = _make_pair()
    follower.node.setPos(0, 0, 0)
    target.node.setPos(10, 0, 0)
    fh.on_start()
    fh.on_update(0.016)
    assert fh.state == "following"
    fh.set_target(None)
    fh.on_update(0.016)
    assert fh.state == "stopped"
    assert ih.move_vector.length() < 1e-6


def test_target_freed_stops_following():
    follower, target, ih, fh = _make_pair()
    follower.node.setPos(0, 0, 0)
    target.node.setPos(10, 0, 0)
    fh.on_start()
    fh.on_update(0.016)
    assert fh.state == "following"
    target.free()
    fh.on_update(0.016)
    assert fh.state == "stopped"
    assert ih.move_vector.length() < 1e-6


def test_speed_factor_scales_intent():
    follower, target, ih, fh = _make_pair()
    follower.node.setPos(0, 0, 0)
    target.node.setPos(10, 0, 0)
    fh.speed_factor = 0.5
    fh.on_start()
    fh.on_update(0.016)
    assert fh.state == "following"
    # The scaled vector is shorter than 1.0, so InputHandler does not clamp it.
    assert ih.move_vector.x == pytest.approx(0.5)
    assert ih.move_vector.y == pytest.approx(0.0)
    assert fh.move_vector.x == pytest.approx(0.5)


def test_speed_factor_above_one_is_capped_at_unit_length():
    follower, target, ih, fh = _make_pair()
    follower.node.setPos(0, 0, 0)
    # A diagonal target keeps the assertions from collapsing onto one axis.
    target.node.setPos(10, 5, 0)
    fh.speed_factor = 2.0
    fh.on_start()
    fh.on_update(0.016)

    assert fh.state == "following"

    distance = math.hypot(10.0, 5.0)
    unit_x = 10.0 / distance
    unit_y = 5.0 / distance

    # The written vector is capped at unit length, so 2.0 behaves exactly
    # like 1.0: the intent is the plain unit direction toward the target.
    assert ih.move_vector.length() == pytest.approx(1.0)
    assert ih.move_vector.x == pytest.approx(unit_x)
    assert ih.move_vector.y == pytest.approx(unit_y)
    # The handler's own mirror proves the cap happened in the brain and not
    # only in the InputHandler, which normalizes long vectors as well.
    assert fh.move_vector.length() == pytest.approx(1.0)
    assert fh.move_vector == ih.move_vector


def test_negative_speed_factor_points_away_from_target():
    follower, target, ih, fh = _make_pair()
    follower.node.setPos(0, 0, 0)
    target.node.setPos(10, 5, 0)
    fh.speed_factor = -0.5
    fh.on_start()
    fh.on_update(0.016)

    assert fh.state == "following"

    distance = math.hypot(10.0, 5.0)
    unit_x = 10.0 / distance
    unit_y = 5.0 / distance

    # The clamp is on the length, not on the sign: the intent is the unit
    # direction toward the target scaled by -0.5, so the follower walks
    # away from the target instead of toward it.
    assert ih.move_vector.x == pytest.approx(-0.5 * unit_x)
    assert ih.move_vector.y == pytest.approx(-0.5 * unit_y)
    assert ih.move_vector.length() == pytest.approx(0.5)
    # Away from the target: the dot product with the direction to the target
    # is negative on both axes.
    assert ih.move_vector.x * unit_x + ih.move_vector.y * unit_y < 0.0
    assert ih.move_vector.x < 0.0
    assert ih.move_vector.y < 0.0


def test_chase_sprint_sets_action():
    follower, target, ih, fh = _make_pair()
    follower.node.setPos(0, 0, 0)
    target.node.setPos(10, 0, 0)
    fh.chase_sprint = True
    fh.on_start()
    fh.on_update(0.016)
    assert fh.state == "following"
    assert ih.is_action_down(SPRINT) is True


def test_disabled_handler_writes_no_intent():
    follower, target, ih, fh = _make_pair()
    follower.node.setPos(0, 0, 0)
    target.node.setPos(10, 0, 0)
    fh.set_enabled(False)
    # Only enabled handlers receive the frame hooks, and the gate lives in
    # Entity.on_update, so the tick has to go through the entity.
    follower.start()
    follower.update(0.016)
    assert fh.state == "following"
    assert ih.move_vector.length() < 1e-6


def test_on_stop_writes_zero_intent():
    follower, target, ih, fh = _make_pair()
    follower.node.setPos(0, 0, 0)
    target.node.setPos(10, 0, 0)
    fh.on_start()
    fh.on_update(0.016)
    assert ih.move_vector.length() > 0.5
    fh.on_stop()
    assert ih.move_vector.length() < 1e-6


def test_last_move_vector_mirror():
    follower, target, ih, fh = _make_pair()
    follower.node.setPos(0, 0, 0)
    target.node.setPos(10, 0, 0)
    fh.on_start()
    fh.on_update(0.016)
    assert fh.move_vector.x > 0.9
    assert fh.move_vector == ih.move_vector


def test_sprint_cleared_when_target_enters_stop_radius():
    follower, target, ih, fh = _make_pair()
    follower.node.setPos(0, 0, 0)
    target.node.setPos(10, 0, 0)
    fh.chase_sprint = True
    fh.on_start()
    fh.on_update(0.016)
    assert fh.state == "following"
    assert ih.is_action_down(SPRINT) is True

    # The target walks inside the stop radius: the brain must release sprint.
    target.node.setPos(0.5, 0, 0)
    fh.on_update(0.016)
    assert fh.state == "stopped"
    assert ih.is_action_down(SPRINT) is False
    assert ih.move_vector.length() < 1e-6


def test_sprint_cleared_when_target_goes_out_of_range():
    follower, target, ih, fh = _make_pair()
    follower.node.setPos(0, 0, 0)
    target.node.setPos(10, 0, 0)
    fh.max_distance = 12.0
    fh.chase_sprint = True
    fh.on_start()
    fh.on_update(0.016)
    assert fh.state == "following"
    assert ih.is_action_down(SPRINT) is True

    # The target leaves the leash: the brain must release sprint.
    target.node.setPos(40, 0, 0)
    fh.on_update(0.016)
    assert fh.state == "out_of_range"
    assert ih.is_action_down(SPRINT) is False
    assert ih.move_vector.length() < 1e-6


def test_sprint_cleared_when_target_is_cleared():
    follower, target, ih, fh = _make_pair()
    follower.node.setPos(0, 0, 0)
    target.node.setPos(10, 0, 0)
    fh.chase_sprint = True
    fh.on_start()
    fh.on_update(0.016)
    assert ih.is_action_down(SPRINT) is True

    fh.set_target(None)
    fh.on_update(0.016)
    assert fh.state == "stopped"
    assert ih.is_action_down(SPRINT) is False


def test_on_start_writes_zero_intent():
    follower, target, ih, fh = _make_pair()
    follower.node.setPos(0, 0, 0)
    target.node.setPos(10, 0, 0)

    # A stale intent from a previous writer must be wiped when the brain starts.
    ih.set_move_vector(1.0, 0.0)
    ih.set_action_state(SPRINT, True)

    fh.on_start()

    assert ih.move_vector.length() < 1e-6
    assert ih.is_action_down(SPRINT) is False
    assert fh.move_vector.length() < 1e-6


def test_public_exports_expose_follow_handler():
    import src.handlers as handlers_package
    import src.handlers.ai as ai_package
    from src.handlers import FollowHandler as FromHandlersPackage
    from src.handlers.ai import FollowHandler as FromAiPackage

    assert FromHandlersPackage is FollowHandler
    assert FromAiPackage is FollowHandler
    assert "FollowHandler" in handlers_package.__all__
    assert "FollowHandler" in ai_package.__all__


def test_public_exports_expose_follow_state():
    import src.handlers as handlers_package
    import src.handlers.ai as ai_package
    from src.handlers import FollowState as FromHandlersPackage
    from src.handlers.ai import FollowState as FromAiPackage
    from src.handlers.ai.follow import FollowState as FromFollowModule

    assert FromHandlersPackage is FromFollowModule
    assert FromAiPackage is FromFollowModule
    assert "FollowState" in handlers_package.__all__
    assert "FollowState" in ai_package.__all__


def test_min_distance_mirrors_stop_radius_when_stop_radius_is_not_explicit():
    follower, target, ih, fh = _make_pair()

    # Construction default: stop_radius starts out mirroring min_distance.
    assert fh.min_distance == pytest.approx(1.5)
    assert fh.stop_radius == pytest.approx(1.5)

    fh.min_distance = 3.0

    assert fh.min_distance == pytest.approx(3.0)
    assert fh.stop_radius == pytest.approx(3.0)

    # The mirrored radius is the one the brain reads at runtime: a target at
    # 2.0 m is now inside the stop radius, so the follower holds its ground.
    follower.node.setPos(0, 0, 0)
    target.node.setPos(2.0, 0, 0)
    fh.on_start()
    fh.on_update(0.016)
    assert fh.state == "stopped"
    assert ih.move_vector.length() < 1e-6


def test_min_distance_does_not_override_stop_radius_set_by_constructor():
    follower = _make_entity("follower")
    target = _make_entity("target")
    ih = InputHandler()
    fh = FollowHandler(target=target, stop_radius=4.0)
    follower.add_handler(ih)
    follower.add_handler(fh)

    assert fh.stop_radius == pytest.approx(4.0)

    fh.min_distance = 1.0

    # An explicit stop_radius stays authoritative: min_distance is inert.
    assert fh.min_distance == pytest.approx(1.0)
    assert fh.stop_radius == pytest.approx(4.0)

    # Behaviour follows the explicit radius: 2.0 m is inside it, 6.0 m is not.
    follower.node.setPos(0, 0, 0)
    target.node.setPos(2.0, 0, 0)
    fh.on_start()
    fh.on_update(0.016)
    assert fh.state == "stopped"
    assert ih.move_vector.length() < 1e-6

    target.node.setPos(6.0, 0, 0)
    fh.on_update(0.016)
    assert fh.state == "following"
    assert ih.move_vector.x == pytest.approx(1.0)


def test_min_distance_does_not_override_stop_radius_set_after_construction():
    follower, target, ih, fh = _make_pair()

    # The setter marks the radius as explicit, so a later min_distance write
    # must not steal the effective stop distance back.
    fh.stop_radius = 4.0
    fh.min_distance = 1.0

    assert fh.min_distance == pytest.approx(1.0)
    assert fh.stop_radius == pytest.approx(4.0)

    follower.node.setPos(0, 0, 0)
    target.node.setPos(2.0, 0, 0)
    fh.on_start()
    fh.on_update(0.016)
    assert fh.state == "stopped"
    assert ih.move_vector.length() < 1e-6


def test_follow_uses_target_character_controller_position():
    follower, target, ih, fh, follower_cc, target_cc = _make_controlled_pair()
    try:
        # The entity nodes stay at the origin; only the Bullet bodies moved.
        follower.node.setPos(0, 0, 0)
        target.node.setPos(0, 0, 0)
        assert follower_cc.controller_np is not None
        assert target_cc.controller_np is not None
        follower_cc.controller_np.setPos(0.0, 0.0, 0.0)
        target_cc.controller_np.setPos(10.0, 0.0, 0.0)

        fh.on_start()
        fh.on_update(0.016)

        # Resolving through the entity node would report a distance of 0 and
        # therefore "stopped"; resolving through the controller must follow.
        assert fh.state == "following"
        assert ih.move_vector.x == pytest.approx(1.0)
        assert ih.move_vector.y == pytest.approx(0.0)
    finally:
        follower.free()
        target.free()


def test_follow_direction_uses_controller_positions_of_both_bodies():
    follower, target, ih, fh, follower_cc, target_cc = _make_controlled_pair()
    try:
        # The controllers are parented under the entity nodes, so the body world
        # position is entity node + controller offset. Node-only resolution
        # would point the follower at -X; the controller positions point it +Y.
        follower.node.setPos(10.0, 0.0, 0.0)
        target.node.setPos(0.0, 0.0, 0.0)
        assert follower_cc.controller_np is not None
        assert target_cc.controller_np is not None
        follower_cc.controller_np.setPos(-10.0, 0.0, 0.0)
        target_cc.controller_np.setPos(0.0, 10.0, 0.0)

        fh.on_start()
        fh.on_update(0.016)

        assert fh.state == "following"
        assert ih.move_vector.x == pytest.approx(0.0)
        assert ih.move_vector.y == pytest.approx(1.0)
    finally:
        follower.free()
        target.free()


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__]))
