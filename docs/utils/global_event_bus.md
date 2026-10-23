# Global Event Bus

`GlobalEventBus` (`src/utils/global_event_bus.py`) is an engine-wide event bus
built on top of `Event` (`src/utils/event.py`). It publishes and subscribes to
named events without requiring an entity owner, filling the gap for engine-wide
or cross-entity events such as `level_completed`, `game_paused` or
`auto_save` that do not belong to any single entity.

Unlike the `Global*` singletons in `src/globals/` (resolved lazily through
`builtins.base` as described in [../engine/README.md](../engine/README.md)),
this bus is a plain module-level instance named `bus`. It is **not** a
`Global` subclass and is not resolved through `builtins.base`; it is registered
in the service locator under the key `events` (see
[../engine/README.md#service-locator](../engine/README.md)).

## When to use it

Use the bus for:

- **Owner-less events:** nothing in the scene owns the event (e.g. UI state,
  audio cues, save/load triggers).
- **Cross-entity communication:** two entities that should not hold references
  to each other react to the same named event.

Keep using `entity.get_handler(HandlerType)` for handlers that share an entity;
the bus is complementary, not a replacement for direct handler collaboration
on the same entity. See the delivery semantics in
[event.md](event.md) and the communication rules in
[../architecture.md](../architecture.md).

## Public interface

```python
class GlobalEventBus:
    def subscribe(self, event_name: str, callback: Callable[..., None], priority: int = 0) -> None
    def subscribe_once(self, event_name: str, callback: Callable[..., None], priority: int = 0) -> None
    def unsubscribe(self, event_name: str, callback: Callable[..., None]) -> None
    def publish(self, event_name: str, *args: Any, **kwargs: Any) -> None
    def has_listeners(self, event_name: str) -> bool
    def clear(self, event_name: str | None = None) -> None
```

A default engine-wide instance is exported as `bus` from `src.utils`:

```python
from src.utils import bus

bus.subscribe("level_completed", lambda level: print(f"Done: {level}"))
bus.publish("level_completed", 3)
```

## Delivery semantics

Delivery matches [`Event`](event.md) exactly — see that document for priority
order, argument arity, once-only removal and snapshot dispatch.

## Callable equality

Callbacks are matched by **callable equality** (the same callable object, or an
equal one such as a bound method). The same callable passed to `subscribe` must
be passed to `unsubscribe`; a freshly-created lambda or closure will silently
fail to match.

## Mandatory lifecycle contract

Any handler or scene that subscribes to the bus **must** unsubscribe in its
`on_stop` / `on_detach` hook (or `Scene.on_stop`). Otherwise:

- the bus keeps a strong reference to the callback, which keeps its handler,
  entity and nodes alive past the scene lifetime (a leak);
- on scene reload, callbacks accumulate and fire multiple times.

```python
def on_stop(self) -> None:
    bus.unsubscribe("level_completed", self._on_level_completed)
    super().on_stop()
```

Source: `src/utils/global_event_bus.py`, `src/utils/event.py`, `src/utils/__init__.py`, `src/services/initializers.py`
Tests: `tests/terminal/global_event_bus_test.py`
