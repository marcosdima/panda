# Graphics and Animation Handlers

Graphics handlers own the visual representation of an entity. They never move it: the body belongs to the physics handler.

## `ModelHandler`

`src/handlers/graphics/model.py` loads static geometry (`.bam`, `.glb`, `.egg`).

| Parameter | Meaning |
| --- | --- |
| `model_path` | Path of the asset, resolved through `GlobalLoader`. |
| `scale` | Uniform scale applied to the instance. |
| `offset` | Positional offset of the instance. |
| `hpr` | Heading, pitch and roll of the instance. |

Behaviour:

- The template is resolved through `GlobalLoader`, which caches it, and the entity receives a deep `copyTo` instance. Entities sharing one asset never steal each other's nodes.
- A missing asset falls back to an empty placeholder and logs a warning instead of raising, so a scene keeps running.
- The instance is removed on stop and detach while the cached template stays; the model is rebuilt automatically if the entity restarts.

## `ActorAnimationHandler`

`src/handlers/graphics/actor.py` loads articulated models through Panda3D's `Actor` and drives their clips.

- Binds the animation clips to the entity and exposes `play_animation(name)`, `loop_animation(name)` and `stop_animation()`.
- `current_animation` returns the clip that is playing, and `get_anim_names()` lists the available ones.
- Locomotion is derived from the entity velocity: idle, walk and run, with the jump clip applied when the entity is not grounded. A missing clip falls back to the closest available state instead of failing.
- A manual override (`play_animation`) is honoured until the next state change reconciles it.
- `ActorAnimationHandler.kaykit_rig_medium(character=...)` builds a handler for the KayKit rig characters shipped with the project.
- The visual pivot is separated from the body node, so the mesh can be animated without touching the simulation.

## Asset loading

`GlobalLoader` (`src/globals/loader.py`) owns the cache.

- **`load(asset_path)`** — load any asset through the global Panda3D loader.
- **`load_from_assets(relative_path)`** — resolve under `config.ASSETS_PATH`.
- **`load_panda_asset(model_key)`** — load one of the models bundled with Panda3D.
- **`load_actor(asset_path, animations)`** — load an articulated model with its clips.

The `gltf` module is imported once by the loader so glTF support is registered before the first asset is read.

Source: `src/handlers/graphics/`, `src/globals/loader.py`
Tests: `tests/terminal/model_handler.py`, `tests/terminal/actor_animation.py`, `tests/terminal/actor_locomotion_test.py`
