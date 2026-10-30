"""Vertical layout container."""

from __future__ import annotations

from panda3d.core import NodePath

from .base import UIComponent


class UIColumn(UIComponent):
    """Lay children out vertically with consistent spacing."""

    def __init__(
        self,
        parent: object,
        spacing: float = 0.02,
        owner: object = None,
        pos: tuple[float, ...] = (0.0, 0.0),
    ) -> None:
        self._spacing = float(spacing)
        self._pos = self._normalize_pos(pos)
        self._children: list[object] = []

        node = NodePath("ui_column")
        try:
            node.reparentTo(parent)
            node.setPos(self._pos)
        except Exception:  # noqa: BLE001, S110
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
        node = UIColumn._node_of(child)
        try:
            mins, maxs = node.getTightBounds()
            if mins is not None and maxs is not None:
                return (float(maxs.x - mins.x), float(maxs.z - mins.z))
        except Exception:  # noqa: BLE001, S110
            pass
        return (0.2, 0.1)

    def add(self, child: object) -> None:
        node = self._node_of(child)
        try:
            node.reparentTo(self.node)
        except Exception:  # noqa: BLE001, S110
            pass
        self._children.append(child)
        self.relayout()

    def relayout(self) -> None:
        sizes = [self._size(child) for child in self._children]
        total_height = sum(size[1] for size in sizes) + self._spacing * max(
            len(sizes) - 1, 0
        )
        z = total_height / 2.0
        for child, size in zip(self._children, sizes):
            node = self._node_of(child)
            try:
                node.setPos(0.0, 0.0, z - size[1] / 2.0)
            except Exception:  # noqa: BLE001, S110
                pass
            z -= size[1] + self._spacing

    def destroy(self) -> None:
        if self.destroyed:
            return
        for child in list(self._children):
            try:
                destroy = getattr(child, "destroy", None)
                if callable(destroy):
                    destroy()
            except Exception:  # noqa: BLE001, S110
                pass
        self._children.clear()
        super().destroy()
