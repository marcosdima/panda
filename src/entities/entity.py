from __future__ import annotations

from typing import TYPE_CHECKING
from panda3d.core import NodePath

from src.utils.event import Event

if TYPE_CHECKING:
    from src.handlers.base import Handler


class Entity:
    """Lightweight composition-based entity container.

    An Entity manages unique identity, a Panda3D scene graph node,
    and a collection of modular behavioral Handlers.
    """

    _free_ids: list[int] = []
    _next_id: int = 0

    @classmethod
    def _allocate_id(cls) -> int:
        """Allocate a unique entity ID, reusing recycled IDs in LIFO order."""
        if cls._free_ids:
            return cls._free_ids.pop()
        allocated = cls._next_id
        cls._next_id += 1
        return allocated

    @classmethod
    def _recycle_id(cls, entity_id: int) -> None:
        """Recycle an entity ID for future reuse."""
        if entity_id not in cls._free_ids:
            cls._free_ids.append(entity_id)

    @classmethod
    def reset_ids(cls) -> None:
        """Reset ID allocator pool state. Primarily used for testing isolation."""
        cls._free_ids.clear()
        cls._next_id = 0

    def __init__(self, name: str | None = None, node: NodePath | None = None) -> None:
        self.id: int = Entity._allocate_id()
        self.name: str = name if name is not None else f"Entity-{self.id}"
        self.node: NodePath = node if node is not None else NodePath(self.name)
        self.node.setPythonTag("entity", self)

        self._handlers: list[Handler] = []
        self._started: bool = False
        self._freed: bool = False
        self.on_free: Event = Event()

    @property
    def is_started(self) -> bool:
        """Return True if the entity is currently started."""
        return self._started

    @property
    def is_freed(self) -> bool:
        """Return True if the entity has been freed."""
        return self._freed

    def get_name(self) -> str:
        """Return entity name for backwards compatibility."""
        return self.name

    def add_handler[H: Handler](self, handler: H) -> H:
        """Attach a handler to this entity and return it."""
        if handler not in self._handlers:
            self._handlers.append(handler)
            handler.on_attach(self)
            if self._started:
                handler.on_start()
        return handler

    def get_handler[T](self, handler_type: type[T]) -> T | None:
        """Return the first attached handler matching handler_type, or None."""
        for handler in self._handlers:
            if isinstance(handler, handler_type):
                return handler
        return None

    def get_handlers[T](self, handler_type: type[T]) -> list[T]:
        """Return all attached handlers matching handler_type."""
        return [handler for handler in self._handlers if isinstance(handler, handler_type)]

    def remove_handler(self, handler: Handler) -> bool:
        """Remove a handler from this entity. Return True if removed, False otherwise."""
        if handler in self._handlers:
            if self._started:
                handler.on_stop()
            self._handlers.remove(handler)
            handler.on_detach()
            return True
        return False

    def has_handler(self, handler_type: type) -> bool:
        """Check whether a handler of the specified type is attached."""
        return any(isinstance(handler, handler_type) for handler in self._handlers)

    def on_start(self) -> None:
        """Start the entity and notify all attached handlers."""
        if self._started or self._freed:
            return
        self._started = True
        for handler in list(self._handlers):
            handler.on_start()

    def start(self) -> None:
        """Alias for on_start."""
        self.on_start()

    def on_update(self, dt: float) -> None:
        """Update all enabled handlers attached to this entity."""
        if not self._started or self._freed:
            return
        for handler in list(self._handlers):
            if handler.is_enabled:
                handler.on_update(dt)

    def update(self, dt: float) -> None:
        """Alias for on_update."""
        self.on_update(dt)

    def on_stop(self) -> None:
        """Stop the entity and notify all attached handlers."""
        if not self._started:
            return
        self._started = False
        for handler in list(self._handlers):
            handler.on_stop()

    def stop(self) -> None:
        """Alias for on_stop."""
        self.on_stop()

    def free(self) -> None:
        """Detach all handlers, remove scene node cleanly, and recycle entity ID."""
        if self._freed:
            return
        self._freed = True

        if self._started:
            self.on_stop()

        for handler in list(self._handlers):
            self.remove_handler(handler)

        self.on_free()

        if self.node is not None and not self.node.isEmpty():
            self.node.clearPythonTag("entity")
            self.node.removeNode()

        Entity._recycle_id(self.id)

    def __repr__(self) -> str:
        return f"<Entity id={self.id} name='{self.name}'>"
