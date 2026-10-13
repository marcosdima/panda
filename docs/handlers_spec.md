# Handler Architecture Specification

## 1. Concept

A `Handler` is a modular component responsible for a single piece of behavior or system integration (e.g., input handling, character controller physics, camera tracking, animation playback).

Instead of deriving complex entity classes via multiple inheritance, entities are composed dynamically:

```python
player = Entity("Player")
player.add_handler(WASDInputHandler())
player.add_handler(CharacterPhysicsHandler(mass=75.0, height=1.8))
player.add_handler(ActorAnimationHandler(model_path="X Bot.glb"))
player.add_handler(ThirdPersonCameraHandler())
```

---

## 2. Base Handler Interface (`src/handlers/base.py`)

All handlers must inherit from `Handler`:

```python
from abc import ABC
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.entities.entity import Entity

class Handler(ABC):
    """Base class for all modular entity handlers."""
    
    def __init__(self) -> None:
        self.entity: 'Entity | None' = None
        self._enabled: bool = True

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def on_attach(self, entity: 'Entity') -> None:
        """Called when this handler is added to an entity."""
        self.entity = entity

    def on_detach(self) -> None:
        """Called when this handler is removed from an entity or the entity is freed."""
        self.entity = None

    def on_start(self) -> None:
        """Called when the scene starts or the entity is activated."""
        pass

    def on_update(self, dt: float) -> None:
        """Frame update hook called every tick if the handler is enabled."""
        pass

    def on_stop(self) -> None:
        """Called when the scene stops or the entity is deactivated."""
        pass
```

---

## 3. Handler Categories & Responsibilities

### 3.1 Input Handlers (`src/handlers/input/`)
* **`InputHandler` (Base):** Tracks keystrokes, mouse axes, and gamepads. Exposes `move_vector: Vec2` and action states (`jump`, `sprint`, `interact`).
* **`WASDInputHandler`:** Standard PC keyboard input mapping.

### 3.2 Physics Handlers (`src/handlers/physics/`)
* **`CharacterControllerHandler`:** Encapsulates Panda3D's `BulletCharacterControllerNode`. Manages linear velocity, walking on slopes, step climbing, jumping, and gravity.
* **`RigidBodyHandler`:** Encapsulates standard `BulletRigidBodyNode` for dynamic props (mass > 0) or static terrain (mass = 0).
* **`TriggerZoneHandler`:** Encapsulates `BulletGhostNode` for trigger volumes with `on_enter`, `on_stay`, and `on_exit` callbacks.

### 3.3 Camera Handlers (`src/handlers/camera/`)
* **`ThirdPersonCameraHandler`:** Orbits around the entity's position with mouse pitch/yaw control, collision raycast to avoid clipping through walls, and position lerp for smooth following.
* **`FirstPersonCameraHandler`:** Locks camera to character eye position and rotates with look angles.

### 3.4 Visual & Animation Handlers (`src/handlers/graphics/`)
* **`ModelHandler`:** Loads and reparents static geometry (`.bam` / `.glb` / `.egg`).
* **`ActorAnimationHandler`:** Loads articulated models via `Actor`, manages animation clips (`Idle`, `Walk`, `Run`), and provides blending / state machines driven by entity velocity.
