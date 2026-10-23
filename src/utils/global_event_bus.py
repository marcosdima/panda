"""Engine-wide event bus built on top of :class:`src.utils.event.Event`.

Publishes and subscribes to named events without requiring an entity owner.
Intended for engine-wide or cross-entity events such as ``level_completed``,
``game_paused`` or ``auto_save`` that do not belong to any single entity.

Unlike the ``Global*`` singletons in ``src/globals/`` (which are resolved
through ``builtins.base``), this bus is a plain module-level instance named
``bus``. It is *not* registered as a `Global` and does not depend on ShowBase.
"""

from __future__ import annotations

from typing import Any, Callable

from .event import Event


class GlobalEventBus:
    """Engine-wide event bus built on top of :class:`Event`.

    Subscribers are matched by **callable equality**: the same callable object
    (or an equal one, such as a bound method) passed to :meth:`subscribe`
    must be passed to :meth:`unsubscribe`. A freshly-created lambda or closure
    will not match.

    Handlers that share an entity should keep using
    ``entity.get_handler(HandlerType)``; this bus is for cross-entity and
    owner-less communication, not a replacement for direct handler
    collaboration on the same entity.

    Any subscriber added from a handler or scene **must** unsubscribe in
    :meth:`~src.handlers.base.Handler.on_stop` / :meth:`~src.handlers.base.Handler.on_detach`
    (or :meth:`~src.scenes.__scene.Scene.on_stop`) to avoid keeping entities
    and nodes alive past the scene lifetime and to prevent duplicate
    subscriptions on scene reload.
    """

    def __init__(self) -> None:
        self._events: dict[str, Event] = {}

    def _get_or_create(self, event_name: str) -> Event:
        """Return the named :class:`Event`, creating it on first use."""
        event = self._events.get(event_name)
        if event is None:
            event = Event()
            self._events[event_name] = event
        return event

    def subscribe(
        self,
        event_name: str,
        callback: Callable[..., None],
        priority: int = 0,
    ) -> None:
        """Subscribe ``callback`` to ``event_name`` with optional priority."""
        self._get_or_create(event_name).add_callback(callback, priority)

    def subscribe_once(
        self,
        event_name: str,
        callback: Callable[..., None],
        priority: int = 0,
    ) -> None:
        """Subscribe ``callback`` to ``event_name`` for a single delivery."""
        self._get_or_create(event_name).add_once(callback, priority)

    def unsubscribe(
        self,
        event_name: str,
        callback: Callable[..., None],
    ) -> None:
        """Remove ``callback`` from ``event_name`` if subscribed."""
        event = self._events.get(event_name)
        if event is not None:
            event.remove_callback(callback)

    def publish(self, event_name: str, *args: Any, **kwargs: Any) -> None:
        """Publish ``event_name``, delivering ``*args`` and ``**kwargs`` to listeners."""
        event = self._events.get(event_name)
        if event is not None:
            event(*args, **kwargs)

    def has_listeners(self, event_name: str) -> bool:
        """Return True if ``event_name`` has at least one subscriber."""
        event = self._events.get(event_name)
        return event is not None and len(event) > 0

    def clear(self, event_name: str | None = None) -> None:
        """Clear listeners for ``event_name``, or all events when omitted."""
        if event_name is None:
            self._events.clear()
        else:
            self._events.pop(event_name, None)


# Engine-wide default instance. Import and reuse this from any module.
bus = GlobalEventBus()
