from abc import ABC
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.entities.entity import Entity


class Handler(ABC):
    """Base class for all modular entity handlers.

    Lifecycle hooks are called in order: ``on_attach`` -> ``on_start`` -> ``on_update``
    (per frame) -> ``on_post_update`` (after physics step) -> ``on_stop`` -> ``on_detach``.
    """

    def __init__(self) -> None:
        self.entity: "Entity | None" = None
        self._enabled: bool = True

    @property
    def is_enabled(self) -> bool:
        """Return whether this handler is currently enabled."""
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable this handler."""
        self._enabled = enabled

    def on_attach(self, entity: "Entity") -> None:
        """Called when this handler is added to an entity."""
        self.entity = entity

    def on_detach(self) -> None:
        """Called when this handler is removed from an entity or the entity is freed."""
        self.entity = None

    def on_start(self) -> None:
        """Called when the scene starts or the entity is activated."""
        pass

    def on_update(self, dt: float) -> None:
        """Frame update hook called every tick if the handler is enabled."""
        pass

    def on_post_update(self, dt: float) -> None:
        """Called after the physics step, for handlers that need the final frame positions."""
        pass

    def on_stop(self) -> None:
        """Called when the scene stops or the entity is deactivated."""
        pass
