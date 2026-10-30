# Capabilities (`src/handlers/capabilities.py`)

Capabilities are runtime-checked `Protocol`s that let a handler declare what it exposes without tying it to a concrete class. An entity can then look up a capability by type and receive the first attached handler that matches, either by `isinstance` or by the handler's `provides` metadata.

## The protocols

| Capability | What it means | Typical provider |
|------------|---------------|------------------|
| `IntentSource` | Writes movement intent (`move_vector`, `set_move_vector`). | `WASDInputHandler`, `AIPatrolHandler`, `FollowHandler` |
| `Mover` | Owns entity movement (`on_update`). | `CharacterControllerHandler` |
| `PhysicsBody` | Exposes a physics body (`body_np` property). | `RigidBodyHandler` |
| `AnimationPlayer` | Plays animation clips (`play_animation`). | `ActorAnimationHandler` |
| `CameraRig` | Owns a camera. | Camera handlers |

All five are decorated with `@runtime_checkable`, so `isinstance(obj, Capability)` works at runtime against any object with the right shape — no `provides` declaration required.

## Looking up capabilities on an entity

`Entity.get_capability(capability_type)` returns the first attached handler that matches:

- by `isinstance(handler, capability_type)` (structural match for Protocols), or
- by `capability_type in handler.provides` (explicit declaration).

```python
mover = entity.get_capability(Mover)
if mover is not None:
    # the entity can move
```

`Entity.get_handler(type)` is the stricter alternative: it only matches exact types, never Protocols or `provides`.

## Declaring `provides`

A handler lists the capabilities it exposes in the class attribute `provides`:

```python
class RigidBodyHandler(Handler):
    phase = HandlerPhase.PHYSICS
    provides = (PhysicsBody,)
```

This lets `get_capability(PhysicsBody)` find the handler even when `isinstance(handler, PhysicsBody)` is `False` (for example when the Protocol requires a property the handler exposes differently).

## Why it exists

Without capabilities, an AI handler that needs "something that moves" would have to import `CharacterControllerHandler` directly. With capabilities it asks for `Mover` and works with any handler that satisfies the protocol — a test stub, a different physics backend, or a hand-rolled mover. That keeps the AI testable headless and the movement code path single.

Source: `src/handlers/capabilities.py`, `src/entities/entity.py`
Tests: `tests/terminal/capabilities_test.py`