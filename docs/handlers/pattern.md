# Handler Pattern

A `Handler` is a modular component responsible for a single piece of behaviour or system integration (input handling, character controller physics, camera tracking, animation playback, AI decisions).

Instead of deriving complex entity classes via multiple inheritance, entities are composed dynamically:

```python
player = Entity("Player")
player.add_handler(WASDInputHandler())
player.add_handler(CharacterControllerHandler(mass=75.0, height=1.8))
player.add_handler(ActorAnimationHandler(model_path="X Bot.glb"))
player.add_handler(ThirdPersonCameraHandler())
```

The available handler areas are listed in [README.md](README.md).

## Base interface

All handlers inherit from `Handler` (`src/handlers/base.py`):

```python
class Handler(ABC):
    def __init__(self) -> None:
        self.entity: "Entity | None" = None
        self._enabled: bool = True

    @property
    def is_enabled(self) -> bool: ...
    def set_enabled(self, enabled: bool) -> None: ...

    def on_attach(self, entity: "Entity") -> None: ...
    def on_detach(self) -> None: ...
    def on_start(self) -> None: ...
    def on_update(self, dt: float) -> None: ...
    def on_post_update(self, dt: float) -> None: ...
    def on_stop(self) -> None: ...
```

### Lifecycle

| Hook | When it runs | Typical use |
| --- | --- | --- |
| `on_attach(entity)` | The handler is added to an entity. | Store the entity, create nodes, register listeners. |
| `on_start()` | The entity or the scene becomes active. | Acquire physics bodies, load assets, capture the pointer. |
| `on_update(dt)` | Every frame, before the physics step. | Read input, write intent, decide. |
| `on_post_update(dt)` | Every frame, after the physics step. | Read final positions and write transforms that depend on them. |
| `on_stop()` | The scene stops or the entity is deactivated. | Release bodies, restore camera settings, remove nodes. |
| `on_detach()` | The handler is removed or the entity is freed. | Drop the entity reference. |

Only enabled handlers receive the frame hooks. `set_enabled(False)` pauses a handler without removing it.

### Choosing a phase

`on_update` and `on_post_update` are not interchangeable:

- **Intent and decisions** belong in `on_update`: they must be visible to the physics step that follows.
- **Transforms that depend on the result of the simulation** belong in `on_post_update`: writing them earlier would show the previous frame's position.

The full ordering and the rules that go with it are in [../engine/update_pipeline.md](../engine/update_pipeline.md).

## Composition rules

- **Handlers never move the entity directly** unless they own the movement. The character controller owns movement; cameras and graphics handlers only read.
- **Handlers talk to each other through the entity**, using `entity.get_handler(HandlerClass)`:

```python
input_handler = self.entity.get_handler(InputHandler)
if input_handler and input_handler.is_action_pressed("jump"):
    self.jump()
```

- **Handlers do not import each other's state.** A handler reads another handler's public API, never its private attributes.
- **A handler owns everything it creates**: nodes are removed with `removeNode()`, Bullet bodies are removed from the world, tasks are removed from the task manager, pointer capture is restored.
- **One concern per handler.** If a class needs a second unrelated behaviour, it is two handlers.

## Checklist for a new handler

1. Subclass `Handler` and implement only the hooks you need.
2. Keep the entity reference from `on_attach`; clear it in `on_detach`.
3. Do all cleanup in `on_stop` and `on_detach` so a scene can be restarted without leaks.
4. Write intent in `on_update` and transforms in `on_post_update`.
5. Use `entity.get_handler()` to read collaborators, never `entity.get_handlers()[0]`.
6. Add a headless test under `tests/terminal/` and, when the behaviour is visual, a sandbox under `tests/panda/`.
7. Document it in the document of its area, ending with `Source:` and `Tests:` lines.

Source: `src/handlers/base.py`, `src/entities/entity.py`, `src/scenes/__scene.py`
Tests: `tests/terminal/entities.py`, `tests/terminal/events.py`
