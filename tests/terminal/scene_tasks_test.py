"""Headless tests for Scene task ownership, isolation and automatic cleanup."""

from __future__ import annotations

import builtins
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from direct.task.Task import TaskManager

from src.scenes import Scene

try:
    from ..__test import Test
except ImportError:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from tests.__test import Test


class FakeBase:
    """Minimal stand-in for ShowBase exposing only a task manager."""

    def __init__(self, task_mgr: TaskManager) -> None:
        self.taskMgr = task_mgr


class ProbeScene(Scene):
    """Scene counting how many times its own task has been executed."""

    def __init__(self) -> None:
        super().__init__()
        self.ticks: int = 0

    def tick(self, task: Any) -> int:
        """Count one execution of the task owned by this scene."""
        self.ticks += 1
        return task.cont


@contextmanager
def task_manager_scope() -> Iterator[TaskManager]:
    """Install a private task manager as the global base for the duration of the scope."""
    manager = TaskManager()
    original = getattr(builtins, "base", None)
    builtins.base = FakeBase(manager)
    try:
        yield manager
    finally:
        if original is not None:
            builtins.base = original
        else:
            delattr(builtins, "base")


def check_task_removed_on_stop(task_mgr: TaskManager) -> None:
    """A task registered by a scene must be gone from the task manager once the scene stops."""
    scene = ProbeScene()
    scene.add_task("scene_task", scene.tick)
    assert task_mgr.hasTaskNamed("scene_task")
    task_mgr.step()
    assert scene.ticks == 1

    scene.on_stop()

    assert not task_mgr.hasTaskNamed("scene_task")
    assert task_mgr.getTasksNamed("scene_task") == []
    task_mgr.step()
    assert scene.ticks == 1


def check_same_name_scenes_do_not_interfere(task_mgr: TaskManager) -> None:
    """Two scenes owning tasks with the same name must stay independent from each other."""
    first = ProbeScene()
    second = ProbeScene()
    first.add_task("shared_task", first.tick)
    second.add_task("shared_task", second.tick)
    assert len(task_mgr.getTasksNamed("shared_task")) == 2

    task_mgr.step()
    assert first.ticks == 1 and second.ticks == 1

    first.on_stop()

    assert len(task_mgr.getTasksNamed("shared_task")) == 1
    task_mgr.step()
    assert first.ticks == 1
    assert second.ticks == 2


def check_remove_task_only_affects_owning_scene(task_mgr: TaskManager) -> None:
    """Scene.remove_task must remove the task of that scene only."""
    scene = ProbeScene()
    other = ProbeScene()
    scene.add_task("owned_task", scene.tick)
    other.add_task("owned_task", other.tick)
    assert len(task_mgr.getTasksNamed("owned_task")) == 2

    scene.remove_task("owned_task")

    assert len(task_mgr.getTasksNamed("owned_task")) == 1
    task_mgr.step()
    assert scene.ticks == 0
    assert other.ticks == 1


def check_reused_task_name_leaves_no_orphan(task_mgr: TaskManager) -> None:
    """Registering the same name twice must keep a single active task."""
    scene = ProbeScene()
    scene.add_task("reused_task", scene.tick)
    first_handle = scene._owned_tasks["reused_task"]

    scene.add_task("reused_task", scene.tick)
    second_handle = scene._owned_tasks["reused_task"]

    assert first_handle is not second_handle
    assert not first_handle.isAlive()
    assert len(task_mgr.getTasksNamed("reused_task")) == 1
    task_mgr.step()
    assert scene.ticks == 1


def test_scene_task_is_removed_on_stop() -> None:
    """Scene tasks are removed from the task manager when the scene stops."""
    with task_manager_scope() as task_mgr:
        check_task_removed_on_stop(task_mgr)


def test_scenes_with_the_same_task_name_do_not_interfere() -> None:
    """Stopping one scene keeps the task of another scene with the same name alive."""
    with task_manager_scope() as task_mgr:
        check_same_name_scenes_do_not_interfere(task_mgr)


def test_remove_task_only_removes_the_scene_own_task() -> None:
    """Scene.remove_task removes only the task owned by that scene."""
    with task_manager_scope() as task_mgr:
        check_remove_task_only_affects_owning_scene(task_mgr)


def test_reusing_a_task_name_leaves_no_orphan() -> None:
    """Registering an already used task name leaves exactly one active task."""
    with task_manager_scope() as task_mgr:
        check_reused_task_name_leaves_no_orphan(task_mgr)


class TestSceneTasks(Test):
    """In-engine suite running the scene task checks against a private task manager."""

    def on_start(self) -> None:
        """Run every scene task check inside an isolated task manager."""
        super().on_start()
        self.print_title("Scene Tasks Suite started.", color="cyan")
        with task_manager_scope() as task_mgr:
            check_task_removed_on_stop(task_mgr)
            self.p("Scene tasks are removed when the scene stops.", color="green")
            check_same_name_scenes_do_not_interfere(task_mgr)
            self.p("Scenes with the same task name stay independent.", color="green")
            check_remove_task_only_affects_owning_scene(task_mgr)
            self.p("Scene.remove_task removes only its own task.", color="green")
            check_reused_task_name_leaves_no_orphan(task_mgr)
            self.p("Reusing a task name leaves no orphan task.", color="green")
        self.space_line()
        self.print_subtitle("Scene Tasks Suite completed.", color="green")

    def on_stop(self) -> None:
        """Report the suite shutdown."""
        self.print_subtitle("Scene Tasks Suite stopped.")


if __name__ == "__main__":
    import sys

    import pytest

    sys.exit(pytest.main([__file__]))
