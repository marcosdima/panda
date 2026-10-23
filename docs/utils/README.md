# Utils

Reusable helpers in `src/utils`, exported from `src.utils`.

| Module | Doc | Summary |
| --- | --- | --- |
| `event.py` | [event.md](event.md) | `Event` callback dispatcher |
| `global_event_bus.py` | [global_event_bus.md](global_event_bus.md) | Engine-wide `GlobalEventBus` on top of `Event` |
| `cooldown.py` | [cooldown.md](cooldown.md) | `Cooldown` timer tracker |
| `math.py` | [math.md](math.md) | `clamp`, `lerp`, `smoothstep`, `normalize_angle`, `lerp_angle`, `remap` |
| `state_machine.py` | [state_machine.md](state_machine.md) | `StateMachine` FSM |
| `paths.py` | [paths.md](paths.md) | `get_project_root`, `resolve_asset_path` |
| `position.py` | [position.md](position.md) | `world_position` authoritative entity position |

One file per module; add new docs here and link them in this table.

Source: `src/utils/`
Tests: `tests/terminal/`
