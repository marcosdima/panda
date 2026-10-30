"""Reusable vertical list primitive."""

from __future__ import annotations

from .base import UIComponent
from .button import UIButton
from .theme import UITheme


class UIList(UIComponent):
    """A vertical list of selectable items."""

    def __init__(
        self,
        parent: object,
        items: list[tuple[str, object]] | None = None,
        on_select=None,
        theme: UITheme | None = None,
        owner: object = None,
        pos: tuple[float, ...] = (0.0, 0.0),
        item_height: float = 0.06,
        scale: float = 0.05,
    ) -> None:
        self.theme = theme if theme is not None else UITheme()
        self._parent = parent
        self._pos = self._normalize_pos(pos)
        self._item_height = float(item_height)
        self._scale = float(scale)
        self._on_select = on_select
        self._items: list[dict[str, object]] = []
        self._buttons: list[UIButton] = []
        self._selected_index: int = -1

        from panda3d.core import NodePath

        self._root = NodePath("ui_list")
        try:
            self._root.reparentTo(parent)
            self._root.setPos(self._pos)
        except Exception:  # noqa: BLE001
            pass

        super().__init__(node=self._root, theme=self.theme, owner=owner)

        for label, value in items or []:
            self.add_item(str(label), value)

    @staticmethod
    def _normalize_pos(pos: tuple[float, ...]) -> tuple[float, float, float]:
        if len(pos) == 2:
            return (float(pos[0]), 0.0, float(pos[1]))
        if len(pos) == 3:
            return (float(pos[0]), float(pos[1]), float(pos[2]))
        raise ValueError("pos must have 2 or 3 components")

    @property
    def items_count(self) -> int:
        return len(self._items)

    @property
    def selected_index(self) -> int:
        return self._selected_index

    @property
    def selected_value(self) -> object:
        if 0 <= self._selected_index < len(self._items):
            return self._items[self._selected_index]["value"]
        return None

    def add_item(self, label: str, value: object = None) -> int:
        index = len(self._items)
        self._items.append({"label": label, "value": value})
        button = UIButton(
            parent=self._root,
            text=label,
            command=lambda idx=index: self._handle_click(idx),
            theme=self.theme,
            pos=(0.0, -index * self._item_height),
            scale=self._scale,
        )
        self._buttons.append(button)
        return index

    def remove_item(self, index: int) -> None:
        if not (0 <= index < len(self._items)):
            return
        button = self._buttons.pop(index)
        button.destroy()
        del self._items[index]
        self._rebuild_positions()
        if self._selected_index == index:
            self._selected_index = -1
        elif self._selected_index > index:
            self._selected_index -= 1

    def clear(self) -> None:
        for button in self._buttons:
            button.destroy()
        self._buttons.clear()
        self._items.clear()
        self._selected_index = -1

    def select(self, index: int) -> None:
        if not (0 <= index < len(self._items)):
            return
        self._selected_index = index
        for i, button in enumerate(self._buttons):
            try:
                if i == index:
                    button.node["frameColor"] = self.theme.highlight_color
                else:
                    button.node["frameColor"] = self.theme.button_frame_color(True)
            except Exception:  # noqa: BLE001
                pass
        if self._on_select is not None:
            try:
                self._on_select(index, self._items[index]["value"])
            except Exception:  # noqa: BLE001
                pass

    def _handle_click(self, index: int) -> None:
        self.select(index)

    def _rebuild_positions(self) -> None:
        for index, button in enumerate(self._buttons):
            try:
                button.node.setPos(0.0, 0.0, -index * self._item_height)
            except Exception:  # noqa: BLE001
                pass

    def destroy(self) -> None:
        if self.destroyed:
            return
        self.clear()
        super().destroy()
