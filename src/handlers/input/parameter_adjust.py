"""Parameter adjustment handler for runtime testing.

This handler allows the user to modify a numeric attribute on a target handler
(e.g., ``collision_margin`` on ``FirstPersonCameraHandler``) using the '+' and
'-' keys. It follows the standard Handler lifecycle contract defined in
``src.handlers.base.Handler``.
"""

from __future__ import annotations

import builtins
import logging
from typing import Any

from src.handlers.base import Handler
from src.utils.handler_phase import HandlerPhase

logger = logging.getLogger(__name__)


class ParameterAdjustHandler(Handler):
    phase = HandlerPhase.INPUT
    """Adjust a numeric attribute of a target handler at runtime.

    Parameters
    ----------
    target: Any
        The handler (or any object) that owns the attribute to modify. It must
        expose the attribute via ``setattr``/``getattr``.
    attribute_name: str
        Name of the attribute to adjust (must be a ``float`` or ``int``).
    step: float, optional
        Increment/decrement amount applied for each key press. Defaults to ``0.1``.
    min_value: float | None, optional
        Optional lower bound for the attribute. If ``None`` no lower bound is
        enforced.
    max_value: float | None, optional
        Optional upper bound for the attribute. If ``None`` no upper bound is
        enforced.
    """

    def __init__(
        self,
        target: Any,
        attribute_name: str,
        step: float = 0.1,
        min_value: float | None = None,
        max_value: float | None = None,
    ) -> None:
        super().__init__()
        self._target = target
        self._attr = attribute_name
        self._step = float(step)
        self._min = min_value
        self._max = max_value

    # ---------------------------------------------------------------------
    # Helper methods
    # ---------------------------------------------------------------------
    def _get_current(self) -> float:
        try:
            value = getattr(self._target, self._attr)
            return float(value)
        except Exception:
            logger.error(
                "Failed to read attribute %s from %s",
                self._attr,
                self._target,
                exc_info=True,
            )
            raise

    def _set_current(self, new_value: float) -> None:
        if self._min is not None:
            new_value = max(self._min, new_value)
        if self._max is not None:
            new_value = min(self._max, new_value)
        try:
            setattr(self._target, self._attr, new_value)
            logger.info("%s.%s set to %s", self._target, self._attr, new_value)
        except Exception:
            logger.error(
                "Failed to set attribute %s on %s",
                self._attr,
                self._target,
                exc_info=True,
            )
            raise

    # ---------------------------------------------------------------------
    # Lifecycle hooks
    # ---------------------------------------------------------------------
    def on_start(self) -> None:
        """Bind '+' and '-' keys to increase/decrease the attribute."""
        base = getattr(builtins, "base", None)
        if base is None or not hasattr(base, "accept"):
            logger.warning(
                "Panda3D base not available; ParameterAdjustHandler will be inactive."
            )
            return
        base.accept("+", self._increase)
        base.accept("-", self._decrease)

    def on_stop(self) -> None:
        """Unbind the keys when the handler stops."""
        base = getattr(builtins, "base", None)
        if base is None or not hasattr(base, "ignore"):
            return
        base.ignore("+")
        base.ignore("-")

    # ---------------------------------------------------------------------
    # Key callbacks
    # ---------------------------------------------------------------------
    def _increase(self) -> None:
        current = self._get_current()
        self._set_current(current + self._step)

    def _decrease(self) -> None:
        current = self._get_current()
        self._set_current(current - self._step)

    # ---------------------------------------------------------------------
    # No per‑frame logic needed – changes are driven by key events.
    # ---------------------------------------------------------------------
    def on_update(self, dt: float) -> None:  # pragma: no cover – required by interface
        pass
