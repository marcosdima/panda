"""CameraControlComponent
~~~~~~~~~~~~~~~
A reusable test‑time component that exposes UI buttons to tweak the
`ThirdPersonCameraHandler` (or any compatible camera handler) at runtime.
It follows the *composition over inheritance* rule: the component is a
stand‑alone :class:`Handler` that can be attached to any :class:`Entity`
containing a camera handler.

The component creates two DirectButton instances (``+`` and ``-``) that
increase or decrease the camera ``distance`` attribute.  In headless mode
the UI is not created – the component becomes a no‑op to keep tests
compatible with ``windowType='none'``.

Typical usage in a test sandbox:

```python
entity = world.create_entity()
entity.add_handler(ThirdPersonCameraHandler())
entity.add_handler(CameraControlComponent())
```

Pressing the UI buttons will instantly update the distance, which is
reflected in the next camera update.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import builtins
from direct.gui.DirectGui import DirectButton

from src.handlers.base import Handler

if TYPE_CHECKING:
    from src.entities.entity import Entity
    from src.handlers.camera.third_person import ThirdPersonCameraHandler

logger = logging.getLogger(__name__)


class CameraControlComponent(Handler):
    """Component that adds UI sliders/buttons to control camera distance.

    The component looks for a :class:`ThirdPersonCameraHandler` attached to the
    same entity.  If none is found it logs a warning and does nothing.
    """

    _increment: float = 0.5  #: Step size for each button press.

    def on_attach(self, entity: "Entity") -> None:  # noqa: D401
        """Store a reference to the owning *entity*.

        The base implementation registers the entity pointer; we also keep a
        reference to the camera handler (if available) for quick access.
        """
        super().on_attach(entity)
        self.entity = entity
        # Resolve the camera handler lazily; it may be added later.
        self._camera_handler: ThirdPersonCameraHandler | None = None

    def on_start(self) -> None:
        """Create UI buttons when a graphical window is present.

        In headless mode (``base`` is ``None`` or ``base.win`` is ``None``) the
        component becomes inert, preserving test stability.
        """
        super().on_start()

        base = getattr(builtins, "base", None)
        if base is None or getattr(base, "win", None) is None:
            # Headless – skip UI creation.
            logger.debug("CameraControlComponent: headless mode, UI disabled.")
            return

        # Find the camera handler on the same entity.
        from src.handlers.camera.third_person import ThirdPersonCameraHandler

        self._camera_handler = self.entity.get_handler(ThirdPersonCameraHandler)  # type: ignore[arg-type]
        if self._camera_handler is None:
            logger.warning(
                "CameraControlComponent attached to entity without a ThirdPersonCameraHandler."
            )
            return

        # Simple helper to create a button.
        def _make_button(text: str, pos_x: float, command):
            return DirectButton(
                text=text,
                scale=0.07,
                pos=(pos_x, 0, 0.9),
                command=command,
                relief=1,
                frameColor=(0.2, 0.2, 0.2, 0.8),
                text_fg=(1, 1, 1, 1),
            )

        self._btn_inc = _make_button("+", 0.2, self._increase_distance)
        self._btn_dec = _make_button("-", -0.2, self._decrease_distance)

    # ---------------------------------------------------------------------
    # UI callbacks
    # ---------------------------------------------------------------------
    def _increase_distance(self) -> None:
        if self._camera_handler is None:
            return
        new_dist = self._camera_handler.distance + self._increment
        self._camera_handler.distance = new_dist
        logger.info("Camera distance increased to %.2f", new_dist)

    def _decrease_distance(self) -> None:
        if self._camera_handler is None:
            return
        new_dist = self._camera_handler.distance - self._increment
        self._camera_handler.distance = new_dist
        logger.info("Camera distance decreased to %.2f", new_dist)

    def on_stop(self) -> None:
        """Remove UI elements and clean references."""
        super().on_stop()
        # DirectButton instances clean themselves on ``removeNode``.
        for btn in getattr(self, "_btn_inc", []), getattr(self, "_btn_dec", []):
            if btn:
                btn.removeNode()
        self._camera_handler = None

    def on_detach(self) -> None:
        """Delegate to ``on_stop`` and clear the entity reference."""
        self.on_stop()
        if hasattr(self, "entity"):
            del self.entity
        super().on_detach()
