"""Lightweight finite state machine (stdlib only)."""

from __future__ import annotations

from typing import Callable, Hashable, Iterable, Mapping, Optional

StateCallback = Callable[[Hashable, Hashable], None]


class StateMachine:
    """Finite state machine with explicit transitions and enter/exit hooks.

    Parameters
    ----------
    initial:
        Starting state. No hooks run for it.
    transitions:
        Mapping ``state -> iterable of allowed target states``. States that
        appear only as targets are registered as states with no outgoing
        transitions. ``None`` allows every transition between known states.
    """

    def __init__(
        self,
        initial: Hashable,
        transitions: Optional[Mapping[Hashable, Iterable[Hashable]]] = None,
    ):
        self._state = initial
        self._allowed: Optional[dict[Hashable, set[Hashable]]] = None
        if transitions is not None:
            self._allowed = {s: set(t) for s, t in transitions.items()}
            for targets in list(self._allowed.values()):
                for target in targets:
                    self._allowed.setdefault(target, set())
            if initial not in self._allowed:
                raise ValueError(f"initial state {initial!r} is not defined")
        self._on_enter: dict[Hashable, list[StateCallback]] = {}
        self._on_exit: dict[Hashable, list[StateCallback]] = {}
        self._transitioning = False

    @property
    def state(self) -> Hashable:
        """Current state."""
        return self._state

    def on_enter(self, state: Hashable, cb: StateCallback) -> None:
        """Register ``cb(previous, new)`` to run after entering *state*."""
        self._on_enter.setdefault(state, []).append(cb)

    def on_exit(self, state: Hashable, cb: StateCallback) -> None:
        """Register ``cb(previous, new)`` to run before leaving *state*."""
        self._on_exit.setdefault(state, []).append(cb)

    def reset(self, state: Hashable) -> None:
        """Set the current state without running hooks or validating transitions.

        Registered hooks are kept. Raises ``ValueError`` for undefined states in
        a restricted machine, and ``RuntimeError`` when called from a hook.
        """
        if self._transitioning:
            raise RuntimeError("reset() called from within a state hook")
        if self._allowed is not None and state not in self._allowed:
            raise ValueError(f"state {state!r} is not defined")
        self._state = state

    def can_transition(self, target: Hashable) -> bool:
        """Whether moving from the current state to *target* is allowed."""
        if self._allowed is None:
            return True
        return target in self._allowed.get(self._state, ())

    def transition(self, target: Hashable) -> bool:
        """Move to *target*; raise ``ValueError`` if not allowed.

        Transitioning to the current state is a no-op returning ``False``.
        Returns ``True`` when the state changed.

        Hooks must not call :meth:`transition`; doing so raises
        ``RuntimeError`` (re-entrancy guard) so callbacks never run out of order.
        """
        if self._transitioning:
            raise RuntimeError("transition() called from within a state hook")
        if target == self._state:
            return False
        if not self.can_transition(target):
            raise ValueError(f"transition {self._state!r} -> {target!r} not allowed")
        previous = self._state
        self._transitioning = True
        try:
            for cb in list(self._on_exit.get(previous, ())):
                cb(previous, target)
            self._state = target
            for cb in list(self._on_enter.get(target, ())):
                cb(previous, target)
        finally:
            self._transitioning = False
        return True
