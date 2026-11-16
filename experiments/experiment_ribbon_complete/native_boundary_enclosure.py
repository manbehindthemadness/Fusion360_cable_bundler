"""
Bound whole original native edges against finite source sides without curve conversion or nondegenerate-box assumptions.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import InitVar, dataclass, field
from fractions import Fraction
from itertools import product

from .exact_frame import Point
from .flat_cut_domain import FlatCutFrame
from .native_boundary_distance import BoundarySide
from .native_flat_cylinder import NativeCylinderSnapshot
from .profile_continuity import OriginalProfileQDomain, ordered_profile_q


def boundary_axes(frame: FlatCutFrame, side: BoundarySide) -> tuple[Point, Point]:
    """
    Orient an edge enclosure by original side normal and progress without assigning material units to native parameters.
    """
    rows = frame.inverse.rows
    assert rows is not None
    if side in (BoundarySide.LOW, BoundarySide.HIGH):
        cut = frame.low if side is BoundarySide.LOW else frame.high
        normal = tuple(s - cut.slope * q for s, q in zip(rows[0], rows[1]))
        progress = rows[1]
    elif side in (BoundarySide.END0, BoundarySide.END1):
        normal, progress = rows[1], rows[0]
    else:
        raise ValueError("An original finite boundary side required")
    squared = sum(x * x for x in normal)
    along = sum(a * b for a, b in zip(normal, progress)) / squared
    width = tuple(p - along * n for p, n in zip(progress, normal))
    return normal, width


@dataclass(frozen=True)
class NativeEdgeBox:
    """
    Own a whole actual native edge enclosure, including its directed topological endpoints.

    The SDK capture establishes original face/edge incidence, one outer loop and
    unchanged revision. Zero box half axes are valid for lines and points; they
    must not be inflated to satisfy a volume-box requirement. Coordinates use
    component-local millimetres. SDK whole-entity enclosure is a trusted premise.
    """

    native: NativeCylinderSnapshot
    face_token: str
    edge_id: int
    directed_vertices: tuple[int, int]
    vertex_points_mm: tuple[Point, Point]
    center_mm: Point
    half_axes_mm: tuple[Point, ...]

    def __post_init__(self) -> None:
        """
        Reject malformed physical coordinates and discrete identities while allowing degenerate enclosures.
        """
        if (
            not isinstance(self.face_token, str)
            or not self.face_token
            or type(self.edge_id) is not int
            or self.edge_id < 0
            or len(self.directed_vertices) != 2
            or any(type(x) is not int or x < 0 for x in self.directed_vertices)
            or len(self.vertex_points_mm) != 2
            or len(self.half_axes_mm) != 3
            or any(
                len(p) != 3 or any(type(x) is not Fraction for x in p)
                for p in (self.center_mm, *self.vertex_points_mm, *self.half_axes_mm)
            )
        ):
            raise ValueError(
                "Complete owned native edge coordinates and directed identities required"
            )

    def corners(self) -> tuple[Point, ...]:
        """
        Enclose the complete edge by all parallelepiped vertices even when some vertices coincide.
        """
        return tuple(
            tuple(
                self.center_mm[k]
                + sum(sign * axis[k] for sign, axis in zip(signs, self.half_axes_mm))
                for k in range(3)
            )
            for signs in product((-1, 1), repeat=3)
        )


@dataclass(frozen=True)
class FiniteNativeBoundarySide:
    """
    Bound every actual native edge point to one finite original source segment in physical (s,q).

    Affine extrema over the whole SDK box bound cut-plane residual and progress
    overhang. The nearest source progress is a proof witness, not an altered
    output coordinate. No endpoint-only curve inference or 3D conversion occurs.
    This is a boundary-side tube, not filled coverage or a material/path audit.
    """

    box: NativeEdgeBox
    frame: FlatCutFrame
    graph: OriginalProfileQDomain
    side: BoundarySide
    checkpoint: InitVar[Callable[[], None]]
    s_interval_mm: tuple[Fraction, Fraction] = field(init=False)
    q_interval_mm: tuple[Fraction, Fraction] = field(init=False)
    tube_upper_mm: Fraction = field(init=False)

    def __post_init__(self, checkpoint: Callable[[], None]) -> None:
        """
        Require original native/profile ownership and derive all finite-side bounds over the complete enclosure.
        """
        checkpoint()
        if (
            self.frame.region.value != self.box.native.region
            or self.graph.conic.arc.label != self.box.native.profile_label
            or not isinstance(self.side, BoundarySide)
        ):
            raise ValueError("The SAME original native region/profile and finite side required")
        rows = self.frame.inverse.rows
        assert rows is not None
        labels = tuple(
            tuple(
                sum((a * (p - o) for a, p, o in zip(row, point, self.frame.origin)), Fraction(0))
                for row in rows[:2]
            )
            for point in self.box.corners()
        )
        s_interval = min(p[0] for p in labels), max(p[0] for p in labels)
        q_interval = min(p[1] for p in labels), max(p[1] for p in labels)
        if self.side in (BoundarySide.LOW, BoundarySide.HIGH):
            cut = self.frame.low if self.side is BoundarySide.LOW else self.frame.high
            residual = max(abs(s - cut.at(q)) for s, q in labels)
            low, high = self.graph.interval
            overhang = max(Fraction(0), low - q_interval[0], q_interval[1] - high)
            error = residual + (1 + abs(cut.slope)) * overhang
        else:
            q = ordered_profile_q(self.graph)[0 if self.side is BoundarySide.END0 else -1]
            low, high = self.frame.low.at(q), self.frame.high.at(q)
            if low > high:
                raise ValueError("A nonempty original finite generator required")
            residual = max(abs(value - q) for value in q_interval)
            overhang = max(Fraction(0), low - s_interval[0], s_interval[1] - high)
            error = residual + overhang
        object.__setattr__(self, "s_interval_mm", s_interval)
        object.__setattr__(self, "q_interval_mm", q_interval)
        object.__setattr__(self, "tube_upper_mm", error)
        checkpoint()

    @property
    def status(self) -> str:
        """
        Apply one inclusive finite-boundary projected distance allowance.
        """
        return (
            "within_actual_native_finite_side"
            if self.tube_upper_mm <= Fraction(1, 100)
            else "unresolved_actual_native_finite_side"
        )
