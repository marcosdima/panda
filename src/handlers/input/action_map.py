from __future__ import annotations
from src.utils.handler_phase import HandlerPhase

from typing import Callable, Iterable, Mapping

from panda3d.core import ButtonHandle, KeyboardButton, MouseButton

MOVE_FORWARD = "move_forward"
MOVE_BACK = "move_back"
MOVE_LEFT = "move_left"
MOVE_RIGHT = "move_right"
JUMP = "jump"
SPRINT = "sprint"
MOVEMENT_ACTIONS: tuple[str, ...] = (MOVE_FORWARD, MOVE_BACK, MOVE_LEFT, MOVE_RIGHT)

DEFAULT_BINDINGS: dict[str, tuple[str, ...]] = {
    MOVE_FORWARD: ("w", "up"),
    MOVE_BACK: ("s", "down"),
    MOVE_LEFT: ("a", "left"),
    MOVE_RIGHT: ("d", "right"),
    JUMP: ("space",),
    SPRINT: ("lshift",),
}

_NAMED_BUTTONS: dict[str, Callable[[], ButtonHandle]] = {
    "space": KeyboardButton.space,
    "lshift": KeyboardButton.lshift,
    "rshift": KeyboardButton.rshift,
    "lcontrol": KeyboardButton.lcontrol,
    "rcontrol": KeyboardButton.rcontrol,
    "lalt": KeyboardButton.lalt,
    "ralt": KeyboardButton.ralt,
    "up": KeyboardButton.up,
    "down": KeyboardButton.down,
    "left": KeyboardButton.left,
    "right": KeyboardButton.right,
    "enter": KeyboardButton.enter,
    "tab": KeyboardButton.tab,
    "escape": KeyboardButton.escape,
    "backspace": KeyboardButton.backspace,
    "mouse1": MouseButton.one,
    "mouse2": MouseButton.two,
    "mouse3": MouseButton.three,
}


def resolve_button(key: str) -> ButtonHandle:
    """Translate a key name (``"w"``, ``"space"``, ``"mouse1"``...) into a Panda3D ButtonHandle."""
    name = key.lower()
    factory = _NAMED_BUTTONS.get(name)
    if factory is not None:
        return factory()
    if len(name) == 1:
        return KeyboardButton.ascii_key(name)
    raise ValueError(f"Unknown input key name: {key!r}")


class ActionMap:
    phase = HandlerPhase.INPUT
    """Maps logical action names to configurable physical keys, decoupled from any handler.

    The map is hardware-agnostic at the query level: ``is_down`` receives a
    ``is_button_down(ButtonHandle) -> bool`` callable (e.g. ``MouseWatcher.is_button_down``),
    so it can be exercised headless with a fake predicate.
    """

    def __init__(self, bindings: Mapping[str, Iterable[str]] | None = None) -> None:
        self._bindings: dict[str, list[ButtonHandle]] = {}
        self._names: dict[str, list[str]] = {}
        source = DEFAULT_BINDINGS if bindings is None else bindings
        for action, keys in source.items():
            for key in keys:
                self.bind(action, key)

    @classmethod
    def default(cls) -> "ActionMap":
        """Return a map with the standard WASD/arrows + Space + LShift bindings."""
        return cls(DEFAULT_BINDINGS)

    @property
    def actions(self) -> list[str]:
        """Names of all actions that currently have at least one binding."""
        return [a for a, keys in self._names.items() if keys]

    def keys_for(self, action: str) -> list[str]:
        """Return the key names bound to ``action``."""
        return list(self._names.get(action, []))

    def bind(self, action: str, key: str) -> None:
        """Add ``key`` to ``action`` (no-op if already bound)."""
        key = key.lower()
        names = self._names.setdefault(action, [])
        if key in names:
            return
        handle = resolve_button(key)
        names.append(key)
        self._bindings.setdefault(action, []).append(handle)

    def unbind(self, action: str, key: str | None = None) -> None:
        """Remove one key from ``action``, or every key when ``key`` is None."""
        if key is None:
            self._names.pop(action, None)
            self._bindings.pop(action, None)
            return
        key = key.lower()
        names = self._names.get(action, [])
        if key in names:
            index = names.index(key)
            names.pop(index)
            self._bindings[action].pop(index)

    def rebind(self, action: str, keys: Iterable[str]) -> None:
        """Replace all keys of ``action`` with ``keys``."""
        self.unbind(action)
        for key in keys:
            self.bind(action, key)

    def is_down(self, action: str, is_button_down: Callable[[ButtonHandle], bool]) -> bool:
        """Return True if any key bound to ``action`` is currently down."""
        return any(is_button_down(button) for button in self._bindings.get(action, ()))
