"""
Bound a captured loop's projected winding region through ordered convex boundary collars.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import InitVar, dataclass, field
from fractions import Fraction

from .material_polygon import MaterialPolygon
from .native_boundary_distance import FiniteBoundaryTrace


@dataclass(frozen=True)
class DirectedBoundaryTrace:
    """
    Retain captured topological direction independently of the curve parameter direction.

    The capture adapter supplies vertex identities and reversal from the SDK.
    They establish provenance, not a numerical endpoint coincidence assumption.
    """

    finite: FiniteBoundaryTrace
    start_vertex: int
    end_vertex: int
    reversed: bool

    def endpoints(self) -> tuple[tuple[Fraction, ...], tuple[Fraction, ...]]:
        """
        Decode both complete physical-label endpoints in declared topological order.
        """
        trace, frame = self.finite.trace, self.finite.frame
        inverse = frame.inverse.rows
        assert inverse is not None
        values = tuple(
            trace.affine_numerator(
                row, -sum((a * b for a, b in zip(row, frame.origin)), Fraction(0))
            )
            for row in inverse
        )
        indices = (-1, 0) if self.reversed else (0, -1)
        endpoints = [tuple(n[i] / trace.denominator[i] for n in values) for i in indices]
        return endpoints[0], endpoints[1]


@dataclass(frozen=True)
class ProjectedFilledDomain:
    """
    Certify coverage of a captured loop's nonzero-winding region in original physical (s,q).

    Every whole trace lies in a convex epsilon tube of its assigned finite source
    segment. Sides must occur exactly once cyclically, allowing split coedges.
    At side transitions both decoded endpoints are bounded against the SAME
    original corner. Explicit straight endpoint bridges close the comparison
    loop; their total physical-label L1 length is charged once to the collar.
    This neither welds geometry nor assumes native/model endpoint uncertainty.

    A sidewise homotopy to the source polygon stays in that collar. Winding
    therefore agrees outside it, even if the comparison loop is not simple.
    The source is convex with L1 inradius r at c and vertex radius R. Moving any
    source point toward c by 2*epsilon/r gives a point deeper than the collar,
    proving reverse filled distance <=2*R*epsilon/r. Forward distance <=epsilon.
    The closed filled sets are closures of their nonzero-winding regions.

    No native-original correspondence, b-coordinate lifting, isometry or complete
    material-chart acceptance follows from this projected capture certificate.
    """

    boundary: tuple[DirectedBoundaryTrace, ...]
    checkpoint: InitVar[Callable[[], None]]
    collar_upper_mm: Fraction = field(init=False)
    closure_gaps_mm: tuple[Fraction, ...] = field(init=False)
    source_inradius_mm: Fraction = field(init=False)
    source_radius_mm: Fraction = field(init=False)
    forward_upper_mm: Fraction = field(init=False)
    reverse_upper_mm: Fraction = field(init=False)

    def __post_init__(self, checkpoint: Callable[[], None]) -> None:
        """
        Derive the ordered homotopy collar and filled bounds from immutable owned traces.
        """
        checkpoint()
        if not self.boundary:
            raise ValueError("A nonempty directed boundary required")
        first = self.boundary[0].finite
        frame, graph = first.frame, first.graph
        for current, following in zip(self.boundary, self.boundary[1:] + self.boundary[:1]):
            checkpoint()
            finite = current.finite
            if (
                finite.frame is not frame
                or finite.graph is not graph
                or finite.trace.surface is not first.trace.surface
                or type(current.reversed) is not bool
                or type(current.start_vertex) is not int
                or type(current.end_vertex) is not int
                or current.end_vertex != following.start_vertex
            ):
                raise ValueError("The SAME owners and a closed directed vertex cycle required")
        polygon = MaterialPolygon(frame, graph)
        polygon.validate_sides(tuple(row.finite.side for row in self.boundary))
        endpoints = [row.endpoints() for row in self.boundary]
        collar = max(row.finite.forward_upper_mm for row in self.boundary)
        gaps = []
        for i, current in enumerate(self.boundary):
            checkpoint()
            following = self.boundary[(i + 1) % len(self.boundary)]
            end, start = endpoints[i][1], endpoints[(i + 1) % len(self.boundary)][0]
            gaps.append(sum(abs(a - b) for a, b in zip(end, start)))
            if current.finite.side is not following.finite.side:
                corner = polygon.corner(current.finite.side, following.finite.side)
                collar = max(
                    collar,
                    *(sum(abs(a - b) for a, b in zip(p[:2], corner)) for p in (end, start)),
                )
        collar += sum(gaps)
        object.__setattr__(self, "collar_upper_mm", collar)
        object.__setattr__(self, "closure_gaps_mm", tuple(gaps))
        object.__setattr__(self, "source_inradius_mm", polygon.inradius_mm)
        object.__setattr__(self, "source_radius_mm", polygon.radius_mm)
        object.__setattr__(self, "forward_upper_mm", collar)
        object.__setattr__(self, "reverse_upper_mm", polygon.reverse_bound(collar))
        checkpoint()

    @property
    def status(self) -> str:
        """
        Require a nonempty collar-free core and one inclusive projected dimensional allowance.
        """
        return (
            "within_projected_capture_filled_accuracy"
            if 2 * self.collar_upper_mm < self.source_inradius_mm
            and max(self.forward_upper_mm, self.reverse_upper_mm) <= Fraction(1, 100)
            else "unresolved_projected_capture_filled_accuracy"
        )
