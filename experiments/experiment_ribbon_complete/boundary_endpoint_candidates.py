"""
Derive finite source-side query candidates from independent native endpoint positions without whole-edge acceptance.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import InitVar, dataclass, field
from fractions import Fraction

from .exact_frame import Point
from .flat_cut_domain import FlatCutFrame
from .native_boundary_distance import BoundarySide
from .profile_continuity import OriginalProfileQDomain, ordered_profile_q


@dataclass(frozen=True)
class BoundaryEndpointCandidates:
    """
    Measure both world endpoints against every finite source side in original physical (s,q).

    The adapter establishes original native vertex/source ownership first.
    A unique candidate may orient a later whole-edge enclosure query; endpoints
    never establish whole-curve or filled coverage. Multiple acceptable sides
    remain unresolved even when one has a smaller error. No native identity,
    source coordinate, target or geometric point is moved or relabeled.
    """

    frame: FlatCutFrame
    graph: OriginalProfileQDomain
    points_mm: tuple[Point, Point]
    checkpoint: InitVar[Callable[[], None]]
    errors_mm: tuple[Fraction, ...] = field(init=False)
    eligible: tuple[BoundarySide, ...] = field(init=False)

    def __post_init__(self, checkpoint: Callable[[], None]) -> None:
        """
        Derive every finite endpoint error from the SAME original frame/profile without trusting a cached side label.
        """
        checkpoint()
        if len(self.points_mm) != 2 or any(
            len(p) != 3 or any(type(x) is not Fraction for x in p) for p in self.points_mm
        ):
            raise ValueError("Two exact component-local native endpoint positions required")
        inverse = self.frame.inverse.rows
        assert inverse is not None
        labels = tuple(
            tuple(
                sum((a * (p - o) for a, p, o in zip(row, point, self.frame.origin)), Fraction(0))
                for row in inverse[:2]
            )
            for point in self.points_mm
        )
        errors = []
        for side in BoundarySide:
            checkpoint()
            values = []
            for s, q in labels:
                if side in (BoundarySide.LOW, BoundarySide.HIGH):
                    cut = self.frame.low if side is BoundarySide.LOW else self.frame.high
                    low, high = self.graph.interval
                    overhang = max(Fraction(0), low - q, q - high)
                    error = abs(s - cut.at(q)) + (1 + abs(cut.slope)) * overhang
                else:
                    source_q = ordered_profile_q(self.graph)[0 if side is BoundarySide.END0 else -1]
                    low, high = self.frame.low.at(source_q), self.frame.high.at(source_q)
                    if low > high:
                        raise ValueError("A nonempty original finite source side required")
                    error = abs(q - source_q) + max(Fraction(0), low - s, s - high)
                values.append(error)
            errors.append(max(values))
        object.__setattr__(self, "errors_mm", tuple(errors))
        object.__setattr__(
            self,
            "eligible",
            tuple(side for side, error in zip(BoundarySide, errors) if error <= Fraction(1, 100)),
        )
        checkpoint()

    @property
    def unique_side(self) -> BoundarySide | None:
        """
        Return a request side only for a unique fit; ambiguity and no match remain explicit.
        """
        return self.eligible[0] if len(self.eligible) == 1 else None
