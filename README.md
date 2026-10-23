# Panda

A modular 3D game framework built on [Panda3D](https://www.panda3d.org/) 1.10+ and Bullet physics, written in Python 3.12.

Entities are lightweight containers (`Entity`) composed of independent `Handler` components, so input, movement, cameras, animation and AI are attached and swapped without inheritance chains.

## Requirements

- Python 3.12
- Panda3D 1.10+ (`requirements.txt` pins `Panda3D==1.10.16`) plus `panda3d-gltf` for glTF assets

## Install

```bash
python3.12 -m venv venv
./venv/bin/pip install -r requirements.txt
```

## Run

| Command | What it does |
| --- | --- |
| `./venv/bin/python main.py` | Launches the engine with the suite selected by `TARGET` in `tests/__init__.py`. |
| `./scripts/run_tests_menu.sh` | Interactive menu over every suite and sandbox. `--run-default` runs the persisted default stored in `.test_default`. |
| `./scripts/run_test_menu.py` | Same idea driven by pytest, restricted to `tests/terminal`. |
| `windowType=none ./venv/bin/python -m tests.terminal.run_all` | Runs every headless suite and prints a summary. |

Headless suites must pass with `windowType=none`; interactive sandboxes under `tests/panda/` open a window.

## Repository layout

```
src/
  game.py          ShowBase wrapper: scenes and the per-frame pipeline
  entities/        Entity container and id pool
  scenes/          Scene lifecycle and task ownership
  globals/         Singletons: Physics, Loader, Camera, Clock, Tasks, Lights
  handlers/        Modular behaviour: input, physics, camera, graphics, ai, components, pause
  utils/           Event, math, cooldown, state machine, paths
  services/        Service locator registration
tests/
  terminal/        Headless suites (pytest and in-engine)
  panda/           Interactive sandboxes
docs/              Documentation, one document per feature
```

## Documentation

Start at [docs/README.md](docs/README.md).

| Area | Document |
| --- | --- |
| Engine overview | [docs/architecture.md](docs/architecture.md) |
| Handler areas | [docs/handlers/README.md](docs/handlers/README.md) |
| Handler pattern | [docs/handlers/pattern.md](docs/handlers/pattern.md) |
| Frame pipeline | [docs/engine/update_pipeline.md](docs/engine/update_pipeline.md) |
| Physics world | [docs/engine/physics_world.md](docs/engine/physics_world.md) |
| Tasks | [docs/engine/tasks.md](docs/engine/tasks.md) |
| Entities and scenes | [docs/engine/entities_scenes.md](docs/engine/entities_scenes.md) |
| Testing | [docs/testing/README.md](docs/testing/README.md) |
| Utilities | [docs/utils/README.md](docs/utils/README.md) |

## License

See [LICENSE](LICENSE).

Source: `src/`
Tests: `tests/`
