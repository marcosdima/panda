# Component Handlers

Components are handlers that add an interface or an overlay on top of the entity. Most expose a way to interact with it without changing how the entity behaves. Two are behaviour-changing and say so explicitly: ``HealthHandler`` (it can disable the entity's ``InputHandler`` on death) and ``SpawnerHandler`` (it creates new entities). Component authors keep that choice explicit per handler.

All of them degrade gracefully when there is no window: in headless mode UI-only components log a debug line and stay inert, while ``HealthHandler`` and ``SpawnerHandler`` remain fully functional (no window, no Bullet body, no NodePath of their own).

## `PauseHandler`

`src/handlers/pause/pause_handler.py` provides a minimal pause menu.

- **Toggle:** `Escape` (the key is configurable through `_pause_key`, `P` being the usual alternative).
- **While paused:** the mouse capture is released and the cursor becomes visible, a semi-transparent panel with *Resume* and *Quit* buttons is shown, and `is_paused` becomes `True`.
- **While running:** the UI is removed and the mouse capture is restored.
- `toggle_pause()` switches between the two states and can be called from code.
- The handler resolves the `ThirdPersonCameraHandler` of the entity to control the cursor.
- The UI is created only when a window exists; the pause key is still registered.

`is_paused` is the flag the rest of the engine reads. The per-frame dispatch of the engine skips the main scene while it is paused (see [../engine/update_pipeline.md](../engine/update_pipeline.md)), so a paused scene does not advance.

## `CameraControlComponent`

`src/handlers/components/camera_control.py` adds two buttons that zoom the third-person camera.

- It looks for a `ThirdPersonCameraHandler` on the same entity; without one it logs a warning and does nothing.
- The buttons change the camera distance by `_increment` (`0.5`) per press, within the handler's `min_distance` and `max_distance`.

## `CameraSettingsComponent`

`src/handlers/components/camera_settings.py` adds a panel of sliders that tune the third-person camera at runtime.

| Slider | Step | Range |
| --- | --- | --- |
| `distance` | `0.1` | `min_distance` to `max_distance` of the camera handler. |
| `pitch` | `0.5` | Clamped by the camera handler. |
| `yaw` | `1.0` | `0` to `360`. |
| `offset_z` | `0.05` | Vertical offset of the camera target. |

The panel and its sliders are created only when a window exists, and they are removed on stop.

## `HealthHandler`

`src/handlers/components/health_handler.py` owns an entity's health as an optional component.

| Parameter | Default | Meaning |
| --- | --- | --- |
| `max_health` | `100.0` | Upper bound of ``current_health``. |
| `current_health` | `max_health` | Starting health, clamped to ``[0, max_health]``. |
| `auto_free_on_death` | `False` | Free the entity (via ``entity.free()``) when it dies. Takes precedence over ``disable_input_on_death``: when both are set, the entity is freed and the input-disable step is skipped. |
| `disable_input_on_death` | `True` | Disable the entity's ``InputHandler`` when it dies (movement intent is zeroed too) and re-enable it on stop/detach — but only if this handler disabled it (input disabled by the user is left alone). A start on an already-dead entity re-disables the input, unless ``auto_free_on_death`` is set (then only the disable step is skipped on the death path; the entity itself is freed by the caller). This only stops intent written through ``is_enabled``; AI handlers that call ``set_move_vector`` directly bypass it. |

### Properties

| Property | Meaning |
| --- | --- |
| `current_health` | Current health, clamped to ``[0, max_health]``. |
| `is_dead` / `is_alive` | Health at/below zero / above zero. |

### Methods

| Method | Meaning |
| --- | --- |
| `take_damage(amount, source)` | Reduce health (clamped at zero). Returns ``True`` when health changed; ``False`` when already dead. |
| `heal(amount)` | Restore health (clamped at ``max_health``). Returns the amount actually restored; ``0.0`` when dead. |

### Events

Two :class:`~src.utils.event.Event` instances fire without requiring listeners to hold references:

- `on_damage(amount, source)` — whenever health drops, with the **applied** (clamped) amount of damage and the damage source.
- `on_death(entity)` — once when the entity dies as a result of damage.

### How it drives the body

It never touches physics or graphics. The single exception is ``disable_input_on_death``, which disables the entity's ``InputHandler`` on death. Other systems (spawners, UI, scoring) subscribe to ``on_damage`` / ``on_death`` and act independently.

This component degrades gracefully headless: no window, no Bullet body, no NodePath — it can be exercised without a ``ShowBase``.

## `SpawnerHandler`

`src/handlers/components/spawner_handler.py` spawns entities in reaction to its own entity's trigger zone.

| Parameter | Default | Meaning |
| --- | --- | --- |
| `entity_factory` | required | Callable ``() -> Entity`` that builds the entity to spawn. |
| `scene` | `None` | Scene to add spawned entities to. When `None`, ``spawn()`` still builds and tracks but does not register in a scene. |
| `spawn_on_enter` | `True` | Spawn automatically when the entity's trigger zone reports an enter. |
| `max_spawns` | `None` | Stop spawning once this many entities have been built. The budget survives a stop -> start cycle; only the cooldown is reset by ``on_start``. |
| `cooldown` | `0.0` | Seconds between allowed spawns; enters within the window are ignored. |

### Properties

| Property | Meaning |
| --- | --- |
| `spawned_entities` | Currently tracked spawned entities (alive spawns). |
| `spawn_count` | Total entities spawned since creation. |

### Methods

| Method | Meaning |
| --- | --- |
| `spawn()` | Build via factory, add to scene, track. Returns the entity or ``None`` when blocked by ``max_spawns``/cooldown. |
| `clear_spawned()` | Free every live tracked spawn and clear the list. Each spawn is deregistered from the scene first, but only when the registry still maps its id to that exact entity; spawns already freed elsewhere are deregistered without a second ``free()``. Also invoked by ``on_stop`` and ``on_detach``. |

### How it drives the body

It does not move anything: the spawner reads its entity's ``TriggerZoneHandler.on_enter`` and writes nothing to physics or transforms. Detection (``TriggerZoneHandler``) and reaction (``SpawnerHandler``) live on the same entity — a clean split of concerns.

``on_detach`` also runs the cleanup: :meth:`Entity.free` skips ``on_stop`` for an entity that was never started, so detaching is the only hook available in that path. Spawns freed elsewhere (for example by ``HealthHandler(auto_free_on_death=True)``) are not reported by ``spawned_entities`` and are skipped by ``clear_spawned``; this matters because ``Entity.free`` recycles ids, and a stale tracked id could otherwise stop an unrelated entity.

Place spawns outside the trigger volume. A spawn created inside it fires a new ``on_enter`` on the next frame, and with ``max_spawns=None`` that self-retriggering chains one spawn per frame without bound; ``max_spawns`` is the guard when the factory cannot control placement.

Degrades gracefully headless: no window, no Bullet body of its own, no NodePath beyond the factory's entities. Every live tracked spawn is freed on ``on_stop``, ``on_detach`` or ``clear_spawned``, so spawning never leaks entities or ids.

Source: `src/handlers/components/`, `src/handlers/input/`, `src/handlers/pause/`, `src/handlers/physics/`
Tests: `tests/terminal/entities.py`, `tests/terminal/health_handler_test.py`, `tests/terminal/spawner_handler_test.py`
