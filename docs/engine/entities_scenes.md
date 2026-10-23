# Entities and Scenes

An entity is a bag of handlers with a node. A scene owns entities and the tasks that belong to them.

## `Entity`

`src/entities/entity.py`.

| Member | Behaviour |
| --- | --- |
| `Entity(name=None, node=None)` | Creates an entity with a unique id and a node. The node defaults to a `NodePath` named after the entity. |
| `entity.id` | Unique integer id, allocated from a recycled pool. |
| `entity.name` | The given name, or `Entity-<id>`. |
| `entity.node` | The entity's own `NodePath`. |
| `entity.on_free` | Event fired when the entity is freed. |
| `Entity.reset_ids()` | Resets the id pool. Useful to make a test deterministic. |

### Handlers

| Method | Behaviour |
| --- | --- |
| `entity.add_handler(handler)` | Adds a handler and attaches it. If the entity is already started, the handler is started too. |
| `entity.get_handler(type)` | Returns the first handler of that type, or `None`. |
| `entity.get_handlers(type)` | Returns every handler of that type. |
| `entity.has_handler(type)` | Whether a handler of that type is present. |
| `entity.remove_handler(handler)` | Detaches and removes a handler. Returns whether it was there. |

**Order matters.** Handlers are updated in the order they were added, and a handler that reads another one sees the state the previous one left. The AI handler must therefore be attached **before** the movement handler, and the camera handler before the movement handler that reads the camera's forward vector.

### Lifecycle

```
on_attach → on_start → on_update → on_post_update → on_stop → on_detach
```

- `entity.start()` / `entity.on_start()` starts the entity and its handlers.
- `entity.update(dt)` and `entity.update_post(dt)` run the two phases.
- `entity.stop()` / `entity.on_stop()` stops the entity and its handlers.
- `entity.free()` stops it if needed, fires `on_free` and marks it freed. A freed entity ignores any further update.

Handlers are attached before the entity starts and detached when it is freed.

## Authoritative position

`entity.node` is not necessarily where the entity is: a `CharacterControllerHandler` moves its own Bullet node, not the entity node. Never choose between the two nodes by hand; call [`world_position`](../utils/position.md), which owns the resolution rule and the headless fallback.

## `Scene`

`src/scenes/__scene.py`.

| Method | Behaviour |
| --- | --- |
| `scene.add_entity(entity)` | Adds an entity and starts it if the scene is already active. |
| `scene.remove_entity(entity_or_id)` | Removes and frees an entity. |
| `scene.get_entity(entity_id)` | Returns an entity by id. |
| `scene.add_task(name, func, sort=0)` | Registers a task owned by the scene. |
| `scene.remove_task(name)` | Removes a task owned by the scene. |
| `scene.on_start()` | Marks the scene active and starts its entities. |
| `scene.on_update(dt)` | Updates the entities. |
| `scene.on_post_update(dt)` | Runs the post-update phase of the entities. |
| `scene.on_stop()` | Removes the owned tasks, then frees the entities. |

The order inside `on_stop` matters: the tasks are removed **before** the entities are freed, so a task can never run against an entity that is being destroyed.

Scene tasks are described in [tasks.md](tasks.md), and the phase order in [update_pipeline.md](update_pipeline.md).

Source: `src/entities/entity.py`, `src/scenes/__scene.py`
Tests: `tests/terminal/entities.py`, `tests/terminal/scene_tasks_test.py`, `tests/terminal/post_update_test.py`
