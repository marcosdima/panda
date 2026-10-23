from __future__ import annotations

from typing import TYPE_CHECKING

from src.handlers.base import Handler
from src.handlers.input.base import InputHandler
from src.utils.event import Event

if TYPE_CHECKING:
    from src.entities.entity import Entity


class HealthHandler(Handler):
    """Entity health, damage and death as an optional component.

    Owns a ``current_health`` value clamped to ``[0, max_health]`` and exposes
    ``take_damage`` / ``heal`` plus ``is_dead`` / ``is_alive``. Two
    :class:`~src.utils.event.Event` instances (``on_damage``, ``on_death``)
    let other systems react without holding references to this handler or its
    entity — matching the engine's event-bus communication pattern.

    This component degrades gracefully headless: it touches no graphics,
    physics or window API, so it can be exercised without a ``ShowBase``.

    Death handling precedence: when both ``auto_free_on_death`` and
    ``disable_input_on_death`` are set, the entity is freed first and the
    input-disable step is skipped (a freed entity has no handlers left).
    """

    def __init__(
        self,
        max_health: float = 100.0,
        current_health: float | None = None,
        auto_free_on_death: bool = False,
        disable_input_on_death: bool = True,
    ) -> None:
        super().__init__()
        self.max_health: float = float(max_health)
        current = self.max_health if current_health is None else float(current_health)
        self._current_health: float = max(0.0, min(self.max_health, current))
        self.auto_free_on_death: bool = bool(auto_free_on_death)
        self.disable_input_on_death: bool = bool(disable_input_on_death)
        # True only when this handler disabled the entity's InputHandler on
        # death; used to avoid resurrecting input the user disabled itself.
        self._input_disabled_by_handler: bool = False

        # Engine events, typed by payload. Subscribers react without holding
        # references to this handler or its entity.
        self.on_damage: Event[tuple[float, "Entity | None"]] = Event()
        self.on_death: Event["Entity | None"] = Event()

    @property
    def current_health(self) -> float:
        """Current health, clamped to ``[0, max_health]``."""
        return self._current_health

    @property
    def is_dead(self) -> bool:
        """True when current health is at or below zero."""
        return self._current_health <= 0.0

    @property
    def is_alive(self) -> bool:
        """True when current health is above zero."""
        return self._current_health > 0.0

    # ------------------------------------------------------------------
    # Damage / healing
    # ------------------------------------------------------------------

    def take_damage(self, amount: float, source: "Entity | None" = None) -> bool:
        """Reduce health by ``amount`` (clamped at zero).

        Returns ``True`` when health actually changed. Damage taken while
        already dead is a no-op and returns ``False``. Fires ``on_damage``
        with the *applied* ``(amount, source)`` whenever health drops, and
        ``on_death`` with the owning entity when the entity dies as a result.
        """
        if self.is_dead:
            return False

        amount = max(0.0, float(amount))
        previous = self._current_health
        self._current_health = max(0.0, previous - amount)
        applied = previous - self._current_health

        if applied == 0.0:
            return False

        self.on_damage(applied, source)

        if self.is_dead:
            self._on_death()

        return True

    def heal(self, amount: float) -> float:
        """Restore health by ``amount`` (clamped at ``max_health``).

        Returns the amount of health actually restored. Healing a dead entity
        is a no-op and returns ``0.0``.
        """
        if self.is_dead:
            return 0.0

        amount = max(0.0, float(amount))
        previous = self._current_health
        self._current_health = min(self.max_health, previous + amount)

        return self._current_health - previous

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_start(self) -> None:
        """Clamp starting health to ``[0, max_health]`` (idempotent guard).

        Re-apply the death-time input disable so a ``stop()``/``start()`` cycle
        cannot resurrect movement on a dead entity.
        """
        super().on_start()
        self._current_health = max(0.0, min(self.max_health, self._current_health))
        if self.is_dead and self.disable_input_on_death and not self.auto_free_on_death:
            self._disable_input()

    def on_stop(self) -> None:
        """Re-enable input only if this handler disabled it on death."""
        super().on_stop()
        self._restore_input()

    def on_detach(self) -> None:
        """Re-enable input only if this handler disabled it, then clear the entity."""
        self._restore_input()
        super().on_detach()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_death(self) -> None:
        """Run once when the entity dies: fire on_death and apply options.

        Precedence: when ``auto_free_on_death`` is set, the entity is freed
        first and the input-disable step is skipped (a freed entity has no
        handlers left).
        """
        self.on_death(self.entity)

        if self.auto_free_on_death and self.entity is not None:
            self.entity.free()
            return

        if self.disable_input_on_death:
            self._disable_input()

    def _disable_input(self) -> None:
        """Disable the entity's InputHandler and stop its movement intent.

        Zeroing the intent matters because ``CharacterControllerHandler``
        reads ``move_vector`` unconditionally — ``InputHandler.set_enabled``
        only gates the frame hook, it does not clear the last written vector.

        Ownership is claimed only when this handler actually flipped the
        state: input the user disabled themselves is left alone, and
        ``_restore_input()`` will not resurrect it.
        """
        if self.entity is None:
            return
        input_handler = self.entity.get_handler(InputHandler)
        if input_handler is None:
            return
        if input_handler.is_enabled:
            self._input_disabled_by_handler = True
        input_handler.set_move_vector(0.0, 0.0)
        input_handler.set_enabled(False)

    def _restore_input(self) -> None:
        """Re-enable the InputHandler only if this handler disabled it."""
        if not self._input_disabled_by_handler or self.entity is None:
            return
        input_handler = self.entity.get_handler(InputHandler)
        if input_handler is not None:
            input_handler.set_enabled(True)
        self._input_disabled_by_handler = False
