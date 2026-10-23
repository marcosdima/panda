# Prefabs & Quickstart

Reduce composition noise with a thin `EntityBuilder` and ready-made prefabs.

## EntityBuilder (thin composer)

```python
from src.prefabs import EntityBuilder

entity = (
    EntityBuilder("Player")
    .at(0, 0, 2)
    .parented_to(render)
    .with_input()
    .with_character()
    .with_animation(kaykit="Knight")
    .with_camera("third_person")
    .build(scene)
)
```

`build()` applies parent/position and calls `Entity.add_handler` in the order
the `with_*` methods were invoked. `with_handler(any_handler)` is the escape
hatch for handlers without a named helper.

## Prefabs

```python
from src.prefabs import create_player, create_patrol_npc, create_static_prop

player = create_player(position=(0, 0, 2))
npc = create_patrol_npc(waypoints=[Vec3(0, 0, 0), Vec3(5, 0, 0)])
prop = create_static_prop(model_path="X Bot.glb")
```

Each prefab returns a small typed rig (`PlayerRig`, `NpcRig`) or an `Entity`,
hiding internal handlers while keeping references for telemetry.

## 10-minute mini game

1. Create ground + player + 2 NPCs + a prop using the calls above.
2. Start the scene and run the update loop.
3. Inspect telemetry via the rig references.

Source: `src/prefabs/`
Tests: `tests/terminal/prefab_smoke_test.py`