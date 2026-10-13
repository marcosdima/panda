# Custom In-Engine Testing Framework Specification

## 1. Motivation

In game development, traditional assertions (`assert a == b`) are necessary but insufficient to verify real-time 3D behavior (collisions, friction, step-climbing, camera smoothing, animation blending, AI perception).

We establish a dual-tier testing architecture:
1. **Headless Unit Tests (`tests/terminal/`):** Fast, non-visual assertion suites executed in headless mode (`windowType='none'`).
2. **Interactive In-Engine Sandboxes (`tests/panda/`):** Visual 3D testbeds where each gameplay subsystem is isolated, observed, and manipulated in real time.

---

## 2. Base Sandbox Architecture (`tests/__test.py`)

All visual sandboxes inherit from `Test` (which extends `Scene`):

```python
class Test(Scene):
    """Base class for all interactive sandbox test scenes."""
    
    def on_start(self) -> None:
        """Sets up default ground, basic lighting, and debug keybindings."""
        super().on_start()
        self._setup_default_environment()
        self._setup_debug_keys()
```

### 2.1 Default Sandbox Features
Every sandbox automatically provides:
* **Neutral Grid / Ground:** A static floor plane with Bullet physics enabled.
* **Default Lighting:** Directional + ambient lights configured via `GlobalLights`.
* **Physics Wireframe Toggle:** Pressing `F12` toggles the Bullet debug wireframe overlay.
* **Camera Freecam / Reset:** Pressing `F1` toggles between free spectator camera and test camera.
* **Lifecycle Cleanup:** Guarantees removal of all spawned geometry, nodes, and physics bodies when leaving the scene.

---

## 3. Catalog of Planned In-Engine Sandboxes

| Suite File | Sandbox Target | Test Objectives |
| :--- | :--- | :--- |
| `tests/panda/physics_sandbox.py` | `Physics` & `RigidBodyHandler` | Collision restitution, mass differences, falling stacks, sloped ramps. |
| `tests/panda/character_sandbox.py` | `CharacterControllerHandler` | Walking, stairs (step climbing up to 0.5m), jumping, gravity, slope sliding. |
| `tests/panda/triggers_sandbox.py` | `TriggerZoneHandler` | Dynamic entry/stay/exit events, group filters (Player vs Enemy vs Default). |
| `tests/panda/animation_sandbox.py` | `ActorAnimationHandler` | Clip playback, velocity-driven state transitions (Idle -> Walk -> Run). |
| `tests/panda/camera_sandbox.py` | `ThirdPersonCameraHandler` | Target follow lerp, mouse orbit, collision spring-arm against test walls. |
| `tests/panda/ai_sandbox.py` | AI Behavior Handlers | Patrol paths, line-of-sight raycasts, target chasing. |

---

## 4. Test Execution Modes

### 4.1 Interactive Visual Mode
Run directly with a graphical window:
```bash
python main.py
```
Switches target suite via configuration or runtime hotkeys.

### 4.2 Headless Automated Mode
Runs the test suite without initializing a display server (suitable for terminal workflows, automated agent verification, and CI):
```bash
python -m tests.terminal.run_all
```
Each headless test runs simulated ticks (`world.doPhysics(dt)`) and confirms state assertions without opening a window.
