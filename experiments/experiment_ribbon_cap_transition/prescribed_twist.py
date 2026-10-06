"""
Prescribe a signed diagnostic roll without bank search or changed tube certification.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PrescribedTwistDiagnostic:
    """
    Apply one global quintic roll matching an independently authored end guide.

    Only the experimental bank-rate restriction is bypassed. Endpoint orientation,
    distances, material, curve certificate and exact cap flow remain authoritative.
    """

    degrees: float

    def angles(self, distances_mm: tuple[float, ...], end_angle: float) -> tuple[float, ...]:
        """
        Retain signed winding, rejecting malformed inputs or incompatible end roll.
        """
        if (
            len(distances_mm) < 3
            or any(not math.isfinite(value) for value in (*distances_mm, end_angle, self.degrees))
            or distances_mm[0] != 0
            or any(b <= a for a, b in zip(distances_mm, distances_mm[1:]))
            or abs(self.degrees) > 360
        ):
            raise ValueError(
                "Diagnostic twist requires increasing finite distances and <=360 degrees."
            )
        roll = math.radians(self.degrees)
        error = math.atan2(math.sin(end_angle - roll), math.cos(end_angle - roll))
        if abs(error) > 1e-8:
            raise ValueError("Prescribed twist differs from frozen end-guide orientation.")
        total = distances_mm[-1]
        result = tuple(
            roll * (10 * (d / total) ** 3 - 15 * (d / total) ** 4 + 6 * (d / total) ** 5)
            for d in distances_mm
        )
        return (0.0, *result[1:-1], roll)
