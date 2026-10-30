# Sensor Handlers

Sensors **observe** and emit events. They never move the entity, never write intent and never touch the Bullet world. That is the split with the other areas:

- **Input** and **AI** produce intent.
- **Physics** consumes intent and owns bodies.
- **Graphics** and **Camera** read state and render it.
- **Sensors** read state and report it, so any brain, movement or gameplay handler can react.

Because a sensor only reads positions and dispatches callbacks, it works the same with a window and headless.

## `ProximitySensorHandler`

`src/handlers/sensors/proximity_sensor.py` maintains the set of entities within a radius of its own entity and emits enter/stay/exit events.

```python
sensor = ProximitySensorHandler(
    radius=8.0,
    exit_radius=12.0,  # hysteresis: leave later than you enter
    scene=scene,
    predicate=lambda entity: entity.name.startswith("NPC"),
)
entity.add_handler(sensor)

sensor.on_enter.add_callback(lambda other, distance: print("seen", other, distance))
sensor.on_exit.add_callback(lambda other, distance: print("lost", other))
```

| Parameter | Default | Meaning |
| --- | --- | --- |
| `radius` | required | Outer range at which a new entity starts being sensed. Must be finite and positive. |
| `exit_radius` | `radius` | Range an **already sensed** entity must exceed to leave. Must be `>= radius`. |
| `scene` | `None` | Scene whose `entities` registry is scanned. Without a scene the sensor stays inert but keeps its configuration. |
| `predicate` | `None` | Optional `Callable[[Entity], bool]` filter applied before measuring. |

| Event | Payload | Fired when |
| --- | --- | --- |
| `on_enter` | `(entity, distance)` | An entity becomes sensed, on that frame only. |
| `on_stay` | `(entity, distance)` | Every following frame the entity remains sensed. |
| `on_exit` | `(entity, distance)` | An entity leaves. The distance is the one measured that frame; when the entity can no longer be measured (freed) it is the last sensed distance. |

Callbacks receive exactly two positional arguments, `(entity, distance)`; the sensor does not call them with keywords.

| Query | Returns |
| --- | --- |
| `sensed_entities` | Currently sensed **alive** entities, nearest first. |
| `nearest` | Closest sensed **alive** entity, or `None`. |
| `distance_to(entity)` | Current distance, or `None` when the entity was freed or the sensor is detached. |
| `is_in_range(entity)` | Whether the entity is sensed and alive. |
| `clear()` | Drops the sensed set **without** firing exit events and aborts the events still pending for the current frame. |

### Hysteresis

`radius` gates entries, `exit_radius` gates exits. With `radius=4` and `exit_radius=6`, a target at 5 m is either outside (it never entered) or inside (it already entered and has not crossed the exit ring). Raising the exit radius is the supported way to stop a body hovering at the edge from flickering between enter and exit.

### Lifecycle

- `on_start` starts from an empty sensed set, so a stop -> start cycle never reports stale entities.
- `on_update` measures every candidate, applies the enter/exit thresholds, then dispatches exits, enters and stays. Callbacks run after the sensed set has been updated, and the frame an entity enters fires `on_enter` only.
- `on_stop` and `on_detach` call `clear()`: the world is going away, so exit events are not fired.
- `set_enabled(False)` pauses sensing because `Entity.on_update` skips disabled handlers; the sensed set is left as it was, so re-enabling resumes from the previous state.
- Assigning `handler.scene = other` clears the sensed set, because entities from the previous scene must not leak into the new one.

### Constraints

- It scans `scene.entities` every frame: **O(n)** in the number of entities of the scene. Use `predicate` to discard candidates cheaply.
- Only entities registered in the scene are visible. An entity that lives outside the scene is never sensed.
- **Scenery counts.** A ground plane or a wall registered in the scene within `radius` is sensed like any other entity; filter scenery with `predicate` when only actors should trigger it.
- Freed candidates are skipped. A sensed entity that is freed disappears from the queries immediately and the next update reports `on_exit` with its last distance.
- The sensor never creates a `NodePath`, a body or a ghost, so it has nothing to clean up beyond its own state.
- Distance comes from [`world_position`](../utils/position.md), so a sensor attached to a character measures from the controller node, not from the authored entity node.

## Sandbox

`tests/panda/proximity_sandbox.py` (`python -m tests.panda.proximity_sandbox`) draws the enter and exit rings and orbits a target through them, with live state, distance, nearest entity and event counters. `SPACE` pauses the orbit, `L` disables the sensor and `R` resets the phase.

Source: `src/handlers/sensors/`, `src/utils/position.py`
Tests: `tests/terminal/proximity_sensor_test.py`, `tests/panda/proximity_sandbox.py`
