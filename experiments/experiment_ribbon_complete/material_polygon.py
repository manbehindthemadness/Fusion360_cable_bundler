"""
Share original convex material-domain geometry and ordered boundary-collar arithmetic across native and captured proofs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from .flat_cut_domain import FlatCutFrame
from .native_boundary_distance import BoundarySide
from .profile_continuity import OriginalProfileQDomain, ordered_profile_q

Pair = tuple[Fraction, Fraction]
ORDER = (BoundarySide.END0, BoundarySide.HIGH, BoundarySide.END1, BoundarySide.LOW)


@dataclass(frozen=True)
class MaterialPolygon:
    """
    Own the original physical (s,q) cut polygon without changing profile labels or finite endpoints.

    Constant-size exact geometry supplies the convex source core used by an
    ordered boundary homotopy. This object alone proves no native membership,
    boundary coverage, isometry or construction success.
    """

    frame: FlatCutFrame
    graph: OriginalProfileQDomain
    vertices: tuple[Pair, ...] = field(init=False)
    inradius_mm: Fraction = field(init=False)
    radius_mm: Fraction = field(init=False)

    def __post_init__(self) -> None:
        """
        Derive original vertices and a positive L1 interior radius, preserving zero-width tips.
        """
        frame, graph = self.frame, self.graph
        q0, q1 = ordered_profile_q(graph)
        vertices = (
            (frame.low.at(q0), q0),
            (frame.high.at(q0), q0),
            (frame.high.at(q1), q1),
            (frame.low.at(q1), q1),
        )
        low_q, high_q = graph.interval
        if low_q >= high_q or any(frame.low.at(q) > frame.high.at(q) for q in (q0, q1)):
            raise ValueError("A nonempty convex original cut polygon required")
        center_q = (low_q + high_q) / 2
        center = ((frame.low.at(center_q) + frame.high.at(center_q)) / 2, center_q)
        radius = max(sum(abs(a - b) for a, b in zip(p, center)) for p in vertices)
        inradius = min(
            center_q - low_q,
            high_q - center_q,
            (center[0] - frame.low.at(center_q)) / max(Fraction(1), abs(frame.low.slope)),
            (frame.high.at(center_q) - center[0]) / max(Fraction(1), abs(frame.high.slope)),
        )
        if inradius <= 0:
            raise ValueError("An original polygon with positive interior required")
        object.__setattr__(self, "vertices", vertices)
        object.__setattr__(self, "inradius_mm", inradius)
        object.__setattr__(self, "radius_mm", radius)

    def validate_sides(self, sides: tuple[BoundarySide, ...]) -> None:
        """
        Require each original side exactly once cyclically, allowing contiguous split coedges and either orientation.
        """
        groups = tuple(side for i, side in enumerate(sides) if side is not sides[i - 1])
        orders = [ORDER]
        for i, side in enumerate(ORDER):
            if self.vertices[i] == self.vertices[(i + 1) % 4]:
                orders += [tuple(value for value in order if value is not side) for order in orders]
        rotations = [order[i:] + order[:i] for order in orders for i in range(len(order))]
        if not any(groups == row or groups == tuple(reversed(row)) for row in rotations):
            raise ValueError("All four original sides exactly once cyclically required")

    def corner(self, first: BoundarySide, second: BoundarySide) -> Pair:
        """
        Return the original finite corner shared by two adjacent named sides.
        """
        if first not in ORDER or second not in ORDER or first is second:
            raise ValueError("Adjacent original boundary sides required")
        first_index, second_index = ORDER.index(first), ORDER.index(second)
        common = {self.vertices[first_index], self.vertices[(first_index + 1) % 4]} & {
            self.vertices[second_index],
            self.vertices[(second_index + 1) % 4],
        }
        if len(common) != 1:
            raise ValueError("Adjacent original boundary sides required")
        return next(iter(common))

    def reverse_bound(self, collar_mm: Fraction) -> Fraction:
        """
        Bound source-to-filled distance after an established ordered collar homotopy.
        """
        if type(collar_mm) is not Fraction or collar_mm < 0:
            raise ValueError("An exact nonnegative physical collar required")
        return 2 * self.radius_mm * collar_mm / self.inradius_mm
