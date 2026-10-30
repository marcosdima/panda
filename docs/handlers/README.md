# Handlers

A `Handler` is a modular component responsible for a single piece of behaviour or system integration. Entities are composed dynamically instead of being subclassed with multiple inheritance, so the same entity can be a player, a patrolling NPC or a test dummy by swapping handlers.

The contract every handler follows is in [pattern.md](pattern.md). This page is the index of the available areas.

## Areas

| Area | Document | Handlers |
| --- | --- | --- |
| Pattern | [pattern.md](pattern.md) | `Handler` base class, lifecycle hooks, composition rules. |
| Input | [input.md](input.md) | `InputHandler`, `WASDInputHandler`, `ActionMap`, `ParameterAdjustHandler`. |
| Physics | [physics.md](physics.md) | `CharacterControllerHandler`, `RigidBodyHandler`, `TriggerZoneHandler`, `CollisionGroup`. |
| Camera | [camera.md](camera.md) | `FirstPersonCameraHandler`, `ThirdPersonCameraHandler`, camera presets. |
| Graphics | [graphics.md](graphics.md) | `ModelHandler`, `ActorAnimationHandler`. |
| AI | [ai.md](ai.md) | `AIPatrolHandler`, `PatrolState`, `AINavigationHandler`, `NavigationState`, `FollowHandler`, `FollowState`. |
| Sensors | [sensors.md](sensors.md) | `ProximitySensorHandler`: distance-based enter/stay/exit detection without physics. |
| Components | [components.md](components.md) | `PauseHandler`, `CameraControlComponent`, `CameraSettingsComponent`, `HealthHandler`, `SpawnerHandler`. |
| Capabilities | [capabilities.md](capabilities.md) | `IntentSource`, `Mover`, `PhysicsBody`, `AnimationPlayer`, `CameraRig` Protocols. |

## Choosing a handler

- **Movement** comes from `CharacterControllerHandler`; it reads intent from an `InputHandler`.
- **Input** is a source of intent, not a source of movement. A player and an NPC both feed the same interface, which is what makes both drive the character controller identically.
- **Camera** handlers read the entity position and write to the camera node. They never move the entity.
- **Graphics** handlers own the visual representation only; they never move the entity either.
- **AI** handlers are virtual input sources: they write intent into an `InputHandler` instead of touching physics.
- **Sensors** only read positions and emit events; they never write intent or move anything.

## Attach order

Order matters when a handler consumes what another one writes in the same frame.

```python
entity = Entity("Npc")
entity.add_handler(InputHandler())            # 1. intent source
entity.add_handler(AIPatrolHandler(...))      # 2. writes intent into the input handler
entity.add_handler(CharacterControllerHandler())  # 3. consumes the intent
entity.add_handler(ThirdPersonCameraHandler())    # 4. reads the resulting position
```

- The AI handler must be attached **before** the movement handler, so the intent it writes is fresh on the same tick.
- Camera handlers are position consumers and must be attached after whatever produces the position they read.
- Two handlers of the same area on one entity are unusual; prefer one.
- The `SpawnerHandler` resolves its entity's `TriggerZoneHandler` in
  `on_start`. Attaching both before the entity starts is order-independent;
  the order matters when the spawner is added to an **already-active** entity:
  attach the trigger first, or the spawner never subscribes and never fires.

Source: `src/handlers/`
Tests: `tests/terminal/action_map_test.py`, `tests/terminal/actor_locomotion_test.py`, `tests/terminal/ai_test.py`, `tests/terminal/camera_handler.py`, `tests/terminal/character_controller.py`, `tests/terminal/follow_handler_test.py`, `tests/terminal/health_handler_test.py`, `tests/terminal/model_handler.py`, `tests/terminal/physics_handlers.py`, `tests/terminal/proximity_sensor_test.py`, `tests/terminal/spawner_handler_test.py`
