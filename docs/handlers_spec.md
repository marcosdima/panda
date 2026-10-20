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
* **`CharacterControllerHandler`:** Encapsulates Panda3D's `BulletCharacterControllerNode`. Manages linear velocity, walking on slopes, step climbing, jumping, and gravity. Accepts a `CollisionGroup` label used by trigger filtering.
* **`RigidBodyHandler`:** Encapsulates standard `BulletRigidBodyNode` for dynamic props (mass > 0) or static terrain (mass = 0). Applies velocity, forces, and impulses. Each `on_update` propagates `entity.node` transform changes into Bullet (parent-change detection → `setTransformDirty`), so scene-driven moves are adopted on the next physics step while untouched bodies remain under Bullet's control.
* **`TriggerZoneHandler`:** Encapsulates `BulletGhostNode` for trigger volumes with `on_enter`, `on_stay`, `on_exit`, and `on_rejected` callbacks. Overlaps are filtered by each entity's `CollisionGroup` (`target_groups` / `avoid_groups`); selective zones (explicit `target_groups`) skip ambient `CollisionGroup.DEFAULT` environment overlaps (e.g. ground under a floating zone, detected only through Bullet's inflated broadphase AABBs) so static scenery never emits event noise. The ghost has collision response disabled and is never tagged as a trigger itself (triggers never detect each other). Uses the same `entity.node` transform auto-sync as `RigidBodyHandler`.
* **`CollisionGroup` (Enum):** Semantic Python-side labels (`DEFAULT`, `PLAYER`, `ENEMY`) stored on physics handlers and consumed by trigger filters.

### 3.3 Camera Handlers (`src/handlers/camera/`)
* **`ThirdPersonCameraHandler`:** Orbits around the entity's position with mouse pitch/yaw control, collision raycast to avoid clipping through walls, and position lerp for smooth following.
* **`FirstPersonCameraHandler`:** Locks camera to character eye position and rotates with look angles.

### 3.4 Visual & Animation Handlers (`src/handlers/graphics/`)
* **`ModelHandler`:** Loads and reparents static geometry (`.bam` / `.glb` / `.egg`).
* **`ActorAnimationHandler`:** Loads articulated models via `Actor`, manages animation clips (`Idle`, `Walk`, `Run`), and provides blending / state machines driven by entity velocity.
