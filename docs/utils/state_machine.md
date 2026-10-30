# state_machine (`src/utils/state_machine.py`)

`StateMachine(initial, transitions=None)` is a small FSM.

- `transitions`: `{state: [allowed targets]}`; `None` allows any transition.
- `state`, `can_transition(target)`, `transition(target)` (raises `ValueError` if not allowed; same-state is a no-op returning `False`).
- `on_exit(state, cb)` runs before leaving, `on_enter(state, cb)` after entering; both receive `(previous, new)`.
- `reset(state)`: sets the state without hooks or validation of transitions (hooks are kept).
- Hooks must not call `transition()`; a nested call raises `RuntimeError`.

```python
sm = StateMachine("idle", {"idle": ["walk"], "walk": ["idle"]})
sm.on_enter("walk", lambda prev, new: print("walking"))
sm.transition("walk")
```

Source: `src/utils/state_machine.py`
Tests: `tests/terminal/state_machine_test.py`.
