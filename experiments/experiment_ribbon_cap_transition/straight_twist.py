"""
Freeze a straight-path twist-only diagnostic, not a routing or compliance solver.
"""

from __future__ import annotations

import math

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_secure_discrete_ribbon.frames import RibbonFrame

LENGTH_MM = 57.0
SECTIONS = 32
TWISTS_DEGREES = (0.0, 180.0, 360.0)


def twist_frames(degrees: float) -> tuple[RibbonFrame, ...]:
    """
    Author fixed parallel sections with quintic roll and unchanged center targets.
    """
    if not math.isfinite(degrees):
        raise ValueError("Twist must be finite.")
    frames = []
    for index in range(SECTIONS):
        fraction = index / (SECTIONS - 1)
        ease = fraction**3 * (10 - 15 * fraction + 6 * fraction**2)
        angle = math.radians(degrees) * ease
        frames.append(
            RibbonFrame(
                Vector3(0.0, 0.0, LENGTH_MM * fraction),
                Vector3(0.0, 0.0, 1.0),
                Vector3(math.cos(angle), math.sin(angle), 0.0),
                Vector3(-math.sin(angle), math.cos(angle), 0.0),
            )
        )
    return tuple(frames)


def rate_metrics(degrees: float) -> dict[str, float]:
    """
    Separate analytic authored peak from maximum finite station increment.
    """
    frames = twist_frames(degrees)
    increments = [
        abs(
            math.degrees(
                math.atan2(
                    left.width.x * right.width.y - left.width.y * right.width.x,
                    left.width.x * right.width.x + left.width.y * right.width.y,
                )
            )
        )
        for left, right in zip(frames, frames[1:])
    ]
    return {
        "analytic_peak_degrees_per_mm": abs(degrees) * 1.875 / LENGTH_MM,
        "maximum_station_increment_degrees": max(increments),
        "maximum_station_rate_degrees_per_mm": max(increments) / (LENGTH_MM / 31),
    }


def section_arcs() -> tuple[tuple[tuple[float, float], ...], ...]:
    """
    Retain the original 19-lobe 40-arc planar contour, including circular side caps.

    Nominal dimensions are 28.5 by 1.5 mm; side-cap extrema reach +/-14.4 mm.
    No physical midpoint vertices or edge guides are needed for this control.
    """
    arcs = []
    for index in range(19):
        left = -14.25 + 1.5 * index
        right = left + 1.5
        center = (left + right) / 2
        arcs.extend(
            (
                ((left, 0.45), (center, 0.75), (right, 0.45)),
                ((right, -0.45), (center, -0.75), (left, -0.45)),
            )
        )
    arcs.extend(
        (
            ((14.25, 0.45), (14.4, 0.0), (14.25, -0.45)),
            ((-14.25, -0.45), (-14.4, 0.0), (-14.25, 0.45)),
        )
    )
    return tuple(arcs)
