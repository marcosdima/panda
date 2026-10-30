from __future__ import annotations

from typing import Protocol, runtime_checkable

from panda3d.core import Vec2, Vec3


@runtime_checkable
class IntentSource(Protocol):
    """Capability for handlers that write movement intent."""

    move_vector: Vec2

    def set_move_vector(self, x: float, y: float) -> None: ...


@runtime_checkable
class Mover(Protocol):
    """Capability for handlers that own entity movement."""

    def on_update(self, dt: float) -> None: ...


@runtime_checkable
class PhysicsBody(Protocol):
    """Capability for handlers exposing a physics body."""

    @property
    def body_np(self) -> object: ...


@runtime_checkable
class AnimationPlayer(Protocol):
    """Capability for handlers that play animations."""

    def play_animation(self, name: str) -> None: ...


@runtime_checkable
class CameraRig(Protocol):
    """Capability for handlers that own a camera."""

    pass
