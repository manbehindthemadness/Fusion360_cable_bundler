"""
Reject source cycle transitions that cannot satisfy the existing boundary collar and convex-core conditions.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import InitVar, dataclass
from fractions import Fraction

from .boundary_traversal import BoundaryTraversal
from .material_polygon import MaterialPolygon, Pair
from .native_boundary_distance import BoundarySide


@dataclass(frozen=True)
class BoundaryCycleJunctions:
    """
    Own actual captured source-plane junctions for necessary cycle feasibility checks.

    Transition errors are lower bounds on the eventual whole-boundary collar.
    A transition unable to satisfy2*error<source inradius or error<=0.01 cannot
    yield the existing filled-domain certificate. Rejecting it before counting
    is a feasibility test, not ranking. This object alone proves no whole-edge,
    filled-domain, inverse-map or physical acceptance.
    """

    polygon: MaterialPolygon
    points: tuple[Pair, ...]
    checkpoint: InitVar[Callable[[], None]]

    def __post_init__(self, checkpoint: Callable[[], None]) -> None:
        """
        Require exact nonempty captured junctions without changing source geometry or coordinates.
        """
        checkpoint()
        if not self.points or any(
            len(point) != 2 or any(type(x) is not Fraction for x in point) for point in self.points
        ):
            raise ValueError("Nonempty exact source-plane junction positions required")

    def allows(
        self,
        traversal: BoundaryTraversal,
        first: BoundarySide,
        following: BoundarySide,
        junction_index: int,
        checkpoint: Callable[[], None],
    ) -> bool:
        """
        Check every source corner on a transition against its actual junction under the shared caller allocation.
        """
        checkpoint()
        if traversal.polygon is not self.polygon or not 0 <= junction_index < len(self.points):
            raise ValueError("The SAME source polygon and a captured junction index required")
        if first is following:
            return True
        error = max(
            sum(abs(a - b) for a, b in zip(self.points[junction_index], corner))
            for corner in traversal.corners(first, following)
        )
        return 2 * error < self.polygon.inradius_mm and error <= Fraction(1, 100)
