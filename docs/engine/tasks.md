# Tasks

Panda3D tasks are the engine's unit of scheduled work. The engine exposes two owners for them: the global `Tasks` singleton and the scene-local `Scene.add_task`.

## Global tasks — `Tasks`

`src/globals/tasks.py` manages the tasks that belong to the engine itself.

| Method | Behaviour |
| --- | --- |
| `Tasks.add_task(name, task)` | Registers a task under `name`, replacing any task already using that name. |
| `Tasks.remove_task(name)` | Removes the task registered under `name`, if any. |
| `Tasks.remove_task_handle(handle)` | Removes one task by handle and forgets its name binding. |
| `Tasks.get_task(name)` | Returns the handle registered under `name`. |

### The naming gotcha

**Task names are not unique in Panda3D.** `taskMgr.remove(name)` removes *every* task registered under that name, while `taskMgr.remove(handle)` removes only that one task.

`Tasks` therefore stores the handle of each registered name and always removes by handle. A global task is never killed by accident because another task happens to share its name.

**Rule:** never call `taskMgr.remove(name)` directly. Use `Tasks.remove_task(name)` or `Tasks.remove_task_handle(handle)`.

`Tasks.add_task` replaces an existing name on purpose: registering the same name twice does not leave a duplicate running.

## Scene tasks — `Scene.add_task`

`src/scenes/__scene.py` manages the tasks that belong to one scene.

| Method | Behaviour |
| --- | --- |
| `scene.add_task(name, func, sort=0)` | Registers a task owned by the scene, replacing any task already using that name. |
| `scene.remove_task(name)` | Removes the task owned by the scene with that name. |

A scene task is **owned by the scene**: when the scene stops, every task it owns is removed automatically, before its entities are freed. A task that must outlive its scene has to be a global task.

The scene also removes its tasks by handle, for the same reason as `Tasks`: names are not unique in Panda3D.

## Which one to use

| | Global task (`Tasks`) | Scene task (`Scene.add_task`) |
| --- | --- | --- |
| Lifetime | Until it is removed explicitly | Until the scene stops |
| Survives a scene change | Yes | No |
| Typical use | Engine systems: the physics step | Spawning, ambient logic, per-scene loops |

**Rule:** a task that belongs to a scene is registered through that scene. A task that belongs to the engine is registered through `Tasks`. Registering a scene task globally leaks it when the scene stops.

## Sort

`Scene.add_task` takes a `sort` argument; `Tasks.add_task` does not, so a global task runs at the default sort of `0`. The sorts of the engine tasks define the frame order, described in [update_pipeline.md](update_pipeline.md).

## The clock

A task receives the task object as its single argument and returns `task.cont` to be scheduled again, or `task.done` to stop. Use `GlobalClock.get_dt()` for the delta time.

```python
def _update_world(self, task):
    dt = GlobalClock.get_dt()
    Physics.get_world().doPhysics(dt)
    return task.cont
```

Source: `src/globals/tasks.py`, `src/scenes/__scene.py`
Tests: `tests/terminal/scene_tasks_test.py`
