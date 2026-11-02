"""
Share the unconstrained endpoint-tangent pre-path between solving and gym displays.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from cable_bundler.routing.geometry import CubicBezier, Vector3, difference, magnitude

from .contracts import TargetPose


def controls(targets: TargetPose) -> tuple[Vector3, Vector3, Vector3, Vector3]:
    """
    Preserve the solver's chord/3 handles and directed arrival without fitting a route.
    """
    chord = magnitude(difference(targets.end, targets.start))
    if chord <= 1e-8:
        raise ValueError("Distinct endpoints required for the chord-scaled guide.")
    return (
        targets.start,
        targets.start.translated(targets.start_tangent, chord / 3),
        targets.end.translated(targets.end_tangent, -chord / 3),
        targets.end,
    )


def drawing(targets: TargetPose) -> dict[str, Any]:
    """
    Return exact cubic controls and129display samples without changing frozen gym payloads.

    Controls define the native curve; samples are for the palette canvas only.
    This reference ignores physical rules and is not an accepted ribbon route.
    """
    points = controls(targets)
    curve = CubicBezier(*points)
    return {
        "controls": [asdict(point) for point in points],
        "points": [asdict(curve.point(i / 128)) for i in range(129)],
    }
