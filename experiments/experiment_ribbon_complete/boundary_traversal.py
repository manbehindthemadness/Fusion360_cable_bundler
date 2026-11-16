"""
Account for every original source boundary side, including finite sides covered by one actual native junction.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import InitVar, dataclass, field
from enum import Enum
from fractions import Fraction

from .exact_frame import Point
from .flat_cut_domain import FlatCutFrame
from .material_polygon import ORDER, MaterialPolygon, Pair
from .native_boundary_distance import BoundarySide


class BoundaryTraversalPolicy(Enum):
    """
    Keep complete source-side representation distinct from explicitly measured finite-side bridges.
    """

    COMPLETE = "complete"
    FINITE_BRIDGES = "finite_bridges"


def junctions_sq(frame: FlatCutFrame, points: tuple[Point, ...]) -> tuple[Pair, ...]:
    """
    Decode exact captured junction positions through the original affine frame without moving any returned coordinate.
    """
    rows = frame.inverse.rows
    assert rows is not None
    if any(len(point) != 3 or any(type(x) is not Fraction for x in point) for point in points):
        raise ValueError("Exact original world junction positions required")
    result = []
    for point in points:
        values = tuple(
            sum((a * (p - o) for a, p, o in zip(row, point, frame.origin)), Fraction(0))
            for row in rows[:2]
        )
        result.append((values[0], values[1]))
    return tuple(result)


@dataclass(frozen=True)
class BoundaryTraversal:
    """
    Retain a single cyclic source traversal without deleting missing finite source geometry.

    The bridge policy permits three or four distinct source-side groups. Every
    unrepresented side remains in the original polygon; its complete vertex
    path must subsequently be covered by an actual native junction bound.
    This structural object alone grants no geometric or native acceptance.
    """

    polygon: MaterialPolygon
    sides: tuple[BoundarySide, ...]
    policy: BoundaryTraversalPolicy
    checkpoint: InitVar[Callable[[], None]]
    direction: int = field(init=False)
    omitted_sides: tuple[BoundarySide, ...] = field(init=False)

    def __post_init__(self, checkpoint: Callable[[], None]) -> None:
        """
        Reject repeated, unordered or unsupported source-side groups before constructing finite transition paths.
        """
        checkpoint()
        if not isinstance(self.policy, BoundaryTraversalPolicy):
            raise ValueError("An explicit source boundary traversal policy required")
        if self.policy is BoundaryTraversalPolicy.COMPLETE:
            self.polygon.validate_sides(self.sides)
        groups = tuple(side for i, side in enumerate(self.sides) if side is not self.sides[i - 1])
        if (
            len(groups) not in (3, 4)
            or len(set(groups)) != len(groups)
            or any(side not in ORDER for side in groups)
        ):
            raise ValueError("Three or four original sides exactly once cyclically required")
        retained = tuple(side for side in ORDER if side in groups)
        directions = []
        for direction in (1, -1):
            ordered = retained if direction == 1 else tuple(reversed(retained))
            if any(groups == ordered[i:] + ordered[:i] for i in range(len(ordered))):
                directions.append(direction)
        if len(directions) != 1:
            raise ValueError("A unique original cyclic side orientation required")
        object.__setattr__(self, "direction", directions[0])
        object.__setattr__(
            self, "omitted_sides", tuple(side for side in ORDER if side not in groups)
        )
        checkpoint()

    def corners(self, first: BoundarySide, following: BoundarySide) -> tuple[Pair, ...]:
        """
        Retain all original corner vertices across the source path between two represented sides.
        """
        if first is following or first not in self.sides or following not in self.sides:
            raise ValueError("Distinct represented source sides required")
        start, end = ORDER.index(first), ORDER.index(following)
        index = (start + 1) % 4 if self.direction == 1 else start
        target = end if self.direction == 1 else (end + 1) % 4
        vertices = [self.polygon.vertices[index]]
        while index != target:
            index = (index + self.direction) % 4
            vertices.append(self.polygon.vertices[index])
        return tuple(vertices)


@dataclass(frozen=True)
class BoundaryTransitionBounds:
    """
    Enclose every source transition path using its actual shared native junction.

    The L1 norm is convex, so the maximum distance to all retained source path
    vertices covers every point of every omitted straight source segment.
    Native coedges and IDs are not invented. The caller separately establishes
    actual junction ownership and the complete native loop. These bounds still
    require the common collar/core and material/world lift before coverage.
    """

    polygon: MaterialPolygon
    sides: tuple[BoundarySide, ...]
    junctions: tuple[Pair, ...]
    policy: BoundaryTraversalPolicy
    checkpoint: InitVar[Callable[[], None]]
    traversal: BoundaryTraversal = field(init=False)
    corner_upper_mm: Fraction = field(init=False)

    def __post_init__(self, checkpoint: Callable[[], None]) -> None:
        """
        Require exact complete junction data and account for every original corner across every source-side transition.
        """
        checkpoint()
        if len(self.junctions) != len(self.sides) or any(
            len(point) != 2 or any(type(x) is not Fraction for x in point)
            for point in self.junctions
        ):
            raise ValueError("Complete exact source-plane junctions required")
        traversal = BoundaryTraversal(self.polygon, self.sides, self.policy, checkpoint)
        bound = Fraction(0)
        for index, (side, following) in enumerate(zip(self.sides, self.sides[1:] + self.sides[:1])):
            checkpoint()
            if side is not following:
                for corner in traversal.corners(side, following):
                    bound = max(
                        bound, sum(abs(a - b) for a, b in zip(self.junctions[index], corner))
                    )
        object.__setattr__(self, "traversal", traversal)
        object.__setattr__(self, "corner_upper_mm", bound)
        checkpoint()
