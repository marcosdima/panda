"""Scalar math helper utilities.

This module provides small, pure‑Python functions that are frequently needed
in game‑logic or physics code. They deliberately avoid any external
dependencies, keeping the utilities safe to import from any part of the
project (including the low‑level engine handlers).

All functions operate on ``float`` values and are type‑annotated for static
analysis support.
"""

from __future__ import annotations

Number = float


def clamp(value: Number, minimum: Number, maximum: Number) -> float:
    """Clamp *value* into the inclusive range ``[minimum, maximum]``.

    Parameters
    ----------
    value:
        The numeric value to clamp.
    minimum:
        Lower bound of the allowed range.
    maximum:
        Upper bound of the allowed range.

    Returns
    -------
    float
        ``minimum`` if ``value`` is smaller, ``maximum`` if larger, otherwise
        ``value`` converted to ``float``.
    """

    if minimum > maximum:
        raise ValueError("minimum cannot be greater than maximum")
    # ``float`` conversion ensures a consistent return type.
    return float(max(minimum, min(value, maximum)))


def lerp(start: Number, end: Number, t: Number) -> float:
    """Linear interpolation between *start* and *end*.

    Parameters
    ----------
    start, end:
        Values returned for ``t == 0`` and ``t == 1``.
    t:
        Interpolation factor. Expected in ``[0, 1]`` but not clamped; combine
        with :func:`clamp` if desired.
    """

    return float(start + (end - start) * t)


def smoothstep(edge0: Number, edge1: Number, x: Number) -> float:
    """Smoothstep interpolation.

    The classic Hermite interpolation that eases in and out. The result is
    clamped to ``[0, 1]``.

    Parameters
    ----------
    edge0, edge1:
        Edges of the transition. ``edge0 > edge1`` is allowed and yields a
        descending curve. Equal edges raise ``ValueError``.
    x:
        Input value.
    """

    if edge0 == edge1:
        raise ValueError("edge0 and edge1 must be distinct values")
    # Scale and clamp ``x`` into ``[0, 1]``.
    t = clamp((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    # Hermite polynomial 3t^2 - 2t^3
    return float(t * t * (3.0 - 2.0 * t))


def normalize_angle(degrees: Number, minimum: Number = -180.0) -> float:
    """Wrap *degrees* into the half-open range ``[minimum, minimum + 360)``.

    Parameters
    ----------
    degrees:
        Angle in degrees.
    minimum:
        Lower bound of the output range (default ``-180`` gives ``[-180, 180)``;
        use ``0`` for ``[0, 360)``).
    """

    return float((degrees - minimum) % 360.0 + minimum)


def lerp_angle(start: Number, end: Number, t: Number) -> float:
    """Interpolate between two angles (degrees) along the shortest arc.

    The result is not normalised; wrap it with :func:`normalize_angle` if needed.
    """

    delta = normalize_angle(end - start)
    return float(start + delta * t)


def remap(
    value: Number,
    in_min: Number,
    in_max: Number,
    out_min: Number,
    out_max: Number,
    clamp_result: bool = False,
) -> float:
    """Map *value* from ``[in_min, in_max]`` to ``[out_min, out_max]``.

    Raises
    ------
    ValueError
        If ``in_min == in_max``.
    When *clamp_result* is true the output is limited to the output range.
    """

    if in_min == in_max:
        raise ValueError("in_min and in_max must be distinct values")
    t = (value - in_min) / (in_max - in_min)
    if clamp_result:
        t = clamp(t, 0.0, 1.0)
    return float(out_min + (out_max - out_min) * t)
