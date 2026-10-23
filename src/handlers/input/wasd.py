from __future__ import annotations

import builtins
from typing import TYPE_CHECKING
from panda3d.core import Vec2

from .action_map import (
    MOVE_BACK,
    MOVE_FORWARD,
    MOVE_LEFT,
    MOVE_RIGHT,
    MOVEMENT_ACTIONS,
    ActionMap,
)
from .base import InputHandler

if TYPE_CHECKING:
    from direct.showbase.ShowBase import ShowBase


class WASDInputHandler(InputHandler):
    """Input handler polling an ``ActionMap`` (defaults: WASD/arrows, Space=jump, LShift=sprint)."""

    def __init__(self, action_map: ActionMap | None = None) -> None:
        super().__init__()
        self.action_map: ActionMap = action_map if action_map is not None else ActionMap.default()

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
        amap = self.action_map

        # Directional input polling
        x = 0.0
        y = 0.0

        if amap.is_down(MOVE_FORWARD, is_down):
            y += 1.0
        if amap.is_down(MOVE_BACK, is_down):
            y -= 1.0
        if amap.is_down(MOVE_LEFT, is_down):
            x -= 1.0
        if amap.is_down(MOVE_RIGHT, is_down):
            x += 1.0

        vec = Vec2(x, y)
        if vec.length_squared() > 1.0:
            vec.normalize()
        self.move_vector = vec

        # Action polling (every non-movement action in the map, e.g. jump, sprint, interact)
        self._current_actions = {
            action
            for action in amap.actions
            if action not in MOVEMENT_ACTIONS and amap.is_down(action, is_down)
        }
