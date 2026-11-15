"""
Size the next normalized correction from measured endpoint linearization disagreement.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from experiments.experiment_ribbon_terminal_hardware.projection_system import CoordinateBounds


def interior_terms(terms: tuple[float, ...], touching_rows: frozenset[int]) -> tuple[float, ...]:
    """
    Reserve half existing negative physical slack in the one linear projection.

    Call only after a nonlinear trial loses an already satisfied inequality.
    Caps, positive guidance and actual source-mating whole-member rows retain
    their exact equations. Raw nonlinear residuals and final physical goals
    remain unchanged; this only keeps a proposed step away from known curved
    boundaries. No new row, projection or trial is allocated.
    """
    return tuple(
        0.5 * term if index >= 6 and index not in touching_rows and term < 0 else term
        for index, term in enumerate(terms)
    )


@dataclass(frozen=True)
class LocalBox:
    """
    Intersect physical coordinate bounds with a current local normalized-motion box.

    Only the one existing projector sees this smaller search domain. No physical
    face moves, no new candidate is created, and final admissibility remains the
    original geometry model's responsibility. Infinite radius retains its bounds.
    """

    model: CoordinateBounds
    values: tuple[float, ...]
    radius: float

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Keep each proposed coordinate within both the original and local bounds.
        """
        low, high = self.model.bounds(index)
        return max(low, self.values[index] - self.radius), min(
            high, self.values[index] + self.radius
        )


def radius(
    before: tuple[float, ...],
    after: tuple[float, ...],
    rows: list[list[float]],
    residual: tuple[float, ...],
    observed: tuple[float, ...],
    *,
    previous_radius: float = 0.0,
) -> float:
    """
    Reserve one quarter of the remaining merit for estimated quadratic cap-model error.

    Coordinates use the existing normalized lengths and radian banks. Compare
    actual cap equations with their prediction along the accepted displacement;
    no extra placement, derivative or trial is requested. Agreement within the
    reserved quarter preserves the previous box, with growth to twice the
    accepted displacement. A small step limited by a physical coordinate face
    therefore cannot collapse unrelated motion despite an accurate cap model.
    Larger disagreement contracts from the measured displacement as before.
    This is a next-step heuristic,
    never a certificate or a replacement for physical and actual-descent gates.
    """
    step = tuple(b - a for a, b in zip(before, after))
    distance = max(abs(value) for value in step)
    predicted = tuple(
        r + math.fsum(a * b for a, b in zip(row, step)) for r, row in zip(residual[:6], rows[:6])
    )
    error = max(abs(a - b) for a, b in zip(predicted, observed[:6]))
    merit = max(abs(value) if i < 6 else max(0.0, value) for i, value in enumerate(observed))
    if error <= 0.25 * merit:
        return max(previous_radius, 2 * distance)
    return distance * min(2.0, math.sqrt(0.25 * merit / error))
