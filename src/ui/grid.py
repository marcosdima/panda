"""Simple grid layout container."""

from __future__ import annotations

from panda3d.core import NodePath

from .base import UIComponent


class UIGrid(UIComponent):
    """Lay children out in a fixed number of columns."""

    def __init__(
        self,
        parent: object,
        columns: int = 2,
        spacing: tuple[float, float] = (0.02, 0.02),
        owner: object = None,
        pos: tuple[float, ...] = (0.0, 0.0),
    ) -> None:
        self._columns = max(1, int(columns))
        self._spacing_x, self._spacing_z = float(spacing[0]), float(spacing[1])
        self._pos = self._normalize_pos(pos)
        self._children: list[object] = []

        node = NodePath("ui_grid")
        try:
            node.reparentTo(parent)
            node.setPos(self._pos)
        except Exception:  # noqa: BLE001
            pass

        super().__init__(node=node, owner=owner)
        self.node = node

    @staticmethod
    def _normalize_pos(pos: tuple[float, ...]) -> tuple[float, float, float]:
        if len(pos) == 2:
            return (float(pos[0]), 0.0, float(pos[1]))
        if len(pos) == 3:
            return (float(pos[0]), float(pos[1]), float(pos[2]))
        raise ValueError("pos must have 2 or 3 components")

    @staticmethod
    def _node_of(child: object):
        return getattr(child, "node", child)

    @staticmethod
    def _size(child: object) -> tuple[float, float]:
        node = UIGrid._node_of(child)
        try:
            mins, maxs = node.getTightBounds()
            if mins is not None and maxs is not None:
                return (float(maxs.x - mins.x), float(maxs.z - mins.z))
        except Exception:  # noqa: BLE001
            pass
        return (0.2, 0.1)

    def add(self, child: object) -> None:
        node = self._node_of(child)
        try:
            node.reparentTo(self.node)
        except Exception:  # noqa: BLE001
            pass
        self._children.append(child)
        self.relayout()

    def relayout(self) -> None:
        if not self._children:
            return
        sizes = [self._size(child) for child in self._children]
        cell_width = max(size[0] for size in sizes) + self._spacing_x
        cell_height = max(size[1] for size in sizes) + self._spacing_z

        rows = (len(self._children) + self._columns - 1) // self._columns
        total_width = self._columns * cell_width - self._spacing_x
        total_height = rows * cell_height - self._spacing_z

        for index, child in enumerate(self._children):
            row = index // self._columns
            col = index % self._columns
            size = sizes[index]
            node = self._node_of(child)
            x = -total_width / 2.0 + col * cell_width + size[0] / 2.0
            z = total_height / 2.0 - row * cell_height - size[1] / 2.0
            try:
                node.setPos(x, 0.0, z)
            except Exception:  # noqa: BLE001
                pass

    def destroy(self) -> None:
        if self.destroyed:
            return
        for child in list(self._children):
            try:
                destroy = getattr(child, "destroy", None)
                if callable(destroy):
                    destroy()
            except Exception:  # noqa: BLE001
                pass
        self._children.clear()
        super().destroy()
