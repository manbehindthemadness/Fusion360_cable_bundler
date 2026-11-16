"""
Bind direct native boundary, global coordinates and original-domain distance into bidirectional surface coverage.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import InitVar, dataclass, field
from fractions import Fraction

from .boundary_traversal import BoundaryTransitionBounds, BoundaryTraversalPolicy, junctions_sq
from .material_polygon import MaterialPolygon
from .native_boundary_distance import BoundarySide, ProfileGraph
from .native_boundary_enclosure import FiniteNativeBoundarySide
from .native_cylinder_projection import ActualCylinderProjection
from .native_flat_domain import NativeFlatDomainAccuracy


@dataclass(frozen=True)
class NativeOuterLoop:
    """
    Own every coedge of one captured original native face's single outer boundary.

    The capture adapter establishes exactly one outer loop and its SDK coedge
    count. Native edge continuity and shared vertex identities are explicit BRep
    model premises. This object enforces completeness, owner identity, directed
    incidence and exact shared captured vertex positions, without curve fitting,
    exported UV bridges or geometric welding.
    """

    sides: tuple[FiniteNativeBoundarySide, ...]
    coedge_count: int
    checkpoint: InitVar[Callable[[], None]]

    def __post_init__(self, checkpoint: Callable[[], None]) -> None:
        """
        Reject missing coedges, foreign owners or a broken native boundary cycle before any winding inference.
        """
        checkpoint()
        if (
            not self.sides
            or type(self.coedge_count) is not int
            or self.coedge_count != len(self.sides)
        ):
            raise ValueError("The complete nonempty native outer loop required")
        first = self.sides[0]
        for side, following in zip(self.sides, self.sides[1:] + self.sides[:1]):
            checkpoint()
            if (
                side.frame is not first.frame
                or side.graph is not first.graph
                or side.box.native is not first.box.native
                or side.box.face_token != first.box.face_token
                or side.box.directed_vertices[1] != following.box.directed_vertices[0]
                or side.box.vertex_points_mm[1] != following.box.vertex_points_mm[0]
            ):
                raise ValueError(
                    "The SAME original native owners and closed directed vertex cycle required"
                )


@dataclass(frozen=True)
class NativeBoundaryCollar:
    """
    Account for the complete original source boundary under the explicit native traversal policy.
    """

    loop: NativeOuterLoop
    checkpoint: InitVar[Callable[[], None]]
    policy: BoundaryTraversalPolicy = BoundaryTraversalPolicy.COMPLETE
    polygon: MaterialPolygon = field(init=False)
    collar_upper_mm: Fraction = field(init=False)
    planar_reverse_upper_mm: Fraction = field(init=False)
    omitted_source_sides: tuple[BoundarySide, ...] = field(init=False)

    def __post_init__(self, checkpoint: Callable[[], None]) -> None:
        """
        Bound whole native sides and every original source transition path under the explicit traversal policy.
        """
        checkpoint()
        first = self.loop.sides[0]
        frame, graph = first.frame, first.graph
        polygon = MaterialPolygon(frame, graph)
        transitions = BoundaryTransitionBounds(
            polygon,
            tuple(side.side for side in self.loop.sides),
            junctions_sq(frame, tuple(side.box.vertex_points_mm[1] for side in self.loop.sides)),
            self.policy,
            checkpoint,
        )
        collar = max(transitions.corner_upper_mm, *(side.tube_upper_mm for side in self.loop.sides))
        object.__setattr__(self, "polygon", polygon)
        object.__setattr__(self, "collar_upper_mm", collar)
        object.__setattr__(self, "planar_reverse_upper_mm", polygon.reverse_bound(collar))
        object.__setattr__(self, "omitted_source_sides", transitions.traversal.omitted_sides)
        checkpoint()


@dataclass(frozen=True)
class NativeMaterialDomainCoverage:
    """
    Qualify bidirectional original material/world coverage of an actual native surface face.

    Whole native edge boxes place the complete original boundary in finite side
    collars, with every transition vertex bounded against its original corner.
    Each source side occurs once cyclically. The resulting sidewise homotopy
    preserves winding outside the collar. Global native (s,q) injectivity and
    the single native outer loop identify that filled region with the actual
    face image. The source convex-core bound supplies reverse planar distance.

    Existing domain evidence gives a source witness z within joint distance D
    of every native p. For source y with planar distance <=delta from p, source
    graph Lipschitz L gives |p-y| <=D+L*(delta+D). Both material and world L1
    share ONE dimensional allowance. The original labels and native geometry
    remain unchanged. This proves surface-domain coverage, not 3D isometry,
    conductor paths, volume, contact, junctions, endings or complete outputs.
    """

    loop: NativeOuterLoop
    projection: ActualCylinderProjection
    domain: NativeFlatDomainAccuracy
    checkpoint: InitVar[Callable[[], None]]
    polygon: MaterialPolygon = field(init=False)
    collar_upper_mm: Fraction = field(init=False)
    planar_reverse_upper_mm: Fraction = field(init=False)
    source_lipschitz: Fraction = field(init=False)
    forward_upper_mm: Fraction = field(init=False)
    reverse_upper_mm: Fraction = field(init=False)

    def __post_init__(self, checkpoint: Callable[[], None]) -> None:
        """
        Require the SAME actual face, original frame/profile and qualified projection/domain evidence.
        """
        checkpoint()
        first = self.loop.sides[0]
        frame, graph, native = first.frame, first.graph, first.box.native
        if not isinstance(graph, ProfileGraph):
            raise ValueError(
                "The original finite-slope profile graph required for this projection certificate"
            )
        if (
            self.projection.frame is not frame
            or self.projection.status != "certified_actual_native_sq_projection"
            or self.domain.profile.frame is not frame
            or self.domain.profile.conic is not graph.conic
            or self.domain.status != "within_native_original_flat_domain_accuracy"
            or self.domain.distance_upper_mm is None
            or any(
                box.native is not native or box.face_token != first.box.face_token
                for box in (
                    *self.projection.boxes,
                    *self.domain.profile.boxes,
                    self.domain.cuts.low_box,
                    self.domain.cuts.high_box,
                )
            )
        ):
            raise ValueError(
                "The SAME qualified actual native face, original frame/profile and domain required"
            )
        boundary = NativeBoundaryCollar(self.loop, checkpoint)
        delta = boundary.planar_reverse_upper_mm
        scales = tuple(sum(map(abs, column)) for column in frame.columns)
        lipschitz = max(1 + graph.slope_upper, scales[0], scales[1] + scales[2] * graph.slope_upper)
        forward = self.domain.distance_upper_mm
        reverse = forward + lipschitz * (delta + forward)
        object.__setattr__(self, "polygon", boundary.polygon)
        object.__setattr__(self, "collar_upper_mm", boundary.collar_upper_mm)
        object.__setattr__(self, "planar_reverse_upper_mm", delta)
        object.__setattr__(self, "source_lipschitz", lipschitz)
        object.__setattr__(self, "forward_upper_mm", forward)
        object.__setattr__(self, "reverse_upper_mm", reverse)
        checkpoint()

    @property
    def status(self) -> str:
        """
        Require a source core and one inclusive joint material/world accuracy in both filled directions.
        """
        return (
            "qualified_actual_native_material_domain"
            if 2 * self.collar_upper_mm < self.polygon.inradius_mm
            and max(self.forward_upper_mm, self.reverse_upper_mm) <= Fraction(1, 100)
            else "unresolved_actual_native_material_domain"
        )
