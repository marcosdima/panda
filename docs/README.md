# Documentation

Every general feature of the engine is documented in its own file. This page is the map: it says where each topic lives and which rule keeps the documentation from turning into a monolith.

## Map

| Area | Document | Covers |
| --- | --- | --- |
| Engine | [architecture.md](architecture.md) | How the pieces fit together: layers, ownership, communication patterns. |
| Engine | [engine/README.md](engine/README.md) | Index of the engine subsystems. |
| Engine | [engine/update_pipeline.md](engine/update_pipeline.md) | The per-frame phases and what may be written in each one. |
| Engine | [engine/physics_world.md](engine/physics_world.md) | The Bullet world: bodies, queries, masks. |
| Engine | [engine/tasks.md](engine/tasks.md) | Task registration and ownership. |
| Engine | [engine/entities_scenes.md](engine/entities_scenes.md) | `Entity` and `Scene` lifecycle and messaging. |
| Handlers | [handlers/README.md](handlers/README.md) | Index of the handler areas, how to choose one, attach order. |
| Handlers | [handlers/pattern.md](handlers/pattern.md) | The Handler contract: lifecycle hooks, composition rules, checklist. |
| Handlers | [handlers/input.md](handlers/input.md) | Keyboard/mouse input, `ActionMap`, parameter adjustment. |
| Handlers | [handlers/physics.md](handlers/physics.md) | Character controller, rigid bodies, trigger zones, collision groups. |
| Handlers | [handlers/camera.md](handlers/camera.md) | First and third person cameras, presets, occlusion handling. |
| Handlers | [handlers/graphics.md](handlers/graphics.md) | Model and actor/animation handlers. |
| Handlers | [handlers/ai.md](handlers/ai.md) | Patrol brain, chase behaviour, line of sight, follow-at-distance brain. |
| Handlers | [handlers/sensors.md](handlers/sensors.md) | Distance-based proximity sensing, enter/stay/exit events, hysteresis. |
| Handlers | [handlers/components.md](handlers/components.md) | `PauseHandler`, `CameraControlComponent`, `CameraSettingsComponent`, `HealthHandler`, `SpawnerHandler`. |
| Testing | [testing/README.md](testing/README.md) | Test framework, headless suites, interactive sandboxes. |
| Utilities | [utils/README.md](utils/README.md) | `Event`, `GlobalEventBus`, `Cooldown`, math helpers, `StateMachine`, paths, world position. |
| Services | [services/README.md](services/README.md) | Service Locator for engine-wide resources. |
| Handlers | [handlers/capabilities.md](handlers/capabilities.md) | Protocol-based capability lookup on entities. |

## Editorial rules

- **One feature, one document.** A general feature (a handler area, a subsystem, a workflow) gets its own file. Reference tables such as the suite catalogs live in the index of their area instead of being spread across pages.
- **One fact, one home.** Each rule is stated once, in the document that owns it. Other documents link to it instead of restating it. The most repeated rules used to be the line-of-sight semantics, the camera split phase and the sandbox catalog; each now has a single owner.
- **Documents mirror the source tree.** `docs/handlers/` covers `src/handlers/`, `docs/engine/` covers `src/globals/`, `src/scenes/`, `src/entities/` and `src/game.py`, `docs/testing/` covers `tests/`, `docs/utils/` covers `src/utils/`.
- **Every document is verifiable.** It ends with the modules it describes (`Source:`) and the suites that cover them (`Tests:`), so a reader can go straight to the code and to the verification.
- **English.** All documentation is written in English, like the code.
- **Relative links.** Documents link to each other with relative paths so the tree stays portable.

## Writing a new document

1. Pick the area that owns the feature. If it does not fit any area, add it to the closest index and create a file next to it.
2. Start from the code, not from another document: copy the behaviour from the source and link to the sources of the rules you reuse.
3. Add the file to the index of its area and to the map above.
4. End the file with `Source:` and `Tests:` lines.

Source: `docs/`
Tests: `tests/`
