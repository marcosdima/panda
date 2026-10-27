# Testing

## Why two tiers

Traditional assertions (`assert a == b`) are necessary but insufficient to verify real-time 3D behaviour (collisions, friction, step climbing, camera smoothing, animation blending, AI perception). The engine therefore uses a dual-tier architecture:

1. **Headless unit tests (`tests/terminal/`):** fast, non-visual suites executed with `windowType='none'`, suitable for CI and automated verification.
2. **Interactive in-engine sandboxes (`tests/panda/`):** visual testbeds where each gameplay subsystem is isolated, observed and manipulated in real time.

Every feature is expected to have at least the headless coverage; sandbox coverage is added when the behaviour is visual.

## Base test class

All tests inherit from `Test` (`tests/__test.py`), which extends `Scene`:

```python
class Test(Scene):
    """Base class for all test scenes."""
```

`Test` provides terminal formatting helpers used by every suite:

- **`p(msg, *, bold, color, center, width, raw)`:** print a message with optional ANSI styling.
- **`space_line(l)`:** print a decorative separator line.
- **`print_title(title, color, width)` / `print_subtitle(subtitle, color, width)`:** decorated section headers.

Environment setup (ground planes, lighting, cameras, debug keybindings) is the responsibility of each sandbox, not of the base class.

## Writing a test

A suite is a `Test` subclass that exposes `test*` methods. `TerminalTest` auto-discovers them and runs them on scene start; the same methods are collected by pytest, so a suite runs in both modes.

```python
class TestSomething(Test):
    def on_start(self) -> None:
        super().on_start()
        self.print_title("Something Suite started.", color="cyan")
        self.check_something()          # shared check functions
        self.p("Something works.", color="green")
        self.print_subtitle("Something Suite completed.", color="green")
```

Rules that keep the suites usable headless:

- **No `ShowBase` in the suite.** Use the shared `check_*` functions and let the harness own the window. Suites that need a loader bootstrap their own `ShowBase(windowType="none")`.
- **Checks are plain functions.** A `check_*` function holds the assertions and is called both by the in-engine suite and by the pytest wrapper, so the two modes never drift.
- **Assert on behaviour, not on internals.** Prefer observable results (a position, a state, a callback) over private attributes.
- **Fake the input, not the physics.** Input handlers expose a fake-predicate API, so input can be exercised without a keyboard.

## Catalog of headless suites (`tests/terminal/`)

