"""
Prepare bounded continuous cubic display approximations without changing routes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from cable_bundler.routing.geometry import CubicBezier, Vector3

from .contracts import RibbonPath
from .provenance import mark_loaded


def cubic_controls(
    jet: Callable[[float], tuple[Vector3, Vector3]], intervals: int = 64
) -> tuple[tuple[Vector3, ...], tuple[float, ...]]:
    """
    Sample position/velocity into one clamped piecewise cubic Hermite curve.

    Preserve endpoint positions and first derivatives. Interior curvature remains
    an approximation to be measured natively. Restrict16..1024intervals to bound
    host work;invalid values reject without silently changing resolution.
    """
    if isinstance(intervals, bool) or not isinstance(intervals, int) or not 16 <= intervals <= 1024:
        raise ValueError("Use an integer display interval count within16..1024.")
    points = [jet(0)[0]]
    step = 1 / intervals
    for index in range(intervals):
        p, v = jet(index / intervals)
        q, w = jet((index + 1) / intervals)
        points.extend((p.translated(v, step / 3), q.translated(w, -step / 3), q))
    knots = (
        (0.0,) * 4
        + tuple(i / intervals for i in range(1, intervals) for _ in range(3))
        + (1.0,) * 4
    )
    return tuple(points), knots


@dataclass(frozen=True)
class TracePath:
    """
    Retain an ordered exact cubic chain and its equivalent clamped NURBS controls.
    """

    number: int
    curves: tuple[CubicBezier, ...]
    controls: tuple[Vector3, ...]
    knots: tuple[float, ...]


def trace(path: RibbonPath, number: int, offset: float) -> TracePath:
    """
    Preserve one lane's position and velocity in512cubic intervals without repair.
    """

    def jet(u: float) -> tuple[Vector3, Vector3]:
        """
        Evaluate one fixed material offset without altering endpoints.
        """
        return path.lane(u, offset)

    controls, knots = cubic_controls(jet, 512)
    curves = tuple(CubicBezier(*controls[i : i + 4]) for i in range(0, len(controls) - 1, 3))
    return TracePath(number, curves, controls, knots)


mark_loaded(__file__)
