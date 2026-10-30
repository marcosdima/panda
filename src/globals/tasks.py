from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from .__global import Global

if TYPE_CHECKING:
    from typing import ClassVar

    from direct.task.Task import AsyncTask, TaskManager


class Tasks(Global):
    """A singleton class to manage global tasks.

    Panda3D gotcha: task names are not unique. `taskMgr.remove(name)` removes
    every task registered under that name, while `taskMgr.remove(handle)` removes
    only the given task. Handles are therefore stored per name and are always
    removed by handle, so unrelated tasks are never killed by accident.
    """

    _tasks: ClassVar[dict[str, AsyncTask]] = {}

    @classmethod
    def add_task(cls, name: str, task: Callable) -> AsyncTask | None:
        """Register a global task by name, replacing any task already using that name."""
        if not hasattr(cls, "_instance"):
            cls()
        cls.remove_task(name)
        task_mgr = cls._get_task_manager()
        if task_mgr is None:
            return None
        handle = task_mgr.add(task, name)
        cls._tasks[name] = handle
        return handle

    @classmethod
    def remove_task(cls, name: str) -> None:
        """Remove the global task registered under the given name, if any."""
        handle = cls._tasks.pop(name, None)
        if handle is not None:
            cls.remove_task_handle(handle)

    @classmethod
    def remove_task_handle(cls, handle: AsyncTask) -> None:
        """Remove a single task by its handle, forgetting it when registered by name."""
        if handle is None:
            return
        for task_name, registered in list(cls._tasks.items()):
            if registered is handle:
                del cls._tasks[task_name]
        task_mgr = cls._get_task_manager()
        if task_mgr is None:
            return
        task_mgr.remove(handle)

    @classmethod
    def _get_task_manager(cls) -> TaskManager | None:
        """Return the global task manager, or None when no base is available."""
        if not hasattr(cls, "_instance"):
            cls()
        base = cls._instance.base
        if base is None:
            return None
        return getattr(base, "taskMgr", None)
