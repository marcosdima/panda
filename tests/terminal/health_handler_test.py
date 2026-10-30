"""Headless tests for HealthHandler (no window)."""

import pytest
from panda3d.core import Vec2

from src.entities.entity import Entity
from src.handlers.components.health_handler import HealthHandler
from src.handlers.input.base import InputHandler


def _make_entity(name: str) -> Entity:
    return Entity(name)


def _make_with_input(
    max_health: float = 100.0,
) -> tuple[Entity, HealthHandler, InputHandler]:
    entity = _make_entity("damageable")
    health = HealthHandler(max_health=max_health)
    ih = InputHandler()
    entity.add_handler(ih)
    entity.add_handler(health)
    return entity, health, ih


def _make_user_disabled_input() -> tuple[Entity, HealthHandler, InputHandler]:
    """Entity whose InputHandler was disabled by the user, not by the handler."""
    entity = _make_entity("user-disabled-input")
    ih = InputHandler()
    entity.add_handler(ih)
    ih.set_enabled(False)
    health = HealthHandler(max_health=100.0, disable_input_on_death=True)
    entity.add_handler(health)
    return entity, health, ih


class _RecordingInputHandler(InputHandler):
    """InputHandler that records every ``set_enabled`` transition."""

    def __init__(self) -> None:
        super().__init__()
        self.enable_calls: list[bool] = []

    def set_enabled(self, enabled: bool) -> None:
        self.enable_calls.append(enabled)
        super().set_enabled(enabled)


def test_damage_clamps_at_zero_and_dies():
    entity, health, _ = _make_with_input()
    health.on_start()
    assert health.take_damage(60.0) is True
    assert health.current_health == 40.0
    assert health.is_alive and not health.is_dead
    assert health.take_damage(40.0) is True
    assert health.current_health == 0.0
    assert health.is_dead and not health.is_alive
    entity.free()


def test_overkill_leaves_health_at_zero():
    entity, health, _ = _make_with_input()
    health.on_start()
    assert health.take_damage(200.0) is True
    assert health.current_health == 0.0
    assert health.is_dead
    entity.free()


def test_damage_while_dead_is_noop():
    entity, health, _ = _make_with_input()
    health.on_start()
    health.take_damage(100.0)
    assert health.take_damage(10.0) is False
    assert health.current_health == 0.0
    entity.free()


def test_heal_clamps_at_max_health():
    entity, health, _ = _make_with_input(max_health=50.0)
    health.on_start()
    health.take_damage(30.0)
    assert health.current_health == 20.0
    restored = health.heal(100.0)
    assert restored == 30.0
    assert health.current_health == 50.0
    assert health.is_alive
    entity.free()


def test_heal_while_dead_returns_zero():
    entity, health, _ = _make_with_input()
    health.on_start()
    health.take_damage(100.0)
    assert health.heal(50.0) == 0.0
    assert health.current_health == 0.0
    entity.free()


def test_negative_damage_is_noop():
    entity, health, _ = _make_with_input()
    health.on_start()
    assert health.take_damage(-10.0) is False
    assert health.current_health == 100.0
    entity.free()


def test_negative_heal_is_noop():
    entity, health, _ = _make_with_input()
    health.on_start()
    assert health.heal(-10.0) == 0.0
    assert health.current_health == 100.0
    entity.free()


def test_on_damage_and_on_death_payloads():
    entity, health, _ = _make_with_input()
    health.on_start()

    damage_events = []
    death_events = []
    health.on_damage.add_callback(lambda amount, source: damage_events.append((amount, source)))
    health.on_death.add_callback(lambda ent: death_events.append(ent))

    health.take_damage(30.0, source=entity)
    assert damage_events == [(30.0, entity)]
    assert death_events == []

    health.take_damage(70.0, source=entity)
    assert damage_events == [(30.0, entity), (70.0, entity)]
    assert death_events == [entity]
    entity.free()


def test_on_damage_fires_applied_amount():
    entity, health, _ = _make_with_input()
    health.on_start()

    damage_events = []
    health.on_damage.add_callback(lambda amount, source: damage_events.append((amount, source)))

    # Overkill: the payload carries the applied amount, not the requested one.
    health.take_damage(200.0, source=entity)
    assert damage_events == [(100.0, entity)]

    # A partial hit applies the full requested amount.
    entity2, health2, _ = _make_with_input()
    health2.on_start()
    partial_events = []
    health2.on_damage.add_callback(lambda amount, source: partial_events.append((amount, source)))
    health2.take_damage(30.0, source=entity2)
    assert partial_events == [(30.0, entity2)]
    entity.free()
    entity2.free()


