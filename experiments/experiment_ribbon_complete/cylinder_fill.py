"""
Extend complete native boundary coordinate bounds through compact regular cylinder faces by axial exit.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from .cylinder_coordinates import CylinderChart
from .cylinder_domain import CylinderWindowBound, certify_window, ratio_hull
from .exact_frame import Point
from .native_flat_cylinder import NativeCylinderSnapshot


@dataclass(frozen=True)
class NativeEdgeUse:
    """
    Retain an actual oriented coedge's edge and endpoint identities without coordinate welding.
    """

    edge_id: int
    start_vertex: int
    end_vertex: int

    def __post_init__(self) -> None:
        """
        Require discrete native identities rather than coincident or coerced values.
        """
        if any(
            type(x) is not int or x < 0 for x in (self.edge_id, self.start_vertex, self.end_vertex)
        ):
            raise ValueError("Discrete nonnegative native edge/vertex identities required")


@dataclass(frozen=True)
class CompactCylinderFace:
    """
    Retain an actual BRepFace finite enclosure and complete boundary under the native API contract.

    The capturing adapter obtains the box from BRepFace.boundingBox, the area
    from that SAME face, and every loop and face edge from its owning BRepFace.
    These are model-level geometric contracts, not inferred from point samples.
    A regular cylinder support and finite enclosing box make the face closure
    compact; edges/loops give its complete relative boundary, including holes.
    """

    native: NativeCylinderSnapshot
    face_token: str
    bounding_box_mm: tuple[Point, Point]
    area_mm2: Fraction
    edge_ids: tuple[int, ...]
    loops: tuple[tuple[NativeEdgeUse, ...], ...]

    def __post_init__(self) -> None:
        """
        Require finite exact native bounds, nonempty area and complete closed discrete boundary coverage.
        """
        if (
            not self.face_token
            or len(self.bounding_box_mm) != 2
            or any(
                len(p) != 3 or any(type(x) is not Fraction for x in p) for p in self.bounding_box_mm
            )
            or any(a > b for a, b in zip(*self.bounding_box_mm))
            or type(self.area_mm2) is not Fraction
            or self.area_mm2 <= 0
        ):
            raise ValueError("An actual finite nonempty native cylinder face enclosure required")
        if (
            not self.edge_ids
            or len(set(self.edge_ids)) != len(self.edge_ids)
            or any(type(x) is not int or x < 0 for x in self.edge_ids)
            or not self.loops
            or any(not loop for loop in self.loops)
        ):
            raise ValueError("Complete actual face edge/loop identities required")
        if {edge.edge_id for loop in self.loops for edge in loop} != set(self.edge_ids):
            raise ValueError("Every actual face edge must occur in the complete native loops")
        if any(
            a.end_vertex != b.start_vertex
            for loop in self.loops
            for a, b in zip(loop, loop[1:] + loop[:1])
        ):
            raise ValueError(
                "Closed native vertex identities required; positions cannot weld a loop"
            )


@dataclass(frozen=True)
class BoundaryImage:
    """
    Own the entire actual edge image as positive-basis world controls under documented SDK geometry semantics.

    Line3D.getData supplies its complete segment. Arc3D.asNurbsCurve and
    EllipticalArc3D.asNurbsCurve are documented as geometrically identical to
    the analytic arc. The adapter verifies native face/edge/revision, full
    clamped-span provenance and source kind. No parameter identity follows.
    """

    native: NativeCylinderSnapshot
    edge_id: int
    controls: tuple[Point, ...]
    weights: tuple[Fraction, ...]
    source_kind: str

    def __post_init__(self) -> None:
        """
        Require a supported complete positive image, never an arbitrary sampled polyline.
        """
        count = (
            2
            if self.source_kind == "line3d"
            else 3
            if self.source_kind in ("arc3d_identical_nurbs", "ellipticalarc3d_identical_nurbs")
            else 0
        )
        if (
            type(self.edge_id) is not int
            or self.edge_id < 0
            or not count
            or len(self.controls) != count
            or len(self.weights) != count
            or any(len(p) != 3 or any(type(x) is not Fraction for x in p) for p in self.controls)
            or any(type(w) is not Fraction or w <= 0 for w in self.weights)
        ):
            raise ValueError(
                "A complete supported SDK-identical positive native edge image required"
            )
        if count == 2 and self.weights != (Fraction(1), Fraction(1)):
            raise ValueError("Original linear segment coordinates required")


@dataclass(frozen=True)
class FilledFaceEvidence:
    """
    Own one actual face, complete boundary images and derived filled-coordinate bounds.
    """

    face: CompactCylinderFace
    chart: CylinderChart
    boundary: tuple[BoundaryImage, ...]
    radial_lower_mm: Fraction | None
    maximum_abs_ratio: Fraction | None
    window: CylinderWindowBound | None
    status: str


@dataclass(frozen=True)
class FilledCylinderFace:
    """
    Retain intrinsic coordinate coverage of a native face, not original material-map or whole-ribbon acceptance.
    """

    face: CompactCylinderFace
    chart: CylinderChart
    boundary: tuple[BoundaryImage, ...]
    evidence: FilledFaceEvidence

    def __post_init__(self) -> None:
        """
        Refuse transferring a prior filled-domain result to a replacement face, chart or boundary.
        """
        if (
            self.evidence.face is not self.face
            or self.evidence.chart is not self.chart
            or self.evidence.boundary is not self.boundary
        ):
            raise ValueError("The SAME actual compact face/chart/boundary evidence required")

    @property
    def status(self) -> str:
        """
        Expose the owned complete-domain result without creating a material acceptance flag.
        """
        return self.evidence.status


def certify(
    face: CompactCylinderFace,
    chart: CylinderChart,
    boundary: tuple[BoundaryImage, ...],
    checkpoint: Callable[[], None],
) -> FilledCylinderFace:
    """
    Extend whole-boundary radial/angular bounds through the entire actual compact cylinder face.

    For p in the face closure, intersect its axial generator p+a*s with that
    closure. The intersection is nonempty, closed and bounded by the native
    finite box. Its maximal s is a relative boundary point: an interior point
    has a surface-open neighborhood and would permit continuing the generator.
    Radial x and tangent y coefficients annihilate the cylinder axis exactly,
    hence equal their boundary values at p. Thus positive x and |y/x|<=T on
    EVERY boundary image hold for EVERY face point. No simple-loop, rectangular
    trim, cap ordering, positive lead extent or sampled-interior inference is used.

    This relies on the actual BRepFace geometry/box/complete-boundary API contracts
    retained by the adapter. It proves coverage/injectivity/conditioning of the
    intrinsic chart only, not equality to a planned material image, membership
    of arbitrary query points, material increments, contact or junction flow.
    """
    checkpoint()
    if chart.reference.native is not face.native or any(
        edge.native is not face.native for edge in boundary
    ):
        raise ValueError("The SAME native compact cylinder face and boundary required")
    radial = None
    angular = None
    window = None
    status = "unresolved_complete_native_boundary"
    if (
        chart.status == "qualified_intrinsic_cylinder_basis"
        and len({e.edge_id for e in boundary}) == len(boundary)
        and {e.edge_id for e in boundary} == set(face.edge_ids)
    ):
        rows = chart.evidence.frame.rows
        assert rows is not None
        assert all(
            sum((a * b for a, b in zip(row, face.native.axis)), Fraction(0)) == 0
            for row in rows[1:]
        )
        lows = []
        angles = []
        status = "unresolved_native_boundary_branch"
        for edge in boundary:
            checkpoint()
            try:
                lower, interval = ratio_hull(chart, edge.controls)
            except ValueError:
                break
            lows.append(lower)
            angles.extend(map(abs, interval))
        if len(lows) == len(boundary):
            radial = min(lows)
            angular = max(angles)
            window = certify_window(chart, angular, checkpoint)
            status = (
                "certified_filled_intrinsic_cylinder_face"
                if window.status == "certified_intrinsic_cylinder_window"
                else "unresolved_filled_intrinsic_conditioning"
            )
    checkpoint()
    evidence = FilledFaceEvidence(face, chart, boundary, radial, angular, window, status)
    return FilledCylinderFace(face, chart, boundary, evidence)
