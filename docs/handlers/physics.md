# Physics Handlers

Physics handlers own the bodies. They read intent from an input handler and move the simulation; they never read the keyboard directly.

## `CharacterControllerHandler`

`src/handlers/physics/character.py` wraps Panda3D's `BulletCharacterControllerNode` and is the movement handler of the engine.

| Parameter | Default | Meaning |
| --- | --- | --- |
| `radius` | `0.5` | Capsule radius. |
| `height` | `1.0` | Capsule height. |
| `step_height` | `0.4` | Maximum step the controller walks over. |
| `walk_speed` / `sprint_speed` | `5.0` / `10.0` | Horizontal speed per action state. |
| `jump_speed` | `7.0` | Impulse applied by `jump()`. |
| `gravity` | `14.0` | Downward acceleration. |
| `acceleration` / `deceleration` | `0.0` | Optional smoothing of the horizontal velocity. |
| `turn_speed` | `12.0` | How fast the body turns towards its movement direction. |
| `orientation_mode` | `MOVE_DIRECTION` | `MOVE_DIRECTION` or `CAMERA_LOOK`; `body_follows_camera_yaw` is a compatibility alias. |
| `camera_handler` | `None` | Camera used to orient the movement; resolved from the entity when omitted. |
| `visual_node` | `None` | Node that follows the body without being simulated. |
| `collision_group` | `DEFAULT` | Semantic group used by trigger filters. |

Behaviour:

- The movement vector is expressed **relative to the camera**: the handler projects the camera forward and right vectors on the horizontal plane, so "forward" always means "away from the camera".
- The sprint action selects the speed; the jump action triggers `jump()`.
- The controller moves **its own Bullet node**, which is why the authoritative position of an entity is not `entity.node` (see [../utils/position.md](../utils/position.md)).
- The capsule clears the camera blocker bit from its into-collide mask, so a character never blocks the camera or a line of sight.

## `RigidBodyHandler`

`src/handlers/physics/rigid_body.py` wraps a `BulletRigidBodyNode` for static terrain (`mass = 0`) and dynamic props (`mass > 0`).

- **`is_dynamic`** — true when the body has mass.
- **`linear_velocity`** — read and write the body velocity.
- **`add_shape(shape)`** — attach a collision shape.
- **`apply_impulse(vec)` / `apply_force(vec)`** — act on the body.
- The body node is parented under the entity node, so the transform stays composed.
- Each `on_update` detects a parent change and marks the Bullet transform dirty, so a scene-driven move is adopted on the next physics step while untouched bodies stay under Bullet's control.
- The body is tagged with its entity (`setPythonTag("entity", entity)`), which is how line-of-sight queries recognise a hit on a character instead of on scenery.

## `TriggerZoneHandler`

`src/handlers/physics/trigger_zone.py` wraps a `BulletGhostNode` and reports overlaps.

| Event | When |
| --- | --- |
| `on_enter` | An entity entered the volume. |
| `on_stay` | An entity is inside the volume on this frame. |
| `on_exit` | An entity left the volume. |
| `on_rejected` | An entity overlapped but was filtered out. |

- **`target_groups`** — only these groups trigger the events.
- **`avoid_groups`** — these groups never trigger the events.
- A zone with explicit `target_groups` skips ambient `CollisionGroup.DEFAULT` overlaps, so static scenery detected through Bullet's inflated broadphase AABBs does not produce noise.
- The ghost has no collision response: bodies and characters pass through it.
- The ghost is intentionally **not** tagged with its entity, so triggers never detect each other.

## `CollisionGroup`

`src/handlers/physics/groups.py` defines the semantic labels stored on the physics handlers: `DEFAULT`, `PLAYER`, `ENEMY`, `INTERACTABLE`, `PROP`. They are used by trigger filters and also expose a corresponding `BitMask32` bit via `group.bitmask`.

The same module defines the two query masks, `CameraCollision` and `LineOfSight`, which share a single blocker bit so that both queries ignore characters and trigger volumes. The convention and the query API are documented in [../engine/physics_world.md](../engine/physics_world.md).

Source: `src/handlers/physics/`
Tests: `tests/terminal/physics_handlers.py`, `tests/terminal/character_controller.py`, `tests/terminal/ai_test.py`, `tests/terminal/phase1_stabilization_test.py`
