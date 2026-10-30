from __future__ import annotations

import heapq
import math
from collections.abc import Sequence

from panda3d.core import Vec3

from .grid import NavGrid


class GridPathfinder:
    """A* pathfinder operating on a :class:`NavGrid`."""

    def __init__(self, grid: NavGrid) -> None:
        self.grid = grid

    def find_path(
        self,
        start: Vec3 | Sequence[float],
        goal: Vec3 | Sequence[float],
    ) -> list[Vec3] | None:
        """Return a list of world positions from ``start`` to ``goal``.

        The starting cell is excluded from the result; the goal cell is
        included. Returns ``None`` when no path exists or either endpoint is
        outside the grid or blocked. Returns an empty list when both endpoints
        fall in the same cell.
        """
        start_cell = self.grid.world_to_cell(start)
        goal_cell = self.grid.world_to_cell(goal)
        if start_cell is None or goal_cell is None:
            return None
        if not self.grid.is_walkable(start_cell) or not self.grid.is_walkable(
            goal_cell
        ):
            return None
        if start_cell == goal_cell:
            return []

        # A*.
        open_heap: list[tuple[float, int, tuple[int, int]]] = []
        counter = 0
        heapq.heappush(open_heap, (0.0, counter, start_cell))
        came_from: dict[tuple[int, int], tuple[int, int] | None] = {start_cell: None}
        g_score: dict[tuple[int, int], float] = {start_cell: 0.0}

        while open_heap:
            _, _, current = heapq.heappop(open_heap)
            if current == goal_cell:
                break
            for neighbour, cost in self.grid.neighbors(current):
                tentative = g_score[current] + cost
                if neighbour not in g_score or tentative < g_score[neighbour]:
                    g_score[neighbour] = tentative
                    came_from[neighbour] = current
                    priority = tentative + self._heuristic(neighbour, goal_cell)
                    counter += 1
                    heapq.heappush(open_heap, (priority, counter, neighbour))

        if goal_cell not in came_from:
            return None

        # Reconstruct.
        cells: list[tuple[int, int]] = []
        cur: tuple[int, int] | None = goal_cell
        while cur is not None:
            cells.append(cur)
            cur = came_from[cur]
        cells.reverse()
        return [self.grid.cell_to_world(c) for c in cells]

    @staticmethod
    def _heuristic(a: tuple[int, int], b: tuple[int, int]) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])
