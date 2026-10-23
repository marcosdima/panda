"""CameraSettingsComponent
~~~~~~~~~~~~~~~~~~~~~~~~~~
A reusable UI component that exposes *sliders* for the most common
parameters of a ``ThirdPersonCameraHandler``: distance, pitch, yaw and
target offset (Z).  It follows the same composition‑over‑inheritance
principle used by the other test‑time components.

When a graphical window is present the component builds a small panel
with four ``DirectSlider`` widgets.  In headless mode (``windowType='none'``)
the component becomes a no‑op, keeping unit tests deterministic.

Typical sandbox usage:

```python
entity = Entity(name="Player")
entity.add_handler(ThirdPersonCameraHandler())
entity.add_handler(CameraSettingsComponent())
```

The sliders update the attached camera handler *live* – no extra test
code is required.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import builtins
from direct.gui.DirectGui import DirectFrame, DirectSlider, DirectLabel

from src.handlers.base import Handler

if TYPE_CHECKING:
    from src.entities.entity import Entity
    from src.handlers.camera.third_person import ThirdPersonCameraHandler

logger = logging.getLogger(__name__)


class CameraSettingsComponent(Handler):
    """UI panel with sliders to tweak camera parameters at runtime.

    Parameters controlled:
    * **distance** – zoom level (float).  Range: ``min_distance`` → ``max_distance``.
    * **pitch**    – vertical angle (degrees).  Range defined by the camera handler.
    * **yaw**      – horizontal angle (degrees).  Range: 0‑360.
    * **target Z offset** – vertical offset of the camera target (float).
    """

    # Slider configuration – step size is small enough for fine control.
    _slider_cfg = {
        "distance": {"step": 0.1, "width": 0.4},
        "pitch": {"step": 0.5, "width": 0.4},
        "yaw": {"step": 1.0, "width": 0.4},
        "offset_z": {"step": 0.05, "width": 0.4},
    }

    def on_attach(self, entity: "Entity") -> None:
        super().on_attach(entity)
        self.entity = entity
        self._camera_handler: ThirdPersonCameraHandler | None = None
        self._panel: DirectFrame | None = None
        self._sliders: dict[str, DirectSlider] = {}

    # -----------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------
    def on_start(self) -> None:
        super().on_start()
        base = getattr(builtins, "base", None)
        if base is None or getattr(base, "win", None) is None:
            logger.debug("CameraSettingsComponent: headless mode – UI disabled.")
            return

        # Resolve the camera handler attached to the same entity.
        from src.handlers.camera.third_person import ThirdPersonCameraHandler
        self._camera_handler = self.entity.get_handler(ThirdPersonCameraHandler)  # type: ignore[arg-type]
        if self._camera_handler is None:
            logger.warning(
                "CameraSettingsComponent attached to entity without a ThirdPersonCameraHandler."
            )
            return

        # Build a simple panel in the top‑right corner.
        self._panel = DirectFrame(
            frameColor=(0, 0, 0, 0.5),
            frameSize=(-0.6, 0.6, -0.1, 0.6),
            pos=(0.8, 0, 0),
        )

        # Helper to create a labelled slider.
        def _make_slider(name: str, label: str, lo: float, hi: float, init: float, y: float):
            # Label
            DirectLabel(
                parent=self._panel,
                text=label,
                scale=0.05,
                pos=(-0.5, 0, y + 0.04),
                text_fg=(1, 1, 1, 1),
                frameColor=None,
            )
            # Slider widget
            slider = DirectSlider(
                parent=self._panel,
                range=(lo, hi),
                value=init,
                pageSize=self._slider_cfg[name]["step"],
                scale=self._slider_cfg[name]["width"],
                pos=(0, 0, y),
                command=lambda v, n=name: self._apply_slider(n, float(v)),
            )
            self._sliders[name] = slider

        # Create sliders using the current camera state.
        ch = self._camera_handler
        _make_slider(
            "distance",
            "Distance",
            ch.min_distance,
            ch.max_distance,
            ch.distance,
            y=0.38,
        )
        _make_slider(
            "pitch",
            "Pitch",
            ch.min_pitch,
            ch.max_pitch,
            ch.pitch,
            y=0.22,
        )
        _make_slider(
            "yaw",
            "Yaw",
            0.0,
            360.0,
            ch.yaw,
            y=0.06,
        )
        _make_slider(
            "offset_z",
            "Target Z",
            -5.0,
            5.0,
            ch.target_offset.z,
            y=-0.1,
        )

    # -----------------------------------------------------------------
    # Slider callback – applies the changed value directly to the camera.
    # -----------------------------------------------------------------
    def _apply_slider(self, name: str, value: float) -> None:
        if self._camera_handler is None:
            return
        ch = self._camera_handler
        if name == "distance":
            ch.distance = value
        elif name == "pitch":
            ch.pitch = value
        elif name == "yaw":
            ch.yaw = value
        elif name == "offset_z":
            # Only modify the Z component of the target offset vector.
            ch.target_offset = ch.target_offset.with_z(value)
        logger.debug("Camera %s set to %.3f", name, value)

    # -----------------------------------------------------------------
    # Cleanup
    # -----------------------------------------------------------------
    def on_stop(self) -> None:
        super().on_stop()
        # Remove UI elements if they exist.
        for slider in self._sliders.values():
            slider.removeNode()
        self._sliders.clear()
        if self._panel is not None:
            self._panel.removeNode()
            self._panel = None
        self._camera_handler = None

    def on_detach(self) -> None:
        self.on_stop()
        if hasattr(self, "entity"):
            del self.entity
        super().on_detach()
