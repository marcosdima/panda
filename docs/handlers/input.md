# Input Handlers

Input handlers produce **intent**, never movement. A movement handler reads the intent and decides what the body does with it, so a keyboard player and an NPC brain drive the same code path.

## `InputHandler` (base)

`src/handlers/input/base.py` is the interface every input source implements. It holds a movement vector and a set of action states.

- **`move_vector: Vec2`** — the movement intent, normalised when its length would exceed 1.
- **`set_move_vector(x, y)`** — writes the intent; used by human input and by virtual input sources such as the AI brain.
- **`set_action_state(action, is_down)`** — forces an action on or off.
- **`is_action_down(action)`** — the action is currently held.
- **`is_action_pressed(action)`** — true only on the frame the action went down.
- **`is_action_released(action)`** — true only on the frame the action came up.

Edge detection is resolved in `on_update`: the previous frame's states are kept for exactly one tick, so `is_action_pressed` fires once per press.

The base handler is also the input source for virtual controllers. It does not read the keyboard, so it can be driven from a test or from an AI handler without any device.

## `WASDInputHandler`

`src/handlers/input/wasd.py` maps the keyboard and mouse to the base interface.

- Accepts an optional `ActionMap`; without one it uses the default bindings.
- Writes the movement vector from the movement keys and the action states from the bound keys.
- Reads the mouse through the global mouse watcher, so it needs a running window. In headless mode it simply produces no intent.

## `ActionMap`

`src/handlers/input/action_map.py` decouples logical actions from physical keys.

```python
from src.handlers.input.action_map import ActionMap, JUMP, SPRINT

action_map = ActionMap()
action_map.rebind(JUMP, ["space", "mouse1"])
```

- **Module-level constants name every action**: `MOVE_FORWARD`, `MOVE_BACK`, `MOVE_LEFT`, `MOVE_RIGHT`, `JUMP`, `SPRINT`. `DEFAULT_BINDINGS` maps each action to its default keys.
- **`resolve_button(key)`** translates a key name (`"w"`, `"space"`, `"mouse1"`) into a Panda3D `ButtonHandle`; an unknown name raises `ValueError`.
- **`bind(action, key)`, `unbind(action, key=None)`, `rebind(action, keys)`** change the bindings at runtime.
- **`keys_for(action)`** returns the bound key names.
- **`is_down(action, is_button_down)`** takes the predicate as an argument, so input can be exercised headless with a fake predicate.
- **`ActionMap.default()`** returns the default map.

**Rule:** handlers consume actions through these constants, never through raw string literals. A literal `"jump"` in a handler is a bug: it cannot be rebound and it drifts from the map.

## `ParameterAdjustHandler`

`src/handlers/input/parameter_adjust.py` adjusts a numeric attribute of another handler at runtime, which is how tuning keys work.

- `target`: the object owning the attribute.
- `attribute_name`: the attribute to read and write; it must be a float or an int.
- `step`: increment applied per key press (default `0.1`).
- `min_value` / `max_value`: optional bounds.

It resolves the target handler on start, binds the increase and decrease keys, and writes the new value back through `setattr`.

## Writing an input source

1. Subclass `InputHandler` and implement `on_update` to translate a device into `set_move_vector` and `set_action_state` calls.
2. Use the `ActionMap` constants for every action.
3. Do not touch physics: the movement handler owns that.
4. Make the source work without a window when possible, so it can be tested headless.

Source: `src/handlers/input/`
Tests: `tests/terminal/action_map_test.py`, `tests/terminal/character_controller.py`, `tests/terminal/ai_test.py`
