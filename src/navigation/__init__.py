from .generator import generate_nav_grid
from .grid import NavGrid
from .pathfinder import GridPathfinder
from .smoothing import smooth_path

# Compatibility aliases for alternative naming.
Pathfinder = GridPathfinder
AStar = GridPathfinder
PathFinder = GridPathfinder

__all__ = [
    "AStar",
    "GridPathfinder",
    "NavGrid",
    "PathFinder",
    "Pathfinder",
    "generate_nav_grid",
    "smooth_path",
]
