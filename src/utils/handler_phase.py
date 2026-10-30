from __future__ import annotations

from enum import IntEnum


class HandlerPhase(IntEnum):
    """Execution phase for a handler within a frame.

    Lower values run earlier. ``NORMAL`` keeps the legacy attach-order
    behaviour for handlers that do not declare a phase.
    """

    INPUT = 0
    DECISION = 1
    PHYSICS = 2
    POST = 3
    NORMAL = 100
