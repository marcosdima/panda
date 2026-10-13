# AGENTS.md - Panda3D 3D Game Engine Development Guidelines

Welcome to the **Panda 3D Game Engine** project. This document serves as the authoritative source of rules, architecture principles, and operating standards for all autonomous AI agents and developers working on this codebase.

---

## 1. Project Overview & Philosophy

This project is a modular 3D game framework built on **Panda3D (1.10+)** and **Bullet Physics**, written in **Python 3.12**.

### Core Philosophy: Composition over Inheritance
* **Entities are Lightweight Containers:** An `Entity` is primarily a unique ID, a Panda3D `NodePath`, and a collection of attached `Handler` instances.
* **Handlers Encapsulate Behavior:** All movement, physics, input, animation, camera, and game logic MUST be implemented as independent `Handler` components, never by subclassing `Entity` with multiple inheritance.
* **Headless-First Compatibility:** Core engine classes, mathematical utilities, and logic MUST function without requiring an active graphical window (`windowType='none'`).

---

## 2. Coding & Language Standards

* **Language:** All code, comments, docstrings, tests, commit messages, and documentation MUST be in **English**.
* **Type Annotations:** All functions and methods MUST have explicit type annotations for parameters and return types.
* **Docstrings:** Use concise, descriptive docstrings for public classes, interfaces, and methods.
* **Clean Cleanup (No Memory Leaks):**
  * Every created `NodePath` must be detached or removed with `removeNode()` during cleanup.
  * Every Bullet physics body/ghost must be explicitly removed from `BulletWorld`.
  * Every task registered in `taskMgr` must be removed when the scene or entity stops.
* **Error Handling:** Avoid bare `except:`. Always log or handle specific exceptions.

---

## 3. Architecture & Directory Structure

```
├── AGENTS.md                  # Authoritative agent rules and development guidelines
├── docs/                      # Architectural specs, handler contracts, testing guides
├── assets/                    # 3D models (.glb), animations, textures, sounds
├── config.py                  # Global configurations and asset path constants
├── main.py                    # Entry point to launch the engine and testbeds
├── src/
│   ├── game.py                # Main ShowBase engine wrapper and Scene manager
│   ├── globals/               # Global singletons (Physics, Loader, Camera, Clock, Tasks, Lights)
│   ├── scenes/                # Scene base class and scene lifecycle
│   ├── entities/              # Entity container and core entity registry
│   ├── handlers/              # Modular Handler implementations (base, input, physics, camera, etc.)
│   └── utils/                 # Utilities (Event, math helpers, debug tools)
└── tests/
    ├── __test.py              # Base Test / Sandbox scene class with terminal formatting
    ├── terminal/              # Headless unit tests (lifecycle, ID allocation, events)
    └── panda/                 # Interactive visual testbeds (physics, models, areas, controllers)
```

---

## 4. Handler Lifecycle Contract

Every handler must inherit from `Handler` (`src/handlers/base.py`) and participate in the standard lifecycle:
1. `on_attach(entity: Entity) -> None`: Called when the handler is added to an entity. Store entity reference.
2. `on_start() -> None`: Called when the entity or active scene begins execution.
3. `on_update(dt: float) -> None`: Called every frame with delta time.
4. `on_stop() -> None`: Called when the scene stops or the entity is deactivated.
5. `on_detach() -> None`: Called when the handler is removed from the entity or the entity is freed.

---

## 5. Mandatory Testing Policy (In-Engine Sandboxes)

* **No Blind Implementations:** No feature or handler is complete without a corresponding testbed scene or headless test.
* **Visual Sandboxes (`tests/panda/`):** When creating or modifying mechanics (e.g., character movement, physics triggers, camera orbit), create an isolated test scene subclassing `Test` / `TestScene` to verify behavior visually.
* **Headless Verification:** All unit tests in `tests/terminal/` must execute and pass in headless mode (`windowType='none'`).

---

## 6. Git Commit Protocol

Make atomic commits using the **Conventional Commits** specification:
* `feat(...)`: New features, handlers, or subsystem capabilities.
* `fix(...)`: Bug fixes or regressions.
* `refactor(...)`: Code refactoring without changing observable behavior.
* `docs(...)`: Documentation additions or updates.
* `test(...)`: New testbeds, sandboxes, or unit tests.
* `chore(...)`: Maintenance, dependency updates, or configuration adjustments.
