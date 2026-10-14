from abc import ABC
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.entities.entity import Entity


class Scene(ABC):
    """Base class for all scenes managing active entities and their lifecycles."""

    _count: int = 0

    def __init__(self) -> None:
        self.id: int = Scene._count
        Scene._count += 1
        self.entities: dict[int, Entity] = {}
        self._started: bool = False

    def add_entity(self, entity: "Entity") -> "Entity":
        """Add an entity to the scene and start it if the scene is already active."""
        self.entities[entity.id] = entity
        if self._started:
            entity.on_start()
        return entity

    def remove_entity(self, entity: "Entity | int") -> None:
        """Remove an entity from the scene by reference or ID."""
        entity_id = entity.id if hasattr(entity, "id") else entity
        target = self.entities.pop(entity_id, None)
        if target is not None and self._started:
            target.on_stop()

    def get_entity(self, entity_id: int) -> "Entity | None":
        """Retrieve an entity by its unique ID, or None if not found."""
        return self.entities.get(entity_id)

    def on_start(self) -> None:
        """Called when the scene starts. Starts all active entities."""
        self._started = True
        for entity in list(self.entities.values()):
            entity.on_start()

    def on_update(self, dt: float) -> None:
        """Update all active entities in the scene."""
        for entity in list(self.entities.values()):
            entity.on_update(dt)

    def on_stop(self) -> None:
        """Called when the scene stops. Cleanly frees all entities."""
        self._started = False
        for entity in list(self.entities.values()):
            entity.free()
        self.entities.clear()