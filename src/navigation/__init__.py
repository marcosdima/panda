"""Navigation helpers for grid-based pathfinding.

This package is intentionally independent of Panda3D/Bullet where possible so
that pathfinding can be exercised headless and deterministically. The grid
operates on the X/Y plane; the Z coordinate is carried through but does not
participate in routing.
"""

from .grid import NavGrid
from .pathfinder import GridPathfinder
from .smoothing import smooth_path

# Compatibility aliases for alternative naming.
Pathfinder = GridPathfinder
AStar = GridPathfinder
PathFinder = GridPathfinder

__all__ = ["AStar", "GridPathfinder", "NavGrid", "PathFinder", "Pathfinder", "smooth_path"]
