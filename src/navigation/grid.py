from __future__ import annotations

import math
from typing import Iterable, Sequence

from panda3d.core import Vec3


class NavGrid:
    """A 2D grid used for A* pathfinding on the X/Y plane.

    Parameters
    ----------
    width, height:
        Number of cells along X and Y.
    cell_size:
        World size of a single cell.
    origin:
        World position of the grid's lower-left corner.
    """

    def __init__(
        self,
        width=None,
        height=None,
        cell_size: float = 1.0,
        origin: Vec3 | None = None,
        cols=None,
        rows=None,
        size=None,
        dimensions=None,
        **kwargs,
    ) -> None:
        if size is not None:
            if isinstance(size, (tuple, list)):
                width, height = size[0], size[1]
            else:
                width = height = size
        if dimensions is not None:
            if isinstance(dimensions, (tuple, list)):
                width, height = dimensions[0], dimensions[1]
            else:
                width = height = dimensions
        if cols is not None:
            width = cols
        if rows is not None:
            height = rows
        if "cell_size" in kwargs:
            cell_size = kwargs.pop("cell_size")
        if width is None or height is None:
            # Allow NavGrid(cell_size=..., width=..., height=...) style.
            width = kwargs.pop("width", kwargs.pop("w", None))
            height = kwargs.pop("height", kwargs.pop("h", None))
        if width is None or height is None:
            raise TypeError("NavGrid requires width and height")
        if cell_size is None:
            cell_size = 1.0
        if width <= 0 or height <= 0:
            raise ValueError("width and height must be positive")
        if cell_size <= 0:
            raise ValueError("cell_size must be positive")
        self.width = int(width)
        self.height = int(height)
        self.cell_size = float(cell_size)
        if origin is None:
            self.origin = Vec3(0.0, 0.0, 0.0)
        elif isinstance(origin, Vec3):
            self.origin = Vec3(origin)
        else:
            self.origin = Vec3(*origin)
        self._blocked: set[tuple[int, int]] = set()

    # --- cells -----------------------------------------------------------

    def in_bounds(self, cell: tuple[int, int]) -> bool:
        x, y = cell
        return 0 <= x < self.width and 0 <= y < self.height

    def is_walkable(self, cell: tuple[int, int]) -> bool:
        return self.in_bounds(cell) and cell not in self._blocked

    def block(self, cell: tuple[int, int]) -> None:
        if self.in_bounds(cell):
            self._blocked.add(cell)

    def unblock(self, cell: tuple[int, int]) -> None:
        self._blocked.discard(cell)

    def set_blocked(self, cells: Iterable[tuple[int, int]]) -> None:
        for cell in cells:
            self.block(cell)

    def clear_blocked(self) -> None:
        self._blocked.clear()

    @property
    def blocked(self) -> frozenset[tuple[int, int]]:
        return frozenset(self._blocked)

    # --- coordinate conversion ------------------------------------------

    def world_to_cell(self, pos: Vec3 | Sequence[float]) -> tuple[int, int] | None:
        x = (float(pos[0]) - self.origin.x) / self.cell_size
        y = (float(pos[1]) - self.origin.y) / self.cell_size
        cell = (math.floor(x), math.floor(y))
        if not self.in_bounds(cell):
            return None
        return cell

    def cell_to_world(self, cell: tuple[int, int]) -> Vec3:
        x, y = cell
        return Vec3(
            self.origin.x + (x + 0.5) * self.cell_size,
            self.origin.y + (y + 0.5) * self.cell_size,
            self.origin.z,
        )

    # --- neighbourhood ---------------------------------------------------

    def find_path(self, start, goal):
        from .pathfinder import GridPathfinder

        return GridPathfinder(self).find_path(start, goal)


    def neighbors(self, cell: tuple[int, int]) -> list[tuple[tuple[int, int], float]]:
        """Return (neighbour, cost) pairs for the four cardinal directions."""
        x, y = cell
        result: list[tuple[tuple[int, int], float]] = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb = (x + dx, y + dy)
            if self.is_walkable(nb):
                result.append((nb, 1.0))
        return result
