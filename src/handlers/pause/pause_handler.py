"""PauseHandler
~~~~~~~~~~~~~~~~
A reusable pause component that can be attached to any Entity containing a
camera handler. It toggles a simple pause UI, releases mouse capture, and
stops per‑frame updates while paused.

The implementation follows the project’s *composition over inheritance*
principle: the handler is independent and can be combined with other
handlers (camera, input, etc.).

In headless mode (``windowType='none'``) the UI is not created and the
handler becomes a no‑op, keeping unit tests deterministic.
"""

from __future__ import annotations

import builtins
import logging
from typing import TYPE_CHECKING

from direct.gui.DirectGui import DirectButton, DirectFrame
from panda3d.core import WindowProperties

from src.handlers.base import Handler

if TYPE_CHECKING:
    from src.entities.entity import Entity
    from src.handlers.camera.third_person import ThirdPersonCameraHandler

logger = logging.getLogger(__name__)


class PauseHandler(Handler):
    """Component that provides a minimal pause menu.

    * Press *Esc* (or *P*) to toggle pause.
    * When paused:
        - Mouse capture is released and the cursor becomes visible.
        - A semi‑transparent panel with *Resume* and *Quit* buttons is shown.
        - The game’s update loop is effectively frozen (handlers that respect
          ``self.is_paused`` can skip heavy work).
    * When resumed the UI is removed and mouse capture is restored.
    """

    _pause_key: str = "escape"  # can be changed to "p" if desired

    def on_attach(self, entity: Entity) -> None:
        """Store a reference to the owning entity and optionally the camera handler."""
        super().on_attach(entity)
        self.entity = entity
        self._camera_handler: ThirdPersonCameraHandler | None = None
        self.is_paused: bool = False
        self._ui_frame: DirectFrame | None = None

    # ---------------------------------------------------------------------
    # Lifecycle
    # ---------------------------------------------------------------------
    def on_start(self) -> None:
        """Register the pause key and prepare UI if a graphics window exists."""
        super().on_start()
        base = getattr(builtins, "base", None)
        if base is None:
            logger.debug("PauseHandler: no base – headless mode, disabled.")
            return

        # Find an attached camera handler for later cursor control.
        from src.handlers.camera.first_person import FirstPersonCameraHandler
        from src.handlers.camera.third_person import ThirdPersonCameraHandler

        if self.entity is not None:
            self._camera_handler = self.entity.get_handler(
                ThirdPersonCameraHandler
            ) or self.entity.get_handler(FirstPersonCameraHandler)  # type: ignore[assignment]

        # Register the key that toggles pause.
        if hasattr(base, "accept"):
            base.accept(self._pause_key, self.toggle_pause)
        else:
            logger.warning("PauseHandler: base has no 'accept' method.")

    # ---------------------------------------------------------------------
    # Pause control
    # ---------------------------------------------------------------------
    def toggle_pause(self) -> None:
        """Switch between paused and running states."""
        if self.is_paused:
            self._resume()
        else:
            self._enter_pause()

    def _sync_engine_pause(self, paused: bool) -> None:
        """Propagate pause state to Game, Physics, and the global event bus."""
        from src.globals.physics import Physics
        from src.utils import bus

        base = getattr(builtins, "base", None)
        if base is not None and hasattr(base, "set_paused"):
            base.set_paused(paused)
        else:
            if base is not None:
                base.paused = paused
            Physics.set_paused(paused)
            bus.publish("game_paused", paused)

    def _enter_pause(self) -> None:
        """Activate pause mode: freeze game/physics, release mouse, and show UI."""
        self.is_paused = True
        self._sync_engine_pause(True)
        self._release_mouse()
        self._show_ui()
        logger.info("Game paused.")

    def _resume(self) -> None:
        """Deactivate pause mode: hide UI, resume game/physics, and capture mouse."""
        self.is_paused = False
        self._hide_ui()
        self._sync_engine_pause(False)
        self._capture_mouse()
        logger.info("Game resumed.")

    # ---------------------------------------------------------------------
    # Mouse handling helpers (compatible with headless mode)
    # ---------------------------------------------------------------------
    def _capture_mouse(self) -> None:
        """Re‑enable relative mouse mode if a window exists."""
        base = getattr(builtins, "base", None)
        win = getattr(base, "win", None) if base else None
        if win is not None and hasattr(win, "requestProperties"):
            props = WindowProperties()
            props.setCursorHidden(True)
            props.setMouseMode(WindowProperties.M_relative)
            win.requestProperties(props)
            # Ensure pointer is centered
            cx, cy = win.getXSize() // 2, win.getYSize() // 2
            if hasattr(win, "movePointer"):
                win.movePointer(0, cx, cy)
        else:
            logger.debug("PauseHandler._capture_mouse: no window, nothing to do.")

    def _release_mouse(self) -> None:
        """Show the cursor and switch to absolute mouse mode."""
        base = getattr(builtins, "base", None)
        win = getattr(base, "win", None) if base else None
        if win is not None and hasattr(win, "requestProperties"):
            props = WindowProperties()
            props.setCursorHidden(False)
            props.setMouseMode(WindowProperties.M_absolute)
            win.requestProperties(props)
        else:
            logger.debug("PauseHandler._release_mouse: no window, nothing to do.")

    # ---------------------------------------------------------------------
    # UI helpers
    # ---------------------------------------------------------------------
    def _show_ui(self) -> None:
        """Create a simple pause overlay with *Resume* and *Quit* buttons.

        The UI is only built when a graphical window is available; otherwise
        it stays ``None`` (headless safe).
        """
        base = getattr(builtins, "base", None)
        if base is None:
            return

        # Semi‑transparent background panel
        self._ui_frame = DirectFrame(
            frameColor=(0, 0, 0, 0.6),
            frameSize=(-0.5, 0.5, -0.3, 0.3),
            pos=(0, 0, 0),
        )

        # Helper to create a button inside the frame
        def _make_btn(text: str, x: float, command):
            return DirectButton(
                parent=self._ui_frame,
                text=text,
                scale=0.07,
                pos=(x, 0, 0),
                command=command,
                relief=1,
                frameColor=(0.2, 0.2, 0.2, 0.9),
                text_fg=(1, 1, 1, 1),
            )

        _make_btn("Resume", -0.15, self._resume)
        _make_btn("Quit", 0.15, self._quit_game)

    def _hide_ui(self) -> None:
        """Remove the pause overlay if it exists."""
        if self._ui_frame is not None:
            self._ui_frame.removeNode()
            self._ui_frame = None

    def _quit_game(self) -> None:
        """Signal the application to exit.

        In a full game this would call the global ``base.userExit()``.  For
        sandbox tests we simply log the request; the surrounding test can
        decide how to handle it.
        """
        base = getattr(builtins, "base", None)
        if base is not None and hasattr(base, "userExit"):
            base.userExit()
        else:
            logger.info("PauseHandler: quit requested (no base userExit available).")

    # ---------------------------------------------------------------------
    # Cleanup
    # ---------------------------------------------------------------------
    def on_stop(self) -> None:
        """Unregister key bindings and clean UI when the entity stops."""
        super().on_stop()
        if self.is_paused:
            self.is_paused = False
            self._sync_engine_pause(False)
        base = getattr(builtins, "base", None)
        if base is not None and hasattr(base, "ignore"):
            base.ignore(self._pause_key)
        self._hide_ui()
        self._camera_handler = None

    def on_detach(self) -> None:
        """Delegate to ``on_stop`` and clear the entity reference."""
        super().on_detach()
        self.on_stop()
