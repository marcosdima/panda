# Navigation

Grid-based navigation helpers used by `AINavigationHandler`.

- `NavGrid`: 2D grid with blocked cells and coordinate conversion.
- `GridPathfinder`: A* over `NavGrid`.
- `smooth_path`: remove redundant waypoints via line-of-sight.

The grid is manual in this first iteration; automatic generation from world
geometry is planned for a later iteration.
