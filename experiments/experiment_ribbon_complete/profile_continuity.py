"""
Bound original elliptic profile variation without requiring a finite slope at stationary-width endpoints.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import InitVar, dataclass, field
from fractions import Fraction
from typing import Protocol

from artifacts.verification.resume3204.polynomial import Polynomial, add, derivative, multiply
from experiments.experiment_ribbon_fold_route.material_profile import MaterialArc

from .profile_conic import EllipseArc
from .ruled_support import square_root_upper


class OriginalProfileQDomain(Protocol):
    """
    Expose the same original conic and certified finite q interval without requiring a finite graph slope.
    """

    @property
    def conic(self) -> EllipseArc:
        """
        Retain the original ordered rational profile and its derived ellipse.
        """
        ...

    @property
    def interval(self) -> tuple[Fraction, Fraction]:
        """
        Bound the complete monotone original q image, including stationary endpoints.
        """
        ...


def ordered_profile_q(domain: OriginalProfileQDomain) -> tuple[Fraction, Fraction]:
    """
    Traverse the qualified q interval in the original profile direction without replacing original controls.
    """
    first, last = (
        Fraction(point[0])
        for point in (domain.conic.arc.controls[0], domain.conic.arc.controls[-1])
    )
    if first == last:
        raise ValueError("A monotone original profile direction required")
    low, high = domain.interval
    return (low, high) if first < last else (high, low)


def derivative_numerators(arc: MaterialArc) -> tuple[Polynomial, Polynomial]:
    """
    Derive exact rational q/b derivative numerators with the shared positive denominator omitted.
    """
    weights = tuple(map(Fraction, arc.weights))
    output = []
    for axis in range(2):
        numerator = tuple(
            Fraction(point[axis]) * weight for point, weight in zip(arc.controls, weights)
        )
        output.append(
            add(
                multiply(derivative(numerator), weights),
                multiply(numerator, derivative(weights)),
                Fraction(-1),
            )
        )
    return output[0], output[1]


@dataclass(frozen=True)
class ProfileContinuity:
    """
    Certify an original q graph with a linear plus square-root variation bound.

    Completing the ellipse square gives (b-cb+h/c*(q-cq))²=R(q).
    A single signed branch and monotone q retain the exact original arc, even
    when its endpoint q derivative vanishes. The inequality
    |sqrt(u)-sqrt(v)|<=sqrt(|u-v|) supplies continuity without finite slope.
    Interior turning, branch ambiguity and degenerate inputs stay unsupported;
    this certificate alone grants no native coverage or material compatibility.
    """

    conic: EllipseArc
    checkpoint: InitVar[Callable[[], None]]
    interval: tuple[Fraction, Fraction] = field(init=False)
    linear_coefficient: Fraction = field(init=False)
    radical_coefficient_mm: Fraction = field(init=False)

    def __post_init__(self, checkpoint: Callable[[], None]) -> None:
        """
        Derive every coefficient from the same original conic and validate a unique monotone graph branch.
        """
        checkpoint()
        q, _ = derivative_numerators(self.conic.arc)
        if not ((min(q) >= 0 and max(q) > 0) or (max(q) <= 0 and min(q) < 0)):
            raise ValueError("A certified monotone original q graph required")
        matrix = self.conic.matrix
        a, h, c = matrix[0][0], matrix[0][1], matrix[1][1]
        cq, cb = self.conic.center
        values = tuple(
            Fraction(b) - cb + h / c * (Fraction(q) - cq) for q, b in self.conic.arc.controls
        )
        if not ((min(values) >= 0 and max(values) > 0) or (max(values) <= 0 and min(values) < 0)):
            raise ValueError("A single signed original ellipse graph branch required")
        ends = sorted(
            Fraction(point[0])
            for point in (self.conic.arc.controls[0], self.conic.arc.controls[-1])
        )
        if ends[0] >= ends[1]:
            raise ValueError("A nonempty original q interval required")
        coefficient = 2 * (a * c - h * h) / (c * c) * max(abs(q - cq) for q in ends)
        object.__setattr__(self, "interval", (ends[0], ends[1]))
        object.__setattr__(self, "linear_coefficient", abs(h / c))
        object.__setattr__(self, "radical_coefficient_mm", coefficient)
        checkpoint()

    def variation(self, q_distance_mm: Fraction) -> Fraction:
        """
        Bound b distance for any two original arc points separated by at most the exact nonnegative q distance.

        Only the proof's distance argument is limited to the original q span;
        no returned material coordinate or source point is moved. The existing
        outward-rounded square root retains arithmetic uncertainty explicitly.
        """
        if type(q_distance_mm) is not Fraction or q_distance_mm < 0:
            raise ValueError("An exact nonnegative q distance required")
        distance = min(q_distance_mm, self.interval[1] - self.interval[0])
        return self.linear_coefficient * distance + square_root_upper(
            self.radical_coefficient_mm * distance
        )
