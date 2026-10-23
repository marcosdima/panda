# Engine

Subsystems that are not handlers: the frame pipeline, the physics world, task registration and the core containers.

| Document | Covers |
| --- | --- |
| [update_pipeline.md](update_pipeline.md) | The per-frame phases, their sort order and what may be written in each one. |
| [physics_world.md](physics_world.md) | The Bullet world: body allocation, queries, collision masks. |
| [tasks.md](tasks.md) | Task registration, per-scene ownership, removal by handle. |
| [entities_scenes.md](entities_scenes.md) | `Entity` and `Scene` lifecycle and messaging. |

## Global singletons

`src/globals/` holds the engine-wide managers. Each one extends `Global`, which makes it a singleton that resolves the running `ShowBase` lazily through `builtins.base`. That indirection is what allows the engine to run headless: a global queried before a `ShowBase` exists returns `None` instead of raising.

| Singleton | Responsibility | Document |
| --- | --- | --- |
| `Physics` | `BulletWorld` ownership, body and ghost allocation, ray and sweep queries, debug wireframe, the physics task. | [physics_world.md](physics_world.md) |
| `GlobalLoader` | Cached model and actor loading. | [handlers/graphics.md](../handlers/graphics.md) |
| `Camera` | Position, orientation and look-at of the primary viewport camera. | [handlers/camera.md](../handlers/camera.md) |
| `GlobalClock` | Frame delta time. | [entities_scenes.md](entities_scenes.md) |
| `Tasks` | Registration of *global* tasks, outside any scene. | [tasks.md](tasks.md) |
| `GlobalLights` | Default ambient and directional lights. | [architecture.md](../architecture.md) |

## Service locator

`src/services/` registers the engine services under stable names so handlers can receive them by dependency instead of importing them.

```python
from src.services import services

physics = services.get("physics")
```

`initialize_services()` (called from `Game.__init__`) registers `physics`, `loader`, `camera`, `lights`, `tasks`, `clock` and `events`. `services.get(name)` raises `KeyError` for an unknown name unless a `default` is given.

The `events` key holds the shared [`GlobalEventBus`](../utils/global_event_bus.md) instance (`from src.utils import bus`). Unlike the other entries, which register classes, `events` registers an already-built instance; this is intentional because the bus is a passive registry with no ShowBase dependency.

Source: `src/globals/`, `src/services/`, `src/game.py`
Tests: `tests/terminal/game_update_test.py`, `tests/terminal/post_update_test.py`, `tests/terminal/scene_tasks_test.py`, `tests/terminal/global_event_bus_test.py`
