# Frame Update Pipeline

Every frame the engine runs three tasks in a fixed order. The order is the contract: a handler that writes something another handler reads in the same frame must know which phase it happens in.

| Order | Task | Sort | Owner | What happens |
| --- | --- | --- | --- | --- |
| 1 | `game_scene_update` | `-5` | `Game` | `scene.on_update(dt)` for the main scene. Handlers read input, write intent and decide. |
| 2 | `physics_world_updater` | `0` | `Physics` | `world.doPhysics(dt)`. The simulation advances and the bodies reach their new positions. |
| 3 | `game_post_update` | `1` | `Game` | `scene.on_post_update(dt)` for the main scene. Handlers read the final positions and write the transforms that depend on them. |

The sorts are constants on `Game`: `UPDATE_TASK_SORT = -5`, `POST_UPDATE_TASK_SORT = 1`. The physics task uses the default sort of `0`. A task registered without an explicit sort runs at `0`, so it is interleaved with the physics step: **always give a sort when the order matters**.

## The rule

- **Intent goes in `on_update`.** Input is read, actions are queried, decisions are taken and movement intent is written. Everything written here is visible to the physics step that follows.
- **Transforms that depend on the simulation go in `on_post_update`.** A camera that follows the player must read the position the physics step has just produced, otherwise it shows the previous frame's position and lags one frame behind.

```python
class FollowerCamera(Handler):
    def on_update(self, dt: float) -> None:
        self.yaw = self.read_look()          # input-driven, needed before physics

    def on_post_update(self, dt: float) -> None:
        self.camera.setPos(self.target_pos)  # depends on the physics result
```

Writing the transform in `on_update` is not wrong in a vacuum, it is wrong when the value depends on the body: the body has not moved yet at that point.

## Reading the clock

Both engine tasks use `GlobalClock.get_dt()`, the delta time of the global Panda3D clock. Handlers receive that same `dt`; they never read the clock themselves.

## Pausing

`Game.set_paused(True)` stops the dispatch of both phases for the main scene. The physics task is a separate global task and keeps running, so a paused scene freezes its handlers while the world stays consistent. `PauseHandler` drives that flag from the pause menu (see [../handlers/components.md](../handlers/components.md)).

## Scenes

Only the main scene is dispatched. `Game.set_main_scene(scene_id)` stops the previous scene, which frees its entities and removes the tasks it owned, and starts the new one.

Source: `src/game.py`, `src/scenes/__scene.py`, `src/entities/entity.py`, `src/globals/physics.py`
Tests: `tests/terminal/game_update_test.py`, `tests/terminal/post_update_test.py`
