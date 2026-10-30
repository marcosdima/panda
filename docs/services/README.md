# Services (`src/services/`)

The Service Locator lets handlers obtain engine services by name instead of importing `src.globals` singletons directly. That indirection keeps handlers testable: a test can register a mock service under the same name and the handler never knows the difference.

## The locator

`src/services/__init__.py` exports a module-level singleton, `services`, backed by `_ServiceLocator`.

| Method | Behaviour |
|--------|-----------|
| `services.register(name, service)` | Registers *service* under *name*, overwriting any previous entry. |
| `services.has(name)` / `name in services` | Whether *name* is registered. |
| `services.get(name, typ=None, default=_SENTINEL)` | Returns the registered service. Raises `KeyError` when unknown and no `default` is given. |
| `services.clear()` | Removes every entry. Used for test isolation. |

```python
from src.services import services

services.register("physics", physics_world)
physics = services.get("physics")          # KeyError if missing
physics = services.get("physics", default=None)
```

## Registration at startup

`src/services/initializers.py` defines `initialize_services()`, called from `Game.__init__`. It registers `physics`, `loader`, `camera`, `lights`, `tasks`, `clock` and `events`.

| Key | What it holds |
|-----|---------------|
| `physics` | The `Physics` singleton (`src/globals/physics.py`) |
| `loader` | The `GlobalLoader` singleton (`src/globals/loader.py`) |
| `camera` | The `Camera` global (`src/globals/camera.py`) |
| `lights` | The `GlobalLights` singleton (`src/globals/lights.py`) |
| `tasks` | The `Tasks` singleton (`src/globals/tasks.py`) |
| `clock` | The `GlobalClock` singleton (`src/globals/clock.py`) |
| `events` | The shared `GlobalEventBus` instance (`bus` from `src.utils`) |

Unlike the other entries, which register classes resolved lazily through `builtins.base`, `events` registers an already-built instance. That is intentional: the bus is a passive registry with no ShowBase dependency.

## When to use it

Use the service locator when a handler needs an engine-wide resource and you want to keep the dependency injectable:

- Prefer `services.get("physics")` over `from src.globals.physics import Physics` inside handler code.
- In tests, register a stub under the same key before constructing the handler.

Do not use it for per-entity collaboration — two handlers on the same entity should still talk through `entity.get_handler(...)`. The locator is for engine-wide, owner-less resources.

Source: `src/services/__init__.py`, `src/services/initializers.py`, `src/game.py`
Tests: `tests/terminal/service_locator_test.py`