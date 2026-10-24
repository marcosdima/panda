# Position

`src/utils/position.py` owns the answer to *where is this entity?*.

```python
from src.utils import world_position

position = world_position(entity)
```

## Why it exists

An entity has a `node`, but that node is **not always authoritative**:

- `CharacterControllerHandler` moves its own Bullet node (`controller_np`) and leaves `entity.node` where it was authored.
- Models, cameras and static entities never move the entity node at all.

Reading `entity.node.getPos()` would therefore report a stale position for any character. `world_position` centralizes the resolution so the AI brains, the camera handlers and the proximity sensor all agree:

1. If the entity has a `CharacterControllerHandler` with a valid, non-empty `controller_np`, use that node.
2. Otherwise, if the entity has a `RigidBodyHandler` with a valid, non-empty `body_np`, use that node.
3. Otherwise use `entity.node`.
4. Return the origin for an empty node.

The controller and rigid body nodes are parented under `entity.node`, so resolving them in world space includes the entity node transform: moving either node moves the reported position. What the helper refuses to do is read `entity.node` alone, which would ignore the physics offset.

The position is expressed in `render` when a live `base` exposes one and the node has a parent. Headless there is no `render`, so the node is resolved against its **top-most ancestor**, which keeps parented entities in world-like coordinates instead of reporting a parent-local offset.

The helper imports `CharacterControllerHandler` and `RigidBodyHandler` inside the function on purpose: `src.handlers` imports `src.utils`, so a module-level import would close the cycle. Keep it function-local unless the dependency moves out of `src/utils`.

## Contract

| Aspect | Behaviour |
| --- | --- |
| Return type | `panda3d.core.Vec3` |
| Precedence | `controller_np` -> `body_np` -> `entity.node` |
| Empty node | `Vec3(0, 0, 0)` |
| Headless | Resolves against the top-most ancestor; no `base` or `render` required |
| Ownership | It creates no node and stores no reference. |

Source: `src/utils/position.py`
Tests: `tests/terminal/follow_handler_test.py`, `tests/terminal/proximity_sensor_test.py`, `tests/terminal/phase1_stabilization_test.py`
