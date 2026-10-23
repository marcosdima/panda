# event (`src/utils/event.py`)

`Event` is a prioritised callback dispatcher.

- `add_callback(cb, priority=0)`: higher priority runs first.
- `add_once(cb, priority=0)`: removed automatically after its first run.
- `remove_callback(cb)`, `clear_callbacks()`, `len(event)`.
- `set_check(fn)` / `working()`: when the check returns false, calling the event does nothing.
- `event(*args, **kwargs)`: callbacks declaring no parameters are called without arguments; the rest receive them. Arity is inspected once in `add_callback`, not on every call.
- Callbacks may add or remove callbacks during dispatch (iteration uses a snapshot; removed callbacks are skipped).

Source: `src/utils/event.py`
Tests: `tests/terminal/event_test.py`.
