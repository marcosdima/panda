"""Reusable scroll container primitive."""

from __future__ import annotations

from .base import UIComponent
from .theme import UITheme


class UIScrollContainer(UIComponent):
    """A scrollable frame wrapping ``DirectScrolledFrame``."""

    def __init__(
        self,
        parent: object,
        width: float = 0.6,
        height: float = 0.8,
        canvas_height: float | None = None,
        theme: UITheme | None = None,
        owner: object = None,
        pos: tuple[float, ...] = (0.0, 0.0),
    ) -> None:
        from direct.gui.DirectGui import DirectScrolledFrame

        self.theme = theme if theme is not None else UITheme()
        self._width = float(width)
        self._height = float(height)
        self._canvas_height = float(canvas_height) if canvas_height is not None else self._height * 2.0
        self._pos = self._normalize_pos(pos)

        frame_size = (-self._width / 2.0, self._width / 2.0, -self._height / 2.0, self._height / 2.0)
        canvas_size = (
            -self._width / 2.0,
            self._width / 2.0,
            -self._canvas_height / 2.0,
            self._canvas_height / 2.0,
        )

        widget = DirectScrolledFrame(
            parent=parent,
            frameSize=frame_size,
            canvasSize=canvas_size,
            pos=self._pos,
            frameColor=self.theme.frame_color,
        )
        super().__init__(node=widget, theme=self.theme, owner=owner)

    @staticmethod
    def _normalize_pos(pos: tuple[float, ...]) -> tuple[float, float, float]:
        if len(pos) == 2:
            return (float(pos[0]), 0.0, float(pos[1]))
        if len(pos) == 3:
            return (float(pos[0]), float(pos[1]), float(pos[2]))
        raise ValueError("pos must have 2 or 3 components")

    @property
    def canvas(self):
        if self.destroyed or self.node is None:
            return None
        try:
            return self.node.getCanvas()
        except Exception:  # noqa: BLE001
            try:
                return self.node.canvas
            except Exception:  # noqa: BLE001
                return None

    def set_content(self, content: object) -> None:
        canvas = self.canvas
        if canvas is None:
            return
        node = getattr(content, "node", content)
        if node is None:
            return
        try:
            node.reparentTo(canvas)
            node.setPos(0.0, 0.0, 0.0)
        except Exception:  # noqa: BLE001
            pass

    def scroll_to_top(self) -> None:
        if self.destroyed or self.node is None:
            return
        try:
            self.node.setScroll(0.0, 0.0)
        except Exception:  # noqa: BLE001
            pass

    def scroll_to_bottom(self) -> None:
        if self.destroyed or self.node is None:
            return
        try:
            self.node.setScroll(0.0, 1.0)
        except Exception:  # noqa: BLE001
            pass
