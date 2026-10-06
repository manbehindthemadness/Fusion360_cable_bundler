"""
Prescribe an explicit diagnostic full turn without claiming safe bank rate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class FullTurnDiagnostic:
    """
    Author one positive 360-degree roll with global quintic distance easing.

    This user-authorized native diagnostic bypasses ONLY the experimental
    width-scaled bank-rate constraint. It never changes spacing, route, targets,
    macaroni certification or length policy. Endpoint width must match transported
    start width; a half-twist target is rejected, not turned into 540 degrees.
    """

    def angles(self, distances_mm: tuple[float, ...], end_angle: float) -> tuple[float, ...]:
        """
        Return a fixed full-turn field, preserving winding rather than shortest roll.

        Reject malformed distance coordinates and incompatible endpoint roll.
        Quintic easing has zero first/second roll derivatives at either endpoint
        relative to ideal transport, not a native skin tangency certificate.
        """
        if (
            len(distances_mm) < 3
            or any(not math.isfinite(value) for value in (*distances_mm, end_angle))
            or distances_mm[0] != 0
            or any(b <= a for a, b in zip(distances_mm, distances_mm[1:]))
        ):
            raise ValueError("Full-turn distances must start at zero and increase finitely.")
        if abs(end_angle) > 1e-8:
            raise ValueError(
                "Full-turn endpoint width must match parallel-transported start width."
            )
        total = distances_mm[-1]
        angles = []
        for distance in distances_mm:
            u = distance / total
            angles.append(2 * math.pi * (10 * u**3 - 15 * u**4 + 6 * u**5))
        angles[0], angles[-1] = 0.0, 2 * math.pi
        return tuple(angles)
