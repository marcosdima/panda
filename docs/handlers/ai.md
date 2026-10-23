# AI Handlers

The AI is a **virtual input source**. It writes intent into the entity's `InputHandler` exactly like a human player would, and the same movement handler drives both. The brain never touches physics.

## `AIPatrolHandler`

`src/handlers/ai/patrol.py` patrols a list of waypoints and chases an optional target.

| Parameter | Default | Meaning |
| --- | --- | --- |
| `waypoints` | `[]` | Points to walk through. |
| `arrive_radius` | `0.5` | Distance at which a waypoint counts as reached, and how close the NPC stops while chasing. |
| `wait_time` | `1.0` | Seconds spent waiting on a waypoint. |
| `ping_pong` | `False` | Walk the waypoints back and forth instead of looping. |
| `target` | `None` | The entity to detect and chase. |
| `sight_range` | `8.0` | Maximum distance at which the target can be detected. |
| `lose_range` | `12.0` | Distance at which a chased target is given up (`sight_range * 1.5`). |
| `chase_sprint` | `True` | Set the `sprint` action while chasing. |
| `obstacle_mask` | `LineOfSight.QUERY_MASK` | Mask of the sight query. |
| `eye_height` | `1.0` | Height of the eye above the body origin. |
| `line_of_sight` | `None` | Callable replacing the raycast entirely. |

### States

`PatrolState` has three values, driven by a `StateMachine`:

| State | Behaviour |
| --- | --- |
| `PATROL` | Walk towards the current waypoint. |
| `WAIT` | Stand still for `wait_time` seconds, then advance to the next waypoint. |
| `CHASE` | Move towards the target while it is visible. |

The transitions are: `PATROL → WAIT` on arrival, `WAIT → PATROL` when the wait is over, and `PATROL → CHASE` / `CHASE → PATROL` depending on the detection.

### How it drives the body

Every frame the handler writes a normalized horizontal movement vector and the sprint action into the entity's `InputHandler`. It must therefore be attached **before** the movement handler, so the intent it writes is fresh on the same tick.

### Position resolution

The handler reads positions through [`world_position`](../utils/position.md), which resolves the character controller node when present and falls back to `entity.node`, so the brain is testable headless.

### Line of sight

**The first hit decides.** A ray is cast from the observer's eye to the target's eye:

- **No hit** → the target is visible.
- **A hit on world geometry** → the target is blocked.
- **A hit on the observer's own body or on the target's body** → the target is visible, because a body never hides its owner from itself.

Two consequences worth stating explicitly:

- `arrive_radius` plays **no role** in the sight test. It governs waypoint arrival and how close the NPC stops while chasing. An earlier version compared the hit distance against the distance to the target, which made a target whose body radius exceeded `arrive_radius` permanently invisible.
- The query uses the `LineOfSight` mask, which shares its blocker bit with `CameraCollision`. Character controllers and trigger volumes clear that bit, so characters and trigger volumes never occlude an eye ray while world geometry does.

The sight check is exposed as `can_see_target()`.

### Injectable sight

`line_of_sight` is a property accepting a `Callable[[Vec3, Vec3], bool]`. When it is set, it replaces the Bullet raycast entirely, which is useful for scripted behaviour and for isolating the raycast path in a sandbox. Setting it back to `None` restores the raycast at runtime, so a sandbox can switch between both without rebuilding the entity.

### Cost

The sight ray is only cast when it can change a decision: while patrolling, only when the target is inside `sight_range`, and while chasing, only while the target is inside `lose_range`. A target that is too far to matter costs no raycast.

## `FollowHandler`

`src/handlers/ai/follow.py` follows a single target at a set distance without waypoints or a state machine.

| Parameter | Default | Meaning |
| --- | --- | --- |
| `target` | `None` | The entity to follow. |
| `min_distance` | `1.5` | Stop getting closer when within this distance; inert at runtime when `stop_radius` was set explicitly (via constructor or setter). |
| `max_distance` | `None` | Give up when the target is farther than this; the follower resumes following as soon as the target comes back within range. |
| `stop_radius` | `min_distance` | Effective stop distance; defaults to `min_distance`. |
| `speed_factor` | `1.0` | Scales the unit direction; the written vector is capped at unit length, so values above `1.0` have no further effect. A negative value walks away from the target. |
| `chase_sprint` | `False` | Set the `sprint` action while following. |

### States

`FollowState` (a `str` subclass, mirroring `PatrolState`) has three values:

| State | Member | Behaviour |
| --- | --- | --- |
| `stopped` | `STOPPED` | No target, target freed, or within `stop_radius`. Zero intent is written. |
| `following` | `FOLLOWING` | Between `stop_radius` and `max_distance`: writes a unit direction toward the target scaled by `speed_factor`. |
| `out_of_range` | `OUT_OF_RANGE` | `max_distance` is set and the target is beyond it. Zero intent is written; resumes when the target returns. |

When both `stop_radius` and `max_distance` apply, `OUT_OF_RANGE` takes precedence (the range check is evaluated before the stop check).

**How it drives the body:** see [AIPatrolHandler](#aipatrolhandler) — the same attach-order rule applies: the handler must be attached **before** the movement handler so the intent it writes is fresh on the same tick, and it is a virtual input source that writes to `InputHandler` without touching physics or the target.

**Constraints:**

- The written vector is **world-space**: it points straight at the target regardless of any camera on the follower entity. A follower that also carries a camera handler will walk along the camera's forward axis, not toward the target, because `CharacterControllerHandler` interprets `(x, y)` as camera-relative when a camera handler is present on the same entity. Do not attach a camera handler to the follower.
- Prefer one intent source per entity: if the follower also carries a `WASDInputHandler` (or another intent writer), the last writer in attach order wins each frame.

Position resolution follows the same controller-or-node rule as `AIPatrolHandler` ([Position resolution](#position-resolution) above): the character controller's Bullet node wins over `entity.node`.

**Public members:**

| Member | Meaning |
| --- | --- |
| `target` | Current follow target, or `None`. |
| `set_target(target)` | Set or clear the follow target. |
| `state` | `FollowState.STOPPED` / `FOLLOWING` / `OUT_OF_RANGE`. |
| `move_vector` | Last movement intent written to `InputHandler` (a `Vec2`). |
| `min_distance` / `stop_radius` / `max_distance` / `speed_factor` / `chase_sprint` | Runtime-mutable attributes; see the parameter table above for defaults and semantics. |

Source: `src/handlers/ai/`
Tests: `tests/terminal/ai_test.py`, `tests/terminal/follow_handler_test.py`
