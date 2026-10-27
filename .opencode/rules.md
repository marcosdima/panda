# Project Rules - Panda 3D Game Engine

Authoritative operating rules for every agent and developer working in this repository.
opencode loads this file through `opencode.json` -> `instructions`.

---

## 1. Project overview and philosophy

Modular 3D game framework built on **Panda3D (1.10+)** and **Bullet Physics**, written in **Python 3.12**.

### Core philosophy: composition over inheritance

* **Entities are lightweight containers:** an `Entity` is essentially a unique id, a Panda3D `NodePath`, and a collection of attached `Handler` instances.
* **Handlers encapsulate behavior:** movement, physics, input, animation, camera and game logic live in independent `Handler` components. Never add behavior by subclassing `Entity` with multiple inheritance.
* **Headless-first compatibility:** core engine classes, math utilities and logic must work without an active graphical window (`windowType='none'`).

---

## 2. Coding and language standards

* **Language:** all code, comments, docstrings, tests, commit messages and documentation are written in **English**.
* **Type annotations:** every function and method declares explicit parameter and return types.
* **Docstrings:** concise, descriptive docstrings for public classes, interfaces and methods.
* **Clean cleanup (no leaks):**
  * every created `NodePath` is detached or removed with `removeNode()` during cleanup;
  * every Bullet physics body or ghost is explicitly removed from the `BulletWorld`;
  * every task registered in `taskMgr` is removed when the scene or the entity stops;
  * cached assets are released through their owner (`GlobalLoader`), not by dropping references.
* **Error handling:** no bare `except:`. Catch specific exceptions and log them.

---

## 3. Architecture and directory structure

```
├── opencode.json            # opencode project config (permissions, instructions)
├── .opencode/               # opencode agents, skills and rules
├── docs/                    # Architectural specs, handler contracts, testing guides
├── assets/                  # 3D models (.glb), animations, textures, sounds
├── config.py                # Global configurations and asset path constants
├── main.py                  # Entry point to launch the engine and testbeds
├── src/
│   ├── game.py              # Main ShowBase engine wrapper and Scene manager
│   ├── globals/             # Global singletons (Physics, Loader, Camera, Clock, Tasks, Lights)
│   ├── scenes/              # Scene base class and scene lifecycle
│   ├── entities/            # Entity container and core entity registry
│   ├── handlers/            # Modular Handler implementations (base, input, physics, camera, etc.)
│   └── utils/               # Utilities (Event, math helpers, debug tools)
└── tests/
    ├── __test.py            # Base Test / Sandbox scene class with terminal formatting
    ├── terminal/            # Headless unit tests (lifecycle, ID allocation, events)
    └── panda/               # Interactive visual testbeds (physics, models, areas, controllers)
```

`docs/` mirrors the source tree: `docs/handlers/` covers `src/handlers/`, `docs/engine/` covers `src/globals/`, `src/scenes/`, `src/entities/` and `src/game.py`, `docs/testing/` covers `tests/`, `docs/utils/` covers `src/utils/`.

---

## 4. Handler lifecycle contract

Every handler inherits from `Handler` (`src/handlers/base.py`) and participates in the standard lifecycle:

1. `on_attach(entity: Entity) -> None`: the handler is added to an entity; store the entity reference.
2. `on_start() -> None`: the entity or the active scene begins execution.
3. `on_update(dt: float) -> None`: called every frame with the delta time.
4. `on_stop() -> None`: the scene stops or the entity is deactivated.
5. `on_detach() -> None`: the handler is removed from the entity or the entity is freed.

---

## 5. Mandatory testing policy

* **No blind implementations:** no feature or handler is complete without a corresponding headless test or sandbox scene.
* **Headless verification:** all unit tests in `tests/terminal/` must execute and pass headless (`windowType='none'`).
* **Visual sandboxes:** when creating or modifying mechanics (character movement, physics triggers, camera orbit), create an isolated scene subclassing `Test` / `TestScene` under `tests/panda/`.

Commands:

```bash
# batch validation (mechanical checks + full suite); run before review
./scripts/run_batch_validation.sh

# full headless suite
./venv/bin/python -m tests.terminal.run_all

# a single suite
./venv/bin/python -m tests.terminal.<suite>

# interactive playground
./venv/bin/python -m tests.playground

# the game
./venv/bin/python main.py

# diagnostics
./venv/bin/python -m src.globals.physics --dump
```

---

## 6. Documentation rules

The full editorial contract lives in `docs/README.md`; do not restate it here.

* **One fact, one home:** each rule is stated once, in the document that owns it. Other documents link to it.
* **Every document is verifiable:** it ends with the modules it describes (`Source:`) and the suites that cover them (`Tests:`).
* **Relative links** between documents so the tree stays portable.
* **English**, like the code.

Before changing behavior or a public interface, read the owning document through the `docs-retrieval` skill. If the document and the source disagree, the document is stale: report it and fix the owner document instead of adding a second copy of the rule.

---

## 7. Agent operating rules

* The **lead** is the sole author of production code.
* **Specialists never write production code.** `reviewer` and `research` are strictly read-only; `tester` may only create or modify files under `tests/`.
* Specialists contribute judgment, coverage and observation, never a competing implementation. The lead remains responsible for the result, whatever a specialist reported.
* **Reviews are per feature batch, not per edit.** The lead finishes code, tests and documentation for a feature, runs `./scripts/run_batch_validation.sh`, and only then invokes `reviewer`. Mechanical findings belong to the scripts; the reviewer spends its budget on architecture, contracts and residual risk.
* **Every subagent prompt is self-contained:** exact objective, files and ownership boundary, expected behavior, existing patterns to follow, constraints (what not to modify) and expected validation.
* In opencode a subagent cannot spawn another subagent. The lead invokes `reviewer` and `tester` through the `subagent` tool; `research` only returns proposals and never starts the chain on its own.

---

## 8. Boundaries that require the user

Stop and consult the user before:

* replacing a major engine concept;
* changing the responsibilities between `Game`, scenes and handlers;
* altering a public interface documented in `docs/`;
* changing the handler lifecycle contract or the per-frame update phases.

Before modifying an exported class or function, search its usages, understand its contract, check the docs and keep backward compatibility unless the user approves otherwise.

---

## 9. Git commit protocol

Atomic commits following the **Conventional Commits** specification:

* `feat(...)`: new features, handlers or subsystem capabilities.
* `fix(...)`: bug fixes or regressions.
* `refactor(...)`: refactoring without changing observable behavior.
* `docs(...)`: documentation additions or updates.
* `test(...)`: new testbeds, sandboxes or unit tests.
* `chore(...)`: maintenance, dependency updates or configuration adjustments.

Never commit secrets, and review `git status` and the final diff before committing.
