from __future__ import annotations

import builtins
from abc import ABC
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from direct.task.Task import AsyncTask, TaskManager

    from src.entities.entity import Entity


class Scene(ABC):
    """Base class for all scenes managing active entities and their lifecycles."""

    _count: int = 0

    def __init__(self) -> None:
        self.id: int = Scene._count
        Scene._count += 1
        self.entities: dict[int, Entity] = {}
        self._started: bool = False
        self._owned_tasks: dict[str, AsyncTask] = {}

    @property
    def is_started(self) -> bool:
        """True while the scene is active (between on_start and on_stop)."""
        return self._started

    def add_entity(self, entity: Entity) -> Entity:
        """Add an entity to the scene and start it if the scene is already active."""
        self.entities[entity.id] = entity
        if self._started:
            entity.on_start()
        return entity

    def remove_entity(self, entity: Entity | int) -> None:
        """Remove an entity from the scene by reference or ID."""
        entity_id = entity.id if hasattr(entity, "id") else entity
        target = self.entities.pop(entity_id, None)
        if target is not None and self._started:
            target.on_stop()

    def get_entity(self, entity_id: int) -> Entity | None:
        """Retrieve an entity by its unique ID, or None if not found."""
        return self.entities.get(entity_id)

    def add_task(self, name: str, func: Callable[..., int], sort: int = 0) -> None:
        """Register a task owned by this scene, replacing any task already using that name."""
        task_mgr = self._get_task_manager()
        if task_mgr is None:
            return
        self.remove_task(name)
        self._owned_tasks[name] = task_mgr.add(func, name, sort=sort)

    def remove_task(self, name: str) -> None:
        """Remove the task owned by this scene with the given name, if any."""
        handle = self._owned_tasks.pop(name, None)
        if handle is None:
            return
        task_mgr = self._get_task_manager()
        if task_mgr is None:
            return
        task_mgr.remove(handle)

    def on_start(self) -> None:
        """Called when the scene starts. Starts all active entities."""
        self._started = True
        for entity in list(self.entities.values()):
            entity.on_start()

    def on_update(self, dt: float) -> None:
        """Update all active entities in the scene."""
        for entity in list(self.entities.values()):
            entity.on_update(dt)

    def on_post_update(self, dt: float) -> None:
        """Post-physics update for all active entities in the scene."""
        if not self._started:
            return
        for entity in list(self.entities.values()):
            entity.on_post_update(dt)

    def on_stop(self) -> None:
        """Called when the scene stops. Cleanly frees all owned tasks and entities."""
        self._started = False
        for name in list(self._owned_tasks.keys()):
            self.remove_task(name)
        for entity in list(self.entities.values()):
            entity.free()
        self.entities.clear()

    def _get_task_manager(self) -> TaskManager | None:
        """Return the global task manager, or None when no base is available."""
        base = getattr(builtins, "base", None)
        if base is None:
            return None
        return getattr(base, "taskMgr", None)
