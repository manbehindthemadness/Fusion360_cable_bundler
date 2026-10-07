"""
Preserve requested full-turn motion as a smooth bounded out-and-back roll.
"""

import math

from .prescribed_twist import PrescribedTwistDiagnostic


class ReflectedTwistDiagnostic(PrescribedTwistDiagnostic):
    """
    Replace requested+/-360 winding by0 -> +/-180 ->0 about the path tangent.

    Two quintic halves have zero first/second derivatives at both caps and the
    reversal. This is bounded orientation excursion, not retained full winding
    or a native twist-rate/spacing/strain certificate. Other requests reject.
    """

    @property
    def field_description(self) -> str:
        """
        Distinguish reflected excursion from both winding and a zero-roll field.
        """
        return "Two C2 quintic halves:0 -> signed180 ->0; requested signed360, no bank search."

    def angles(self, distances_mm: tuple[float, ...], end_angle: float) -> tuple[float, ...]:
        """
        Validate frozen caps and return a bounded, smooth lengthwise roll field.
        """
        if abs(self.degrees) != 360:
            raise ValueError("Reflected diagnostic requires requested +/-360 degrees.")
        super().angles(distances_mm, end_angle)
        total = distances_mm[-1]
        peak = math.copysign(math.pi, self.degrees)
        result = []
        for distance in distances_mm:
            fraction = distance / total
            phase = 2 * min(fraction, 1 - fraction)
            eased = 10 * phase**3 - 15 * phase**4 + 6 * phase**5
            result.append(peak * eased)
        return (0.0, *result[1:-1], 0.0)
