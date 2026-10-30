"""Utility module providing a simple cooldown timer.

The :class:`Cooldown` class is useful in game-logic or any system where an
action should only be performed after a certain amount of time has passed.
It tracks the remaining time and exposes a convenient ``ready`` property.

Typical usage::

    cd = Cooldown(2.5)   # 2.5 seconds cooldown
    if cd.ready:
        cd.start()       # trigger the cooldown
        ...
    cd.tick(dt)          # called each frame with the elapsed delta-time

The implementation is deliberately lightweight and has no external
dependencies, making it safe to include in the ``src/utils`` package.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Cooldown:
    """A very small timer that counts down to become ready again.

    Attributes
    ----------
    duration:
        The total length of the cooldown in seconds.
    _remaining:
        Private field tracking how much time is left. It is initialised to ``0``
        so a newly created instance is *ready*.
    """

    duration: float
    _remaining: float = field(default=0.0, init=False, repr=False)

    def __post_init__(self) -> None:
        # Ensure duration is stored as a float for consistency
        self.duration = float(self.duration)
        if self.duration < 0.0:
            raise ValueError("Cooldown duration must be non-negative")

    @property
    def ready(self) -> bool:
        """Return ``True`` when the cooldown has elapsed.

        A cooldown is considered ready when ``_remaining`` is less than or
        equal to ``0``. The property does not modify any internal state.
        """
        return self._remaining <= 0.0

    def start(self) -> None:
        """Activate the cooldown.

        Sets the remaining time to the configured ``duration``. If ``duration``
        is ``0`` the cooldown is instantly ready.
        """
        self._remaining = float(self.duration)

    def reset(self) -> None:
        """Reset the cooldown without starting it.

        This clears any pending time, effectively making the instance ready.
        """
        self._remaining = 0.0

    def tick(self, delta: float) -> None:
        """Advance the cooldown timer by ``delta`` seconds.

        ``delta`` is typically the time elapsed since the last frame. Negative
        values are ignored.
        """
        if delta > 0.0 and self._remaining > 0.0:
            self._remaining = max(0.0, self._remaining - delta)

    @property
    def remaining(self) -> float:
        """Return the remaining cooldown time in seconds.

        Useful for UI displays or debugging. The value is ``0.0`` when the
        cooldown is ready.
        """
        return self._remaining

    def trigger(self) -> bool:
        """Convenience helper: start the cooldown if it is ready.

        Returns ``True`` when the cooldown was started, ``False`` otherwise.
        """
        if self.ready:
            self.start()
            return True
        return False


# __bool__ removed per review – callers should use `ready` explicitly
