from __future__ import annotations

from typing import Callable, Sequence

from panda3d.core import Vec3


def smooth_path(
    path: Sequence[Vec3],
    is_clear: Callable[[Vec3, Vec3], bool],
) -> list[Vec3]:
    """Remove redundant waypoints using a line-of-sight test.

    ``is_clear(a, b)`` must return ``True`` when the straight segment between
    the two points is unobstructed. The first and last points are always kept.
    """
    pts = [Vec3(p) for p in path]
    if len(pts) <= 2:
        return pts

    result: list[Vec3] = [pts[0]]
    i = 0
    n = len(pts)
    while i < n - 1:
        # Find the farthest point visible from pts[i].
        farthest = i + 1
        for j in range(n - 1, i + 1, -1):
            if is_clear(pts[i], pts[j]):
                farthest = j
                break
        if farthest == i + 1:
            i += 1
            if i < n:
                result.append(pts[i])
        else:
            i = farthest
            if i < n:
                result.append(pts[i])
    # Ensure the last point is present.
    if result[-1] != pts[-1]:
        result.append(pts[-1])
    # De-duplicate consecutive equal points.
    deduped: list[Vec3] = [result[0]]
    for p in result[1:]:
        if (p - deduped[-1]).length_squared() > 1e-12:
            deduped.append(p)
    if deduped[-1] != pts[-1]:
        deduped.append(pts[-1])
    return deduped
