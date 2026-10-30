"""Tests for runtime capabilities (src/handlers/capabilities.py).

Verifies the Protocol-based capability system: isinstance checks, provides
metadata, and get_capability lookup on entities.
"""

from typing import Any

import pytest

from src.entities.entity import Entity
from src.handlers.base import Handler
from src.handlers.capabilities import (
    AnimationPlayer,
    IntentSource,
    Mover,
    PhysicsBody,
)


class FakeMover(Handler):
    """Handler exposing the Mover capability via inheritance."""

    provides = (Mover,)

    def on_update(self, dt: float) -> None:
        return None


class FakePhysicsBody(Handler):
    """Handler exposing PhysicsBody via a body_np property."""

    provides = (PhysicsBody,)

    @property
    def body_np(self) -> Any:
        return object()


class FakeAnimationPlayer(Handler):
    """Handler exposing AnimationPlayer via play_animation method."""

    provides = (AnimationPlayer,)

    def play_animation(self, name: str) -> None:
        return None


class FakeIntentSource(Handler):
    """Handler exposing IntentSource via move_vector attribute."""

    provides = (IntentSource,)

    move_vector: Any = (0.0, 0.0)

    def set_move_vector(self, x: float, y: float) -> None:
        self.move_vector = (x, y)


def test_protocol_runtime_checkable() -> None:
    """All capabilities are runtime_checkable Protocols."""
    assert IntentSource.__instancecheck__(FakeIntentSource()) is True
    assert Mover.__instancecheck__(FakeMover()) is True
    assert PhysicsBody.__instancecheck__(FakePhysicsBody()) is True
    assert AnimationPlayer.__instancecheck__(FakeAnimationPlayer()) is True


def test_entity_get_capability_by_protocol() -> None:
    """get_capability finds handlers by Protocol isinstance."""
    Entity.reset_ids()
    entity = Entity("cap_test")
    entity.add_handler(FakeMover())

    mover = entity.get_capability(Mover)
    assert mover is not None
    assert isinstance(mover, FakeMover)


def test_entity_get_capability_by_provides() -> None:
    """get_capability finds handlers listed in provides metadata."""
    Entity.reset_ids()
    entity = Entity("cap_test")
    entity.add_handler(FakePhysicsBody())

    body = entity.get_capability(PhysicsBody)
    assert body is not None
    assert isinstance(body, FakePhysicsBody)


def test_entity_get_capability_returns_none_when_missing() -> None:
    """get_capability returns None when no handler exposes the capability."""
    Entity.reset_ids()
    entity = Entity("cap_test")
    # No handlers at all → nothing can match any capability.

    assert entity.get_capability(Mover) is None
    assert entity.get_capability(PhysicsBody) is None
    assert entity.get_capability(AnimationPlayer) is None


def test_get_capability_matches_provides_metadata() -> None:
    """get_capability finds handlers declared in provides even without structural match."""

    class DeclaresPhysicsBody(Handler):
        provides = (PhysicsBody,)

    Entity.reset_ids()
    entity = Entity("provides_test")
    entity.add_handler(DeclaresPhysicsBody())

    # isinstance(DeclaresPhysicsBody(), PhysicsBody) is False (no body_np property),
    # but provides metadata makes get_capability find it.
    assert entity.get_handler(PhysicsBody) is None
    assert entity.get_capability(PhysicsBody) is not None


def test_protocol_structural_subtyping_without_provides() -> None:
    """A handler with the right shape matches a Protocol even without provides."""

    class DuckMover(Handler):
        def on_update(self, dt: float) -> None:
            return None

    Entity.reset_ids()
    entity = Entity("duck")
    entity.add_handler(DuckMover())

    # Structural subtyping: DuckMover has on_update, so it matches Mover
    assert entity.get_capability(Mover) is not None


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__]))