| Suite | Test object |
| :--- | :--- |
| `events.py` | `Event` callback priority, gating (`check`), invocation. |
| `event_test.py` | `Event` arity handling, `add_once`, mutation during dispatch, clearing. |
| `entities.py` | `Entity` id allocation and recycling, handler attachment and queries, lifecycle hook order, scene propagation. |
| `follow_handler_test.py` | `FollowHandler` virtual-input AI: follow/stop/out-of-range states, target cleared/freed, sprint release on state transition, zero-intent on `on_start`, public exports (`FollowHandler`, `FollowState`), `CharacterControllerHandler` position-resolution branch, `min_distance`/`stop_radius` mirroring contract (mirrors when not explicit, inert when explicit), `speed_factor` scaling (unit-length cap above `1.0`, negative reversal). |
| `proximity_sensor_test.py` | `ProximitySensorHandler`: enter/stay/exit sequence with distance payloads (`on_enter` only on the entry frame), `exit_radius` hysteresis without widening the entry gate, nearest-first sensed set, `predicate` filtering, ignored self and freed candidates, immediate liveness in queries, exit on a freed sensed entity, `clear`/`on_stop`/`on_detach` without exit events, `clear()` from an exit callback aborting the pending batch, reassigning `scene`, never-started `free()`, `scene=None` inertness, distance through `world_position`, headless parented-node resolution, radius/hysteresis validation and package export. |
| `character_controller.py` | `WASDInputHandler` + `CharacterControllerHandler` (parameters, movement, damping, jump, leak-free detach). |
| `camera_handler.py` | `ThirdPersonCameraHandler` (spherical math, clamping, smoothing, headless safety) and `FirstPersonCameraHandler` (eye lock, view orientation, yaw/pitch clamping, controller tracking, see-through protection, near-plane fitting on the real lens, lens restore, ignoring own capsule and triggers, smoothing validation). |
| `actor_animation.py` | `ActorAnimationHandler` (visual pivot, animation binding, locomotion states, teardown). |
| `actor_locomotion_test.py` | Velocity-driven clip selection (Idle → Walk → Run), clip fallbacks, manual override reconciliation, cleanup. |
| `physics_handlers.py` | `RigidBodyHandler` + `TriggerZoneHandler` (config, gravity, impulses, entity-node transform sync, enter/stay/exit edges, group filters, lifecycle leaks). |
| `rigid_body_suspend_test.py` | `RigidBodyHandler` suspension contract: detach/freeze, motion and force clearing (and `preserve_motion`), resume adopting a transform acquired while carried, `rebase` after drift, stop/start persistence, idempotency and the shared `resolve_collision_group` resolver. |
| `model_handler.py` | `ModelHandler` (parameters, entity attachment and transforms, `GlobalLoader` template caching, per-entity instances, graceful missing asset, lifecycle leaks). |
| `action_map_test.py` | `ActionMap` default bindings, bind/unbind/rebind, unknown key errors, custom maps on `WASDInputHandler`. |
| `ai_test.py` | `AIPatrolHandler` (patrol cycle, ping-pong, chase and lose, injected sight) and line-of-sight semantics (no hit, target body, observer body, world geometry, other entity, `arrive_radius` independence, default mask, injectable source precedence, runtime source toggle). |
| `scene_tasks_test.py` | `Scene` task ownership (per-scene registration, same-name isolation between scenes, `remove_task` scoping, no orphan on name reuse, automatic cleanup on `on_stop`). |
| `game_update_test.py` | `Game` update dispatch (started scene only, paused behaviour, missing or stopped scene, switching scenes). |
| `global_event_bus_test.py` | Engine-wide `GlobalEventBus` on top of `Event` (subscribe/publish/unsubscribe/has_listeners/clear, callable-equality matching, mandatory unsubscribe on `on_stop`, `"events"` service-locator registration). |
| `health_handler_test.py` | `HealthHandler` component: damage/heal clamping, `is_dead`/`is_alive`, `on_damage`/`on_death` event payloads (applied amount), `auto_free_on_death`, `disable_input_on_death` (input restore on `on_stop`/`on_detach`, user-disabled input left alone; `on_start` re-disables a dead entity's input), start and constructor clamping, entity-level start/stop cycle. |
| `spawner_handler_test.py` | `SpawnerHandler` component: spawn-on-enter, `max_spawns` cap (budget survives stop→start), cooldown window (reset by `on_start`), `spawn_on_enter=False` manual spawn, `set_enabled(False)` pausing automatic spawns, `scene=None` tracking, subscription symmetry across stop→start, cleanup via `clear_spawned`/`on_stop`/`on_detach` (including a never-started entity and `remove_handler` on a started one), deregistration of spawns freed elsewhere, and stale-spawn pruning so a recycled id never stops an unrelated entity. |
| `post_update_test.py` | Post-update pipeline: handler hook, scene propagation, task sort order, pause behaviour, camera transform written only after the physics step. |
| `cooldown_test.py` | `Cooldown` initial state, invalid duration, start and tick behaviour, reset and trigger. |
| `state_machine_test.py` | `StateMachine` transitions and validation, same-state no-op, hook order, reentrant transition guard, reset semantics. |
| `math_test.py` | `clamp`, `lerp`, `smoothstep`, `normalize_angle`, `lerp_angle`, `remap`. |
| `paths_test.py` | `get_project_root` detection strategies, `resolve_asset_path` with multi-segment and path-like inputs. |
| `physics_cleanup_test.py` | `Physics` cleanup and diagnostics: `clear_all`, counts, idempotency, orphan detection. |
| `replay_test.py` | Replay helpers: file roundtrip, ordered event dispatch, snapshot and assertion validation. |

Run every suite in one isolated subprocess pass (PASS/FAIL summary with durations, non-zero exit on failure):

```bash
windowType=none ./venv/bin/python -m tests.terminal.run_all
```

## Catalog of interactive sandboxes (`tests/panda/`)

| Sandbox | Target | Objectives |
| :--- | :--- | :--- |
| `character_sandbox.py` | `CharacterControllerHandler` + `ThirdPersonCameraHandler` + `ActorAnimationHandler` | Walking, stairs (0.2m–0.6m), ramps (15°/30°/45°), jumping, camera orbit, animation states, OSD telemetry, F12 wireframe. |
| `camera_sandbox.py` | `FirstPersonCameraHandler` + `ThirdPersonCameraHandler` + `CharacterControllerHandler` | Eye-locked first-person look, orientation reference corridor, near-wall contrast and sticky wall to verify FP never sees through geometry, live `V` toggle between FP and TP, OSD telemetry, F12 wireframe. |
| `physics.py` | `Physics` world | Static and dynamic rigid body collision (falling cube on static base). |
| `models.py` | `GlobalLoader` | Loading Panda3D default models and glTF actors with animations. |
| `triggers_sandbox.py` | `TriggerZoneHandler` + `RigidBodyHandler` + `CharacterControllerHandler` | Enter/stay/exit/rejected events, group filters (PLAYER vs ENEMY), oscillating body transform sync, OSD counters, F12 wireframe. |
| `ai_sandbox.py` | `AIPatrolHandler` + `CharacterControllerHandler` + `ThirdPersonCameraHandler` + `TriggerZoneHandler` | Patrol waypoints and chase states, real Bullet line-of-sight raycast against walls with a sight gap, runtime `L` toggle between the raycast and an injected callable, `T` toggle between automatic and manual (`WASD`) target control, trigger enter/stay/exit counters, OSD telemetry, F12 wireframe. |
| `follow_sandbox.py` | `FollowHandler` + `InputHandler` + `CharacterControllerHandler` (follower) + `WASDInputHandler`/`_TargetDriverHandler` + `CharacterControllerHandler` (target) + `ThirdPersonCameraHandler` on a separate rig | Follow-at-distance behaviour, world-space intent vs. camera-on-follower constraint, `T` target AUTO/MANUAL, `L` leash toggle (`out_of_range`), OSD telemetry (`state`, `move_vector`), clean Bullet-teardown check. |
| `proximity_sandbox.py` | `ProximitySensorHandler` | Enter (cyan) and exit (magenta) rings, orbiting target crossing the hysteresis window, `SPACE` pause, `L` enable/disable, `R` phase reset, OSD telemetry (state, distance, nearest, enter/exit counters). |

| `animation_sandbox.py` | `InputHandler` + `CharacterControllerHandler` + `ActorAnimationHandler` + `ThirdPersonCameraHandler` | Velocity-driven state transitions (Idle → Walk → Run) in isolation: scripted ramp writes the movement vector and sprint flag, `A` auto sequence toggle, `J` jump request, phase index and per-transition blend durations in the inspector, OSD telemetry (phase, state, animation, real velocity, blend pair). |

## Execution modes

### Interactive visual

```bash
./venv/bin/python main.py
```

Launches the playground selector (`python -m tests.playground`). It lists every registered visual scene and runs the chosen one in an isolated subprocess. Single-scene runs are possible with `python -m tests.playground --scene <key>`.

### Headless

Each suite runs without a display server:

```bash
windowType=none ./venv/bin/python -m tests.terminal.ai_test
windowType=none ./venv/bin/python -m pytest -q tests/terminal/
```

### Hybrid

A headless suite can also run inside the full engine window by launching its module directly (for example `python -m tests.terminal.entities`); assertion output is printed to the terminal.

### Test menu

```bash
./venv/bin/python -m tests.playground
```

Scans the scene registry, lists every visual sandbox, and launches the selected one in an isolated subprocess with a configurable timeout (`--timeout`). `R` re-runs the last scene and `Q` quits. Integration suites run via `tests.terminal.run_all`.

## Batch validation (`scripts/`)

Before a feature batch goes to review, the lead runs the mechanical checks locally. They cover what a human reviewer should not have to read: naming, scope, lifecycle mechanics and documentation hygiene.

```bash
./scripts/run_batch_validation.sh          # all checks + full headless suite
./scripts/run_batch_validation.sh --no-suite
./scripts/run_batch_validation.sh src/handlers/components/spawner_handler.py docs/handlers/components.md tests/terminal/spawner_handler_test.py
```

| Script | Checks |
| :--- | :--- |
| `scripts/check_diff_scope.py` | New terminal tests follow the `*_test.py` convention and carry the pytest guard; new docs have `Source:`/`Tests:` footers; reports files outside the project trees (ignored unless `--all`). |
| `scripts/audit_handler_contract.py` | Every `Handler`/`Component` subclass calls `super()` in `on_attach`/`on_detach`, declares `on_update(self, dt)`, never creates nodes in `__init__`, never indexes `get_handlers()[0]`, and keeps `direct.showbase` behind `if TYPE_CHECKING:`. |
| `scripts/verify_docs_links.py` | Relative links resolve and every path quoted in a `Source:`/`Tests:` footer exists. |
| `scripts/run_batch_validation.sh` | Runs the three checks above plus `tests.terminal.run_all`; every step runs even if a previous one failed and the summary lists the failing steps. |

Advisory findings (for example `super()` called after cleanup, or a public class that its package `__init__.py` does not re-export) are printed as `note:` lines and only fail with `--strict`. They flag conventions that existing modules do not all follow, so a clean run of the current tree stays green.

Source: `tests/__test.py`, `tests/__init__.py`, `tests/terminal/`, `tests/panda/`, `scripts/`
Tests: `tests/terminal/run_all.py`
