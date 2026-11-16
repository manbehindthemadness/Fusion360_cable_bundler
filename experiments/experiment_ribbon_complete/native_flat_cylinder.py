"""
Bound flat material fields against native cylinder supports without guessing native UV labels.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from artifacts.verification.resume3204.polynomial import multiply
from artifacts.verification.resume3217.metric import Polynomial
from experiments.experiment_ribbon_fold_route.material_profile import MaterialArc

from .exact_frame import Point
from .flat_chart import FlatChart, certify
from .flat_correspondence import controls
from .material_paths import combine
from .ruled_support import dot, square_root_upper


@dataclass(frozen=True)
class NativeCylinderSnapshot:
    """
    Retain the observed component-local cylinder in millimeters and its original face ownership.
    """

    revision: str
    face_index: int
    piece_index: int
    region: str
    profile_label: str
    origin: Point
    axis: Point
    radius_mm: Fraction

    def __post_init__(self) -> None:
        """
        Refuse incomplete identities, nonexact geometry, zero axes and nonpositive radii.
        """
        if (
            any(
                not isinstance(x, str) or not x.strip() for x in (self.revision, self.profile_label)
            )
            or any(type(x) is not int or x < 0 for x in (self.face_index, self.piece_index))
            or self.region not in ("straight", "before", "after")
            or any(
                len(p) != 3 or any(type(x) is not Fraction for x in p)
                for p in (self.origin, self.axis)
            )
            or not any(self.axis)
            or type(self.radius_mm) is not Fraction
            or self.radius_mm <= 0
        ):
            raise ValueError(
                "Complete exact native cylinder geometry and original face identity required"
            )

    def radial(self, vector: Point) -> Point:
        """
        Project a displacement perpendicular to the raw axis without assuming it is unit length.
        """
        squared = sum((x * x for x in self.axis), Fraction(0))
        along = sum((a * b for a, b in zip(vector, self.axis)), Fraction(0)) / squared
        return tuple(x - along * a for x, a in zip(vector, self.axis))


@dataclass(frozen=True)
class FlatCylinderEvidence:
    """
    Own the original source and measured construction bounds used by a support receipt.
    """

    chart: FlatChart
    arc: MaterialArc
    native: NativeCylinderSnapshot
    radial_squared_lower_mm2: Fraction
    position_upper_mm: Fraction | None
    increment_upper_mm: Fraction | None


@dataclass(frozen=True)
class FlatCylinderBound:
    """
    Retain radial-projection construction fidelity, with native trim and inverse validity unresolved.

    The unique radial projection exists only when the whole source rectangle
    stays away from the cylinder axis. Its position and longitudinal increments
    are compared to the SAME original material field; no native UV correspondence,
    trimmed-face coverage, isometry, contact or complete-path acceptance follows.
    """

    chart: FlatChart
    arc: MaterialArc
    native: NativeCylinderSnapshot
    radial_squared_lower_mm2: Fraction
    position_upper_mm: Fraction | None
    increment_upper_mm: Fraction | None
    status: str
    evidence: FlatCylinderEvidence | None = None

    def __post_init__(self) -> None:
        """
        Refuse stale source replacement and qualification without owned construction evidence.
        """
        owned = self.evidence
        if owned is not None and (
            owned.chart is not self.chart
            or owned.arc is not self.arc
            or owned.native is not self.native
            or owned.radial_squared_lower_mm2 != self.radial_squared_lower_mm2
            or owned.position_upper_mm != self.position_upper_mm
            or owned.increment_upper_mm != self.increment_upper_mm
        ):
            raise ValueError("Construction evidence must own the SAME chart/profile/native bounds")
        if self.status == "within_support_construction_accuracy" and (
            owned is None
            or self.radial_squared_lower_mm2 <= 0
            or self.position_upper_mm is None
            or self.position_upper_mm > Fraction(1, 100)
            or self.increment_upper_mm is None
            or self.increment_upper_mm > Fraction(1, 100)
        ):
            raise ValueError("Owned positive support and construction accuracy evidence required")


@dataclass(frozen=True)
class CylinderRadialField:
    """
    Retain exact radial and implicit-cylinder coefficients under the same observed support.
    """

    native: NativeCylinderSnapshot
    denominator: Polynomial
    squared: Polynomial
    residual: Polynomial


def radial_field(
    native: NativeCylinderSnapshot,
    rows: tuple[tuple[Point, ...], ...],
    weights: tuple[Fraction, ...],
    checkpoint: Callable[[], None],
) -> CylinderRadialField:
    """
    Compose the complete linear/rational rectangle with the raw-axis radial projector exactly.

    Callers own the rectangle's source/domain provenance. This shared algebra
    grants neither construction acceptance nor a coordinate-validity receipt.
    """
    checkpoint()
    if (
        len(rows) != 2
        or any(len(row) != 3 for row in rows)
        or len(weights) != 3
        or any(type(w) is not Fraction or w <= 0 for w in weights)
        or any(len(p) != 3 or any(type(x) is not Fraction for x in p) for row in rows for p in row)
    ):
        raise ValueError(
            "Complete exact linear/rational rows and positive quadratic weights required"
        )
    denominator = (multiply(weights, weights),)
    projected = tuple(
        tuple(native.radial(tuple(x - o for x, o in zip(p, native.origin))) for p in row)
        for row in rows
    )
    axes = tuple(
        tuple(tuple(p[k] * w for p, w in zip(row, weights)) for row in projected) for k in range(3)
    )
    vector = axes[0], axes[1], axes[2]
    squared = dot(vector, vector)
    residual = combine(squared, denominator, -(native.radius_mm**2))
    checkpoint()
    return CylinderRadialField(native, denominator, squared, residual)


def enclose(
    chart: FlatChart,
    arc: MaterialArc,
    native: NativeCylinderSnapshot,
    piece_index: int,
    revision: str,
    checkpoint: Callable[[], None],
) -> FlatCylinderBound:
    """
    Bound radial projection on the complete original linear-U/rational-V material rectangle.

    For radial vector r=P(F-origin), its squared length has a degree2U/4V
    Bernstein numerator over positive W². Thus |r²-R²|/R bounds distance to
    the infinite support cylinder. If r² has a positive lower bound, radial
    projection has derivative norm at most R/r_min. Its difference from the
    identity on radial derivatives is bounded by 1+R/r_min. Multiplying by
    ||P*C_s|| and the maximum original longitudinal extent bounds the integral
    of absolute speed discrepancy on every fixed-V longitudinal subinterval.

    No cancellation, subdivision, fitting, unit-axis assumption or per-station
    allowance is used. Missing positive radial bounds remain unresolved.
    """
    checkpoint()
    if (
        native.piece_index != piece_index
        or native.revision != revision
        or native.region != chart.region.value
        or native.profile_label != arc.label
        or certify(chart).status != "certified_affine_material_chart"
    ):
        raise ValueError("The SAME original qualified flat region/profile/native revision required")
    rows = (controls(chart, chart.low, arc), controls(chart, chart.high, arc))
    weights = tuple(Fraction(w) for w in arc.weights)
    field = radial_field(native, rows, weights, checkpoint)
    denominator, squared, residual = field.denominator, field.squared, field.residual
    lower = min(x / w for row in squared for x, w in zip(row, denominator[0]))
    position = (
        max(abs(x) / w for row in residual for x, w in zip(row, denominator[0])) / native.radius_mm
    )
    increment = None
    if lower > 0:
        inverse_radius = square_root_upper(1 / lower)
        radial_rate = sum(map(abs, native.radial(chart.columns[0])), Fraction(0))
        extent = max(
            abs(chart.high.at(Fraction(q)) - chart.low.at(Fraction(q))) for q, _ in arc.controls
        )
        increment = (1 + native.radius_mm * inverse_radius) * radial_rate * extent
    checkpoint()
    status = (
        "within_support_construction_accuracy"
        if lower > 0
        and position <= Fraction(1, 100)
        and increment is not None
        and increment <= Fraction(1, 100)
        else "unresolved_support_construction_accuracy"
    )
    evidence = FlatCylinderEvidence(chart, arc, native, lower, position, increment)
    return FlatCylinderBound(chart, arc, native, lower, position, increment, status, evidence)
