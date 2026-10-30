from __future__ import annotations

import builtins
from abc import ABC
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from panda3d.core import NodePath

if TYPE_CHECKING:
    from direct.task.Task import AsyncTask, TaskManager

    from src.entities.entity import Entity


class Scene(ABC):
    """Base class for all scenes managing active entities, root NodePath, and physics resources."""

    _count: int = 0

    def __init__(self) -> None:
        self.id: int = Scene._count
        Scene._count += 1
        self.entities: dict[int, Entity] = {}
        self._started: bool = False
        self._owned_tasks: dict[str, AsyncTask] = {}
        self.root_np: NodePath = NodePath(f"scene_{self.id}")
        self._owned_bodies: list[Any] = []
        self._owned_ghosts: list[Any] = []
        self.physics_debug: bool = False

    @property
    def is_started(self) -> bool:
        """True while the scene is active (between on_start and on_stop)."""
        return self._started

    def register_body(self, body: Any) -> Any:
        """Register a scene-owned rigid body (node or name) to be removed on scene stop."""
        self._owned_bodies.append(body)
        return body

    def register_ghost(self, ghost: Any) -> Any:
        """Register a scene-owned ghost node (node or name) to be removed on scene stop."""
        self._owned_ghosts.append(ghost)
        return ghost

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

    def add_task(
        self, name: str, func: Callable[..., int], sort: int = 0, pauseable: bool = True
    ) -> None:
        """Register a task owned by this scene, replacing any task already using that name."""
        task_mgr = self._get_task_manager()
        if task_mgr is None:
            return
        self.remove_task(name)

        if pauseable:

            def _wrapped(task: Any) -> int:
                base = getattr(builtins, "base", None)
                if getattr(base, "paused", False):
                    return getattr(task, "cont", 1)
                return func(task)

            self._owned_tasks[name] = task_mgr.add(_wrapped, name, sort=sort)
        else:
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
        """Called when the scene starts. Attaches scene root_np and starts all active entities."""
        self._started = True
        if self.root_np is None or self.root_np.isEmpty():
            self.root_np = NodePath(f"scene_{self.id}")
        base = getattr(builtins, "base", None)
        render = getattr(base, "render", None) if base is not None else None
        if render is not None and self.root_np.getParent() != render:
            self.root_np.reparentTo(render)
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
        """Called when the scene stops. Cleanly frees all owned tasks, entities, bodies, and root_np."""
        self._started = False
        for name in list(self._owned_tasks.keys()):
            self.remove_task(name)
        for entity in list(self.entities.values()):
            entity.free()
        self.entities.clear()

        if self._owned_bodies or self._owned_ghosts:
            from src.globals.physics import Physics

            for body in self._owned_bodies:
                Physics.remove_body(body)
            self._owned_bodies.clear()
            for ghost in self._owned_ghosts:
                Physics.remove_ghost(ghost)
            self._owned_ghosts.clear()

        if getattr(self, "physics_debug", False):
            try:
                import logging

                from src.globals.physics import Physics

                logging.getLogger(__name__).info(
                    "Physics debug dump: %s", Physics.debug_dump()
                )
            except Exception:  # noqa: BLE001, S110
                pass

        if self.root_np is not None and not self.root_np.isEmpty():
            for child in self.root_np.getChildren():
                child.removeNode()
            self.root_np.removeNode()
        self.root_np = NodePath(f"scene_{self.id}")

    def _get_task_manager(self) -> TaskManager | None:
        """Return the global task manager, or None when no base is available."""
        base = getattr(builtins, "base", None)
        if base is None:
            return None
        return getattr(base, "taskMgr", None)
