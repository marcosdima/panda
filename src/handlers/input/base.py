from __future__ import annotations

from panda3d.core import Vec2

from src.handlers.base import Handler
from src.handlers.capabilities import IntentSource
from src.utils.handler_phase import HandlerPhase


class InputHandler(Handler):
    phase = HandlerPhase.INPUT
    provides = (IntentSource,)
    """Base class for entity input handlers providing movement intent and action state querying."""

    def __init__(self) -> None:
        super().__init__()
        self.move_vector: Vec2 = Vec2(0.0, 0.0)
        self._current_actions: set[str] = set()
        self._previous_actions: set[str] = set()
        self._just_modified: set[str] = set()

    def is_action_down(self, action_name: str) -> bool:
        """Return True if the action is currently held down."""
        return action_name in self._current_actions

    def is_action_pressed(self, action_name: str) -> bool:
        """Return True only on the frame the action was initially pressed."""
        return action_name in self._current_actions and action_name not in self._previous_actions

    def is_action_released(self, action_name: str) -> bool:
        """Return True only on the frame the action was released."""
        return action_name not in self._current_actions and action_name in self._previous_actions

    def set_action_state(self, action_name: str, is_down: bool) -> None:
        """Manually set an action state (primarily for testing or virtual inputs)."""
        if is_down:
            if action_name not in self._current_actions:
                self._current_actions.add(action_name)
                self._just_modified.add(action_name)
        else:
            self._current_actions.discard(action_name)
            self._just_modified.discard(action_name)

    def set_move_vector(self, x: float, y: float) -> None:
        """Manually set movement vector, normalizing if magnitude exceeds 1.0."""
        vec = Vec2(x, y)
        if vec.length_squared() > 1.0:
            vec.normalize()
        self.move_vector = vec

    def on_update(self, dt: float) -> None:
        """Frame update hook. Advances action states for edge detection on subsequent ticks."""
        super().on_update(dt)
        for action in list(self._current_actions):
            if action in self._just_modified:
                self._just_modified.discard(action)
            else:
                self._previous_actions.add(action)
        self._previous_actions = set(self._previous_actions & self._current_actions)

    def on_stop(self) -> None:
        """Reset inputs when entity or scene stops."""
        super().on_stop()
        self.move_vector = Vec2(0.0, 0.0)
        self._current_actions.clear()
        self._previous_actions.clear()
        self._just_modified.clear()

    def on_detach(self) -> None:
        """Reset inputs when handler is detached."""
        super().on_detach()
        self.move_vector = Vec2(0.0, 0.0)
        self._current_actions.clear()
        self._previous_actions.clear()
        self._just_modified.clear()
