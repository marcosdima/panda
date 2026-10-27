"""Reusable button primitive."""

from __future__ import annotations

from .base import UIComponent
from .theme import UITheme


class UIButton(UIComponent):
    """A clickable button wrapping ``DirectButton``."""

    def __init__(
        self,
        parent: object,
        text: str = "",
        command=None,
        theme: UITheme | None = None,
        owner: object = None,
        pos: tuple[float, ...] = (0.0, 0.0),
        scale: float = 0.05,
        enabled: bool = True,
        **kwargs: object,
    ) -> None:
        from direct.gui.DirectGui import DirectButton

        self.theme = theme if theme is not None else UITheme()
        self._command = command
        self._enabled = bool(enabled)
        self._pos = self._normalize_pos(pos)

        widget = DirectButton(
            parent=parent,
            text=text,
            command=self._on_click,
            pos=self._pos,
            scale=scale,
            frameColor=self.theme.button_state_colors(self._enabled),
            text_fg=self.theme.text_color,
            pad=(0.18, 0.10),
            **kwargs,
        )
        super().__init__(node=widget, theme=self.theme, owner=owner)
        self.set_enabled(self._enabled)

    @staticmethod
    def _normalize_pos(pos: tuple[float, ...]) -> tuple[float, float, float]:
        if len(pos) == 2:
            return (float(pos[0]), 0.0, float(pos[1]))
        if len(pos) == 3:
            return (float(pos[0]), float(pos[1]), float(pos[2]))
        raise ValueError("pos must have 2 or 3 components")

    def _on_click(self) -> None:
        if not self._enabled or self._command is None or self.destroyed:
            return
        try:
            self._command()
        except Exception:  # noqa: BLE001
            pass

    def set_text(self, text: str) -> None:
        if self.destroyed or self.node is None:
            return
        try:
            self.node["text"] = text
        except Exception:  # noqa: BLE001
            pass

    def set_command(self, command) -> None:
        self._command = command

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        if self.destroyed or self.node is None:
            return
        try:
            self.node["state"] = "normal" if self._enabled else "disabled"
            self.node["frameColor"] = self.theme.button_state_colors(self._enabled)
        except Exception:  # noqa: BLE001
            pass

    @property
    def enabled(self) -> bool:
        return self._enabled