def test_auto_free_on_death_frees_entity():
    entity, health, _ = _make_with_input()
    health.auto_free_on_death = True
    health.on_start()
    assert not entity.is_freed
    health.take_damage(100.0)
    assert entity.is_freed
    # Freeing the entity detached its handlers, so the health handler is gone.
    assert entity.get_handler(HealthHandler) is None
    # Already freed by the death path: freeing again is a no-op.
    entity.free()
    assert entity.is_freed is True


def test_auto_free_on_death_takes_precedence_over_disable_input():
    entity = _make_entity("auto-free")
    ih = _RecordingInputHandler()
    entity.add_handler(ih)
    health = HealthHandler(max_health=100.0, auto_free_on_death=True, disable_input_on_death=True)
    entity.add_handler(health)
    entity.on_start()

    assert ih.is_enabled is True
    health.take_damage(100.0)

    assert entity.is_freed is True
    # The entity was freed first, so the input-disable step was skipped.
    assert ih.is_enabled is True
    # The disable step never ran at all (it was skipped, not undone).
    assert ih.enable_calls == []
    # Already freed by the death path: freeing again is a no-op.
    entity.free()
    assert entity.is_freed is True


def test_pre_dead_entity_with_auto_free_skips_input_disable():
    """An entity born dead with ``auto_free_on_death`` keeps its input on.

    The entity is dead from the start (health clamped at construction), so
    ``on_start`` runs the death branch. ``auto_free_on_death`` takes
    precedence there, so the input-disable step is skipped and the input
    handler stays enabled.
    """
    entity = _make_entity("pre-dead-auto-free")
    ih = InputHandler()
    entity.add_handler(ih)
    health = HealthHandler(
        max_health=100.0,
        current_health=0.0,
        auto_free_on_death=True,
        disable_input_on_death=True,
    )
    entity.add_handler(health)

    entity.start()

    # The constructor clamped the starting health to zero: the entity was
    # born dead, before it ever ran.
    assert health.is_dead is True
    assert health.current_health == 0.0
    # ``auto_free_on_death`` wins over ``disable_input_on_death``: the death
    # branch of ``on_start`` must not disable the input.
    assert ih.is_enabled is True

    entity.free()
    assert entity.is_freed is True


def test_disable_input_on_death_disables_input_handler():
    entity, health, ih = _make_with_input()
    health.on_start()
    assert ih.is_enabled is True
    health.take_damage(100.0)
    assert health.is_dead
    assert ih.is_enabled is False
    entity.free()


def test_death_clears_move_vector():
    """Dying must zero the movement intent, not only disable the input hook."""
    entity, health, ih = _make_with_input()
    ih.set_move_vector(0.5, 0.5)
    health.on_start()
    assert ih.move_vector == Vec2(0.5, 0.5)
    assert ih.is_enabled is True

    health.take_damage(100.0)
    assert health.is_dead
    # ``set_enabled(False)`` only gates the frame hook: the intent must be
    # cleared explicitly or a controller keeps reading the stale vector.
    assert ih.move_vector == Vec2(0.0, 0.0)
    assert ih.is_enabled is False
    entity.free()


def test_input_restored_on_stop_and_detach():
    entity, health, ih = _make_with_input()
    health.on_start()
    health.take_damage(100.0)
    assert ih.is_enabled is False

    health.on_stop()
    assert ih.is_enabled is True

    # A second death disables input again, and detaching restores it.
    entity2, health2, ih2 = _make_with_input()
    health2.on_start()
    health2.take_damage(100.0)
    assert ih2.is_enabled is False
    health2.on_detach()
    assert ih2.is_enabled is True
    entity.free()
    entity2.free()


def test_start_cycle_reapplies_death_input_disable():
    """A dead entity must not resurrect movement through a start/stop cycle."""
    entity, health, ih = _make_with_input()
    entity.start()
    entity.stop()
    ih.set_move_vector(0.5, 0.5)
    health.take_damage(100.0)
    assert health.is_dead
    assert ih.is_enabled is False
    assert ih.move_vector == Vec2(0.0, 0.0)

    # ``on_start`` re-applies the death disable: the entity is still dead, so
    # its input must stay off.
    entity.start()
    assert ih.is_enabled is False
    assert ih.move_vector == Vec2(0.0, 0.0)

    # A full stop -> start round trip must not resurrect the input either.
    entity.stop()
    entity.start()
    assert ih.is_enabled is False
    assert ih.move_vector == Vec2(0.0, 0.0)

    entity.free()
    assert entity.is_freed is True


