# Physics World

`src/globals/physics.py` owns the Bullet world: the single place where bodies are created, removed and queried.

## The world

- `Physics.get_world()` returns the world, creating it on first use.
- The world is created with gravity `(0, 0, -9.81)`.
- The physics task `physics_world_updater` steps the world once per frame with fixed substeps (`doPhysics(dt, MAX_SUBSTEPS, FIXED_TIMESTEP)`) between the two engine phases unless paused via `Physics.set_paused(True)` (see [update_pipeline.md](update_pipeline.md)).

## Bodies

| Method | Behaviour |
| --- | --- |
| `Physics.create_body(name, mass=0.0)` | Creates a rigid body, attaches it to the world and returns the node. |
| `Physics.create_ghost(name)` | Creates a ghost body, attaches it and returns the node. |
| `Physics.remove_body(name_or_node)` | Removes a rigid body. |
| `Physics.remove_ghost(name_or_node)` | Removes a ghost body. |
| `Physics.clear_all()` | Removes all tracked and untracked bodies, ghosts and constraints. Returns counts. |
| `Physics.clear_all_bodies()` | Backward-compatible alias for `clear_all()`. |
| `Physics.debug_dump()` | Returns diagnostic counts and orphan node count. |
| `Physics.attach_character(node)` | Attaches a character controller to the world. |
| `Physics.remove_character(node)` | Detaches a character controller. |

`create_body` attaches the node to the world, but **the shape is added afterwards**. A body without a shape is an empty volume, and Bullet's broadphase registers it with the shape's AABB, so a body created and never given a shape contributes a degenerate volume to the broadphase. This is the reason behind the two-step creation used by the handlers: create the node, then add the shape, and never leave a shapeless body attached.

## Queries

### `raycast_closest(from_pos, to_pos, mask=None, step_physics=False)`

Returns `(hit_pos, hit_node)` for the closest hit, or `None` when the path is clear.

- `step_physics=False` (default) keeps spatial queries pure and never advances the simulation.
- `step_physics=True` advances the world by a tiny amount before the query for standalone setups where transforms were modified without stepping the world.
- `mask=None` means every bit collides (`BitMask32.all_on()`).

### `sweep_sphere_closest(from_pos, to_pos, radius, mask=None)`

Returns `(fraction, hit_pos, hit_normal)` for the first impact of a sphere moving along the segment, or `None` when the path is clear.

- `fraction` in `[0, 1]` is how much of the path was travelled before the contact; the centre of the sphere is at `from_pos + (to_pos - from_pos) * fraction`.
- A `fraction` of about `0` means the sphere already overlaps geometry at its start.
- The query never advances the simulation.

The sweep is what the first-person camera uses to resolve the eye: a single swept sphere from a pivot inside the character to the desired eye position handles walls, corners, floors and ceilings uniformly.

## Collision masks

The masks are defined in `src/handlers/physics/groups.py` and shared by every query.

| Convention | Bit | Meaning |
| --- | --- | --- |
| `CameraCollision.BLOCKER_BIT` | `31` | The bit a body keeps to block camera and sight queries. |
| `CameraCollision.QUERY_MASK` | `31` | The mask a camera or sight query uses. |
| `LineOfSight.BLOCKER_BIT` | `31` | The same bit, on purpose. |
| `LineOfSight.QUERY_MASK` | `31` | The same mask. |

**One bit, one convention.** Both queries answer the same question — *does this body get in the way of a camera or an eye ray?* — and both must ignore the player's own body, so they share the bit instead of keeping two masks that could drift apart.

How it works in Bullet:

- World geometry keeps the default `all_on` into-collide mask, so it blocks both queries.
- Character controllers and trigger volumes use `CameraCollision.non_blocking_mask()`, which clears bit `31` from their into-collide mask. They are therefore invisible to camera and sight queries.
- Ordinary physical collisions are unaffected: Bullet only requires the masks of two bodies to overlap in *any* bit, and every other bit still matches.

`CollisionGroup` (`DEFAULT`, `PLAYER`, `ENEMY`, `INTERACTABLE`, `PROP`) is a semantic label used by trigger filters and also exposes a corresponding `BitMask32` bit via `group.bitmask`.

## Debug view

- `Physics.toggle_debug()` switches the Bullet wireframe on and off.
- `Physics.is_debug_enabled()` reports whether the wireframe is visible.
## Diagnostics

- `Physics.clear_all()` removes every rigid body, ghost and constraint present in the world, including unregistered (orphan) objects, and returns `{"bodies": ..., "ghosts": ..., "constraints": ...}`.
- `Physics.debug_dump()` returns `{"bodies", "ghosts", "constraints", "orphan_nodes"}`.
- CLI: `./venv/bin/python -m src.globals.physics --dump` prints the diagnostic snapshot as JSON.

Source: `src/globals/physics.py`
Tests: `tests/terminal/physics_cleanup_test.py`

- The wireframe requires a display; in headless mode it is simply not created.

Source: `src/globals/physics.py`, `src/handlers/physics/groups.py`
Tests: `tests/terminal/physics_handlers.py`, `tests/terminal/ai_test.py`, `tests/terminal/camera_handler.py`, `tests/terminal/phase1_stabilization_test.py`
