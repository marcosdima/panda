"""Panel container with title and padded content area."""

from __future__ import annotations

from .base import UIComponent
from .theme import UITheme


class UIPanel(UIComponent):
    """A framed container with an optional title and content parent."""

    def __init__(
        self,
        parent: object,
        title: str = "",
        width: float = 1.0,
        height: float = 0.8,
        theme: UITheme | None = None,
        owner: object = None,
        pos: tuple[float, ...] = (0.0, 0.0),
        padding: float | None = None,
    ) -> None:
        from direct.gui.DirectGui import DirectFrame

        self.theme = theme if theme is not None else UITheme()
        self._padding = float(padding if padding is not None else self.theme.padding)
        self._width = float(width)
        self._height = float(height)
        self._pos = self._normalize_pos(pos)

        frame = DirectFrame(
            parent=parent,
            frameSize=(
                -self._width / 2.0,
                self._width / 2.0,
                -self._height / 2.0,
                self._height / 2.0,
            ),
            frameColor=self.theme.panel_color,
            pos=self._pos,
        )

        self.content_parent = frame.attachNewNode("panel_content")
        self.content_parent.setPos(0.0, 0.0, 0.0)

        super().__init__(node=frame, theme=self.theme, owner=owner)

        if title:
            from direct.gui.OnscreenText import OnscreenText

            self._title = OnscreenText(
                parent=frame,
                text=title,
                pos=(0.0, self._height / 2.0 - self._padding),
                scale=self.theme.title_scale,
                fg=self.theme.text_color,
                align=0,
                mayChange=False,
            )
        else:
            self._title = None

    @staticmethod
    def _normalize_pos(pos: tuple[float, ...]) -> tuple[float, float, float]:
        if len(pos) == 2:
            return (float(pos[0]), 0.0, float(pos[1]))
        if len(pos) == 3:
            return (float(pos[0]), float(pos[1]), float(pos[2]))
        raise ValueError("pos must have 2 or 3 components")

    def destroy(self) -> None:
        if self.destroyed:
            return
        if getattr(self, "_title", None) is not None:
            try:
                self._title.destroy()
            except Exception:  # noqa: BLE001, S110
                pass
            self._title = None
        super().destroy()
