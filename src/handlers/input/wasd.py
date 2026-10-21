from __future__ import annotations

import builtins
from typing import TYPE_CHECKING
from panda3d.core import ButtonHandle, KeyboardButton, Vec2

from .base import InputHandler

if TYPE_CHECKING:
    from direct.showbase.ShowBase import ShowBase


class WASDInputHandler(InputHandler):
    """Input handler polling WASD, arrow keys, jump (Space), and sprint (LShift)."""

    def __init__(self) -> None:
        super().__init__()
        # Pre-cache ButtonHandles for fast per-frame polling
        self._btn_w: ButtonHandle = KeyboardButton.ascii_key("w")
        self._btn_s: ButtonHandle = KeyboardButton.ascii_key("s")
        self._btn_a: ButtonHandle = KeyboardButton.ascii_key("a")
        self._btn_d: ButtonHandle = KeyboardButton.ascii_key("d")
        self._btn_up: ButtonHandle = KeyboardButton.up()
        self._btn_down: ButtonHandle = KeyboardButton.down()
        self._btn_left: ButtonHandle = KeyboardButton.left()
        self._btn_right: ButtonHandle = KeyboardButton.right()
        self._btn_space: ButtonHandle = KeyboardButton.space()
        self._btn_lshift: ButtonHandle = KeyboardButton.lshift()

    def _get_mouse_watcher(self):
        """Retrieve MouseWatcher node if engine is initialized with an active window/input node."""
        base: ShowBase | None = getattr(builtins, "base", None)
        if base is None:
            return None
        watcher = getattr(base, "mouseWatcherNode", None)
        if watcher is not None and hasattr(watcher, "is_button_down"):
            return watcher
        mw_np = getattr(base, "mouseWatcher", None)
        if mw_np is not None and hasattr(mw_np, "node"):
            node = mw_np.node()
            if hasattr(node, "is_button_down"):
                return node
        return None

    def on_update(self, dt: float) -> None:
        """Poll input devices and update movement vector and action states."""
        watcher = self._get_mouse_watcher()
        if watcher is None:
            # Gracefully handle headless mode when base.mouseWatcherNode is not present
            super().on_update(dt)
            return

        # Snapshot current actions before new frame input is evaluated
        self._previous_actions = set(self._current_actions)

        is_down = watcher.is_button_down

        # Directional input polling
        x = 0.0
        y = 0.0

        if is_down(self._btn_w) or is_down(self._btn_up):
            y += 1.0
        if is_down(self._btn_s) or is_down(self._btn_down):
            y -= 1.0
        if is_down(self._btn_a) or is_down(self._btn_left):
            x -= 1.0
        if is_down(self._btn_d) or is_down(self._btn_right):
            x += 1.0

        vec = Vec2(x, y)
        if vec.length_squared() > 1.0:
            vec.normalize()
        self.move_vector = vec

        # Action polling
        new_actions: set[str] = set()
        if is_down(self._btn_space):
            new_actions.add("jump")
        if is_down(self._btn_lshift):
            new_actions.add("sprint")

        self._current_actions = new_actions
