# Custom In-Engine Testing Framework Specification

## 1. Motivation

In game development, traditional assertions (`assert a == b`) are necessary but insufficient to verify real-time 3D behavior (collisions, friction, step-climbing, camera smoothing, animation blending, AI perception).

We establish a dual-tier testing architecture:
1. **Headless Unit Tests (`tests/terminal/`):** Fast, non-visual assertion suites executed in headless mode (`windowType='none'`).
2. **Interactive In-Engine Sandboxes (`tests/panda/`):** Visual 3D testbeds where each gameplay subsystem is isolated, observed, and manipulated in real time.

---

## 2. Base Test Class (`tests/__test.py`)

All tests (headless and visual) inherit from `Test` (which extends `Scene`):

```python
class Test(Scene):
    """Base class for all test scenes."""
```

`Test` provides terminal formatting helpers used by every suite:

* **`p(msg, *, bold, color, center, width, raw)`:** Print a message with optional ANSI styling.
* **`space_line(l)`:** Print a decorative separator line.
* **`print_title(title, color, width)` / `print_subtitle(subtitle, color, width)`:** Decorated section headers.

Environment setup (ground planes, lighting, cameras, debug keybindings) is the responsibility of each individual sandbox, not of the base class.

---

## 3. Catalog of Test Suites

### 3.1 Headless Unit Tests (`tests/terminal/`)

| Suite File | Test Object |
| :--- | :--- |
| `tests/terminal/events.py` | `Event<T>` callback priority, gating (`check`), invocation. |
| `tests/terminal/entities.py` | `Entity` ID allocation/recycling, handler lifecycle, scene propagation. |
| `tests/terminal/character_controller.py` | `WASDInputHandler` + `CharacterControllerHandler` (params, movement, damping, jump, leak-free detach). |
| `tests/terminal/camera_handler.py` | `ThirdPersonCameraHandler` (spherical math, clamping, smoothing, headless safety). |
| `tests/terminal/actor_animation.py` | `ActorAnimationHandler` (visual pivot, animation binding, locomotion states, teardown). |

Each suite runs via `TerminalTest`, which auto-discovers and executes all `test*` methods on scene start.

### 3.2 Interactive Sandboxes (`tests/panda/`)

| Suite File | Sandbox Target | Test Objectives |
| :--- | :--- | :--- |
| `tests/panda/character_sandbox.py` | `CharacterControllerHandler` + `ThirdPersonCameraHandler` + `ActorAnimationHandler` | Walking, stairs (0.2m–0.6m), ramps (15°/30°/45°), jumping, camera orbit, animation states, OSD telemetry, F12 wireframe. |
| `tests/panda/physics.py` | `Physics` world | Static/dynamic rigid body collision (falling cube on static base). |
| `tests/panda/models.py` | `GlobalLoader` | Loading Panda3D default models and glTF Actor with animations. |

### 3.3 Planned Sandboxes (not yet implemented)

| Suite File | Sandbox Target | Test Objectives |
| :--- | :--- | :--- |
| `tests/panda/triggers_sandbox.py` | `TriggerZoneHandler` | Dynamic enter/stay/exit events, group filters (Player vs Enemy vs Default). |
| `tests/panda/animation_sandbox.py` | `ActorAnimationHandler` | Velocity-driven state transitions (Idle → Walk → Run) in isolation. |
| `tests/panda/camera_sandbox.py` | `ThirdPersonCameraHandler` | Target follow lerp, mouse orbit, collision spring-arm against test walls. |
| `tests/panda/ai_sandbox.py` | AI Behavior Handlers | Patrol paths, line-of-sight raycasts, target chasing. |

---

## 4. Test Execution Modes

### 4.1 Interactive Visual Mode
Run with a graphical window:
```bash
python main.py
```
The active suite is selected by the `TARGET` constant in `tests/__init__.py` (e.g., `TARGET = 'character'`). Valid targets: `events`, `entities`, `controllers`, `camera`, `animation`, `physics`, `models`, `character`, or `None`.

### 4.2 Headless Suite Execution
Each headless suite is directly executable without initializing a display server (suitable for terminal workflows, automated agent verification, and CI):
```bash
python tests/terminal/events.py
python tests/terminal/entities.py
python tests/terminal/character_controller.py
python tests/terminal/camera_handler.py
python tests/terminal/actor_animation.py
```
Headless suites that require a `Loader` (e.g., `actor_animation.py`) bootstrap their own `ShowBase(windowType="none")` automatically.

### 4.3 Hybrid Execution
Headless suites can also be run through `main.py` by setting the corresponding `TARGET` (e.g., `TARGET = 'entities'`). In this mode the suite runs inside the full engine window; assertion output is printed to the terminal.
