"""Shared theme tokens for the reusable UI components."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UITheme:
    """Style tokens shared by all UI primitives."""

    frame_color: tuple[float, float, float, float] = (0.18, 0.22, 0.30, 0.92)
    text_color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)
    hover_color: tuple[float, float, float, float] = (0.28, 0.36, 0.50, 1.0)
    disabled_color: tuple[float, float, float, float] = (0.35, 0.35, 0.35, 0.8)
    highlight_color: tuple[float, float, float, float] = (0.95, 0.85, 0.35, 1.0)
    scale: float = 0.05
    padding: float = 0.02

    def button_frame_color(self, enabled: bool = True) -> tuple[float, float, float, float]:
        return self.frame_color if enabled else self.disabled_color