def test_stop_cycle_restores_input_after_death_start_cycle():
    """The stop restore still fires after ``on_start`` re-applied the disable."""
    entity = _make_entity("death-start-cycle")
    ih = _RecordingInputHandler()
    entity.add_handler(ih)
    health = HealthHandler(max_health=100.0, disable_input_on_death=True)
    entity.add_handler(health)

    entity.start()
    entity.stop()
    health.take_damage(100.0)
    assert health.is_dead
    # Death disabled the input and the handler owns that disable.
    assert ih.is_enabled is False
    assert ih.enable_calls == [False]

    # ``on_start`` re-applies the disable on the dead entity.
    entity.start()
    assert ih.is_enabled is False
    assert ih.enable_calls == [False, False]

    # ``on_stop`` still restores what this handler disabled.
    entity.stop()
    assert ih.is_enabled is True
    assert ih.enable_calls == [False, False, True]

    # Starting the dead entity again disables the input once more: the
    # restore must not survive a start on a dead entity.
    entity.start()
    assert ih.is_enabled is False
    assert ih.enable_calls == [False, False, True, False]

    entity.free()
    assert entity.is_freed is True


def test_user_disabled_input_is_not_restored_on_stop():
    entity, health, ih = _make_user_disabled_input()
    health.on_start()
    assert ih.is_enabled is False

    health.on_stop()
    # The user owns this disable; the handler never disabled the input.
    assert ih.is_enabled is False
    entity.free()


def test_user_disabled_input_is_not_restored_on_detach():
    entity, health, ih = _make_user_disabled_input()
    health.on_start()
    assert ih.is_enabled is False

    health.on_detach()
    # The user owns this disable; the handler never disabled the input.
    assert ih.is_enabled is False
    entity.free()


def test_user_disabled_input_is_not_resurrected_by_stop_after_death():
    """Death must not let ``on_stop`` re-enable input the user disabled."""
    entity, health, ih = _make_user_disabled_input()
    health.on_start()
    assert ih.is_enabled is False

    health.take_damage(100.0)
    assert health.is_dead
    assert ih.is_enabled is False

    health.on_stop()
    # The handler never owned this disable, so it must not resurrect the input.
    assert ih.is_enabled is False
    entity.free()


def test_user_disabled_input_is_not_resurrected_by_detach_after_death():
    """Same contract through ``on_detach`` on an entity that never started."""
    entity, health, ih = _make_user_disabled_input()
    # The entity was never started: the handler dies without ``on_start``.
    health.take_damage(100.0)
    assert health.is_dead
    assert ih.is_enabled is False

    health.on_detach()
    # The handler never owned this disable, so it must not resurrect the input.
    assert ih.is_enabled is False
    entity.free()


def test_user_disabled_input_is_never_re_enabled_after_death():
    """The death path must never flip the input back on."""
    entity = _make_entity("user-disabled-input-recording")
    ih = _RecordingInputHandler()
    entity.add_handler(ih)
    ih.set_enabled(False)
    health = HealthHandler(max_health=100.0, disable_input_on_death=True)
    entity.add_handler(health)

    health.on_start()
    health.take_damage(100.0)
    health.on_stop()
    health.on_detach()

    assert ih.is_enabled is False
    # No ``set_enabled(True)`` transition happened at any point.
    assert True not in ih.enable_calls
    entity.free()


def test_constructor_clamps_current_health_before_on_start():
    """The constructor clamps the requested value to ``[0, max_health]``."""
    above = HealthHandler(max_health=100.0, current_health=150.0)
    assert above.current_health == 100.0
    assert above.is_alive is True
    assert above.is_dead is False

    below = HealthHandler(max_health=100.0, current_health=-10.0)
    assert below.current_health == 0.0
    assert below.is_dead is True
    assert below.is_alive is False

    # An in-range value is kept as given.
    partial = HealthHandler(max_health=100.0, current_health=40.0)
    assert partial.current_health == 40.0
    assert partial.is_alive is True


def test_on_start_reclamps_current_health_idempotently():
    """``on_start`` re-applies the clamp and keeps the constructor value."""
    above = HealthHandler(max_health=100.0, current_health=150.0)
    above.on_start()
    assert above.current_health == 100.0
    assert above.is_alive is True
    assert above.is_dead is False

    below = HealthHandler(max_health=100.0, current_health=-10.0)
    below.on_start()
    assert below.current_health == 0.0
    assert below.is_dead is True
    assert below.is_alive is False


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__]))
