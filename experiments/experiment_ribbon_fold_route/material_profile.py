"""
Retain the joined circular contour as ordered rational quadratic segments.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .sweep_profile import joined_profile_arcs


@dataclass(frozen=True)
class MaterialArc:
    """
    Preserve clockwise material coordinates, including explicit outer-tip vertices.
    """

    controls: tuple[tuple[float, float], ...]
    weights: tuple[float, ...]
    label: str

    def point(self, parameter: float) -> tuple[float, float]:
        """
        Evaluate the exact rational circle segment in width/thickness coordinates.
        """
        basis = ((1 - parameter) ** 2, 2 * parameter * (1 - parameter), parameter**2)
        factors = [a * b for a, b in zip(basis, self.weights)]
        denominator = math.fsum(factors)
        q = math.fsum(factor * point[0] for factor, point in zip(factors, self.controls))
        b = math.fsum(factor * point[1] for factor, point in zip(factors, self.controls))
        return q / denominator, b / denominator


def material_profile(lines: int, diameter_mm: float) -> tuple[MaterialArc, ...]:
    """
    Represent the unchanged joined outline, splitting only the two side-cap arcs.

    Explicit tip vertices permit triangular flat lead faces when an oblique
    crease first touches an outer material tip. No dimensions or pitch change.
    """
    originals = joined_profile_arcs(lines, diameter_mm)
    half = diameter_mm / 2
    valley = 0.6 * half
    extension = 0.2 * half
    nominal = lines * diameter_mm / 2
    radius = originals[0].radius
    cy = originals[0].center[1]
    weight = (valley - cy) / radius
    high = cy + radius / weight
    top = []
    bottom = []
    for lane in range(lines):
        left = -nominal + lane * diameter_mm
        right = -nominal + (lane + 1) * diameter_mm
        center = -nominal + (lane + 0.5) * diameter_mm
        top.append(
            MaterialArc(
                ((left, valley), (center, high), (right, valley)), (1.0, weight, 1.0), f"top-{lane}"
            )
        )
        bottom.append(
            MaterialArc(
                ((right, -valley), (center, -high), (left, -valley)),
                (1.0, weight, 1.0),
                f"bottom-{lane}",
            )
        )
    cap_radius = originals[-2].radius
    cx = originals[-2].center[0]
    phase = math.atan2(valley, nominal - cx)
    cap_weight = math.cos(phase / 2)
    control_q = cx + cap_radius * math.cos(phase / 2) / cap_weight
    control_b = cap_radius * math.sin(phase / 2) / cap_weight
    right_caps = (
        MaterialArc(
            ((nominal, valley), (control_q, control_b), (nominal + extension, 0.0)),
            (1.0, cap_weight, 1.0),
            "right-top",
        ),
        MaterialArc(
            ((nominal + extension, 0.0), (control_q, -control_b), (nominal, -valley)),
            (1.0, cap_weight, 1.0),
            "right-bottom",
        ),
    )
    left_caps = tuple(
        MaterialArc(
            tuple((-q, -b) for q, b in arc.controls),
            arc.weights,
            "left-bottom" if arc.label == "right-top" else "left-top",
        )
        for arc in right_caps
    )
    return tuple(top) + right_caps + tuple(reversed(bottom)) + left_caps
