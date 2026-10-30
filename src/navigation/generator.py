from __future__ import annotations

from collections.abc import Sequence

from panda3d.core import Vec3

from .grid import NavGrid


def generate_nav_grid(
    bounds_min: Sequence[float] = (-20.0, -20.0),
    bounds_max: Sequence[float] = (20.0, 20.0),
    cell_size: float = 1.0,
    scan_height: float = 10.0,
    max_walkable_height: float = 0.5,
    obstacle_mask=None,
) -> NavGrid:
    """Build a :class:`NavGrid` by probing the world with vertical raycasts.

    A cell is walkable when a ray cast from above hits something whose impact
    height is close to the ground (i.e. not a wall or elevated obstacle).
    """
    from src.globals.physics import Physics
    from src.handlers.physics.groups import LineOfSight

    if obstacle_mask is None:
        obstacle_mask = LineOfSight.QUERY_MASK

    min_x, min_y = float(bounds_min[0]), float(bounds_min[1])
    max_x, max_y = float(bounds_max[0]), float(bounds_max[1])
    cols = max(1, int((max_x - min_x) / cell_size))
    rows = max(1, int((max_y - min_y) / cell_size))
    origin = Vec3(min_x, min_y, 0.0)
    grid = NavGrid(cols, rows, cell_size=cell_size, origin=origin)

    for x in range(cols):
        for y in range(rows):
            center = grid.cell_to_world((x, y))
            start = Vec3(center.x, center.y, scan_height)
            end = Vec3(center.x, center.y, -scan_height)
            try:
                hit = Physics.raycast_closest(
                    start, end, obstacle_mask, step_physics=False
                )
            except (RuntimeError, TypeError, AttributeError, ImportError, ValueError):
                hit = None
            if hit is None:
                grid.block((x, y))
                continue
            point, _node = hit
            if point.z > max_walkable_height:
                grid.block((x, y))
    return grid
