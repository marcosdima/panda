from __future__ import annotations

from abc import ABC
from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from src.entities.entity import Entity


from src.utils.handler_phase import HandlerPhase


class Handler(ABC):
    """Base class for all modular entity handlers.

    Lifecycle hooks are called in order: ``on_attach`` -> ``on_start`` -> ``on_update``
    (per frame) -> ``on_post_update`` (after physics step) -> ``on_stop`` -> ``on_detach``.

    Handlers may declare lightweight metadata to make composition safer:

    - ``phase``: execution phase within a frame.
    - ``requires``: handler types that must already be attached.
    - ``optional_requires``: handler types used when present.
    - ``provides``: capability types this handler exposes.
    """

    phase: ClassVar[HandlerPhase] = HandlerPhase.NORMAL
    requires: ClassVar[Sequence[type[Handler]]] = ()
    optional_requires: ClassVar[Sequence[type[Handler]]] = ()
    provides: ClassVar[Sequence[type]] = ()

    def __init__(self) -> None:
        self.entity: Entity | None = None
        self._enabled: bool = True

    @property
    def is_enabled(self) -> bool:
        """Return whether this handler is currently enabled."""
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable this handler."""
        self._enabled = enabled

    def on_attach(self, entity: Entity) -> None:
        """Called when this handler is added to an entity."""
        self.entity = entity

    def on_detach(self) -> None:
        """Called when this handler is removed from an entity or the entity is freed."""
        self.entity = None

    def on_start(self) -> None:
        """Called when the scene starts or the entity is activated."""

    def on_update(self, dt: float) -> None:
        """Frame update hook called every tick if the handler is enabled."""

    def on_post_update(self, dt: float) -> None:
        """Called after the physics step, for handlers that need the final frame positions."""

    def on_stop(self) -> None:
        """Called when the scene stops or the entity is deactivated."""

    def provides_capabilities(self) -> Sequence[type]:
        """Return the capabilities exposed by this handler."""
        return tuple(self.provides)

    def missing_requirements(self, entity: Entity) -> list[type]:
        """Return required handler types not currently attached to *entity*."""
        missing: list[type] = []
        for required in self.requires:
            if entity.get_handler(required) is None:
                missing.append(required)
        return missing
