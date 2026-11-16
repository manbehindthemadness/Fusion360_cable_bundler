"""
Define intrinsic half-cylinder coordinates from actual world geometry without native UV assumptions.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from artifacts.verification.resume3204.polynomial import add, derivative, elevate, multiply

from .exact_frame import FrameInverse, Point, invert
from .global_chart import cross
from .material_paths import square_root_lower
from .native_cap_material import NativeCapCurve
from .native_flat_cylinder import NativeCylinderSnapshot, radial_field
from .ruled_support import square_root_upper


@dataclass(frozen=True)
class CylinderReference:
    """
    Own a captured actual cross-section arc image and the SAME native cylinder support.

    The adapter verifies face/revision and analytic-to-NURBS image provenance.
    These controls do not define or approximate a native UV parameter map.
    """

    native: NativeCylinderSnapshot
    controls: tuple[Point, ...]
    weights: tuple[Fraction, ...]

    def __post_init__(self) -> None:
        """
        Require complete exact positive quadratic data while leaving branch qualification to the factory.
        """
        if (
            len(self.controls) != 3
            or len(self.weights) != 3
            or any(len(p) != 3 or any(type(x) is not Fraction for x in p) for p in self.controls)
            or any(type(w) is not Fraction or w <= 0 for w in self.weights)
        ):
            raise ValueError("A complete exact positive native reference arc required")


@dataclass(frozen=True)
class CylinderCoordinateEvidence:
    """
    Retain the owned affine basis, whole-reference support error and positive branch bound.
    """

    reference: CylinderReference
    frame: FrameInverse
    reference_error_mm: Fraction
    reference_branch_lower_mm: Fraction | None


@dataclass(frozen=True)
class CylinderPoint:
    """
    Bound one exact half-cylinder image point by a rational candidate and world-L1 uncertainty.
    """

    point: Point
    error_upper_mm: Fraction


@dataclass(frozen=True)
class CylinderCoordinates:
    """
    Retain intrinsic coordinate recovery and world error without native trim or material-label acceptance.
    """

    height_mm: Fraction
    angular_ratio: Fraction | None
    world_upper_mm: Fraction | None
    status: str


@dataclass(frozen=True)
class CylinderChart:
    """
    Map the positive radial half-cylinder bijectively using an exact affine frame and angular ratio.

    Height is the coefficient of an L1-normalized axis, in millimeters. Angular
    ratio is dimensionless; neither coordinate is original material s/q/b or
    a native UV. The1024 gate below bounds the affine basis only, not a uniform
    condition number for the unbounded angular-ratio domain or a material map.
    """

    reference: CylinderReference
    evidence: CylinderCoordinateEvidence

    def __post_init__(self) -> None:
        """
        Refuse replacing the original reference while retaining its coordinate proof.
        """
        if self.evidence.reference is not self.reference:
            raise ValueError("The SAME native reference coordinate evidence required")

    @property
    def status(self) -> str:
        """
        Require positive whole-reference branch, basis conditioning and construction accuracy.
        """
        proof = self.evidence
        inverse = proof.frame.inverse_norm
        lower = proof.reference_branch_lower_mm
        valid = (
            proof.frame.determinant > 0
            and inverse is not None
            and proof.frame.norm * inverse <= 1024
            and lower is not None
            and lower > 0
            and proof.reference_error_mm <= Fraction(1, 100)
        )
        return (
            "qualified_intrinsic_cylinder_basis" if valid else "unresolved_intrinsic_cylinder_basis"
        )

    def affine_coordinates(self, point: Point) -> Point:
        """
        Recover exact height/radial/tangent coefficients without assuming native or material parameter identity.
        """
        rows = self.evidence.frame.rows
        if (
            self.status != "qualified_intrinsic_cylinder_basis"
            or rows is None
            or len(point) != 3
            or any(type(x) is not Fraction for x in point)
        ):
            raise ValueError("A qualified SAME-reference basis and exact world point required")
        delta = tuple(p - o for p, o in zip(point, self.reference.native.origin))
        return tuple(sum((a * b for a, b in zip(row, delta)), Fraction(0)) for row in rows)

    def project(
        self, height_mm: Fraction, angular_ratio: Fraction, checkpoint: Callable[[], None]
    ) -> CylinderPoint:
        """
        Enclose the explicit inverse on the positive half-cylinder with one bounded square root.
        """
        checkpoint()
        if (
            self.status != "qualified_intrinsic_cylinder_basis"
            or type(height_mm) is not Fraction
            or type(angular_ratio) is not Fraction
        ):
            raise ValueError("A qualified basis and exact intrinsic coordinates required")
        axis, across, normal = self.evidence.frame.columns
        direction = tuple(a + angular_ratio * b for a, b in zip(across, normal))
        squared = sum((x * x for x in direction), Fraction(0))
        low, high = square_root_lower(squared), square_root_upper(squared)
        if low <= 0:
            raise ValueError("Positive numerical radial norm enclosure required")
        native = self.reference.native
        point = tuple(
            o + a * height_mm + native.radius_mm * d / low
            for o, a, d in zip(native.origin, axis, direction)
        )
        error = native.radius_mm * sum(map(abs, direction), Fraction(0)) * (1 / low - 1 / high)
        checkpoint()
        return CylinderPoint(point, error)

    def decode(self, point: Point, checkpoint: Callable[[], None]) -> CylinderCoordinates:
        """
        Recover intrinsic coordinates only on the positive branch and retain reconstruction uncertainty.

        A small roundtrip does not prove actual face trim membership. Off-support
        inputs are measured rather than silently treated as exact native points.
        """
        checkpoint()
        height, x, y = self.affine_coordinates(point)
        if x <= 0:
            return CylinderCoordinates(height, None, None, "unresolved_cylinder_branch")
        ratio = y / x
        candidate = self.project(height, ratio, checkpoint)
        error = (
            sum((abs(a - b) for a, b in zip(point, candidate.point)), Fraction(0))
            + candidate.error_upper_mm
        )
        status = (
            "within_intrinsic_coordinate_accuracy"
            if error <= Fraction(1, 100)
            else "unresolved_intrinsic_coordinate_accuracy"
        )
        return CylinderCoordinates(height, ratio, error, status)


def build(reference: CylinderReference, checkpoint: Callable[[], None]) -> CylinderChart:
    """
    Derive an exact orthogonal frame and whole-reference branch without fitting or changing geometry.
    """
    checkpoint()
    native = reference.native
    scale = sum(map(abs, native.axis), Fraction(0))
    axis = tuple(x / scale for x in native.axis)
    radial = tuple(
        native.radial(tuple(p - o for p, o in zip(point, native.origin)))
        for point in (reference.controls[0], reference.controls[-1])
    )
    across = tuple((a + b) / (2 * native.radius_mm) for a, b in zip(*radial))
    normal = cross((axis[0], axis[1], axis[2]), (across[0], across[1], across[2]))
    frame = invert((axis, across, normal))
    field = radial_field(
        native, (reference.controls, reference.controls), reference.weights, checkpoint
    )
    error = (
        max(abs(x) / w for row in field.residual for x, w in zip(row, field.denominator[0]))
        / native.radius_mm
    )
    lower = None
    if frame.rows is not None:
        row = frame.rows[1]
        lower = min(
            sum((a * (p - o) for a, p, o in zip(row, point, native.origin)), Fraction(0))
            for point in reference.controls
        )
    checkpoint()
    return CylinderChart(reference, CylinderCoordinateEvidence(reference, frame, error, lower))


@dataclass(frozen=True)
class CylinderCurveEvidence:
    """
    Own the exact chart/curve and derived branch bounds used by one curve qualification.
    """

    chart: CylinderChart
    curve: NativeCapCurve
    radial_lower_mm: Fraction
    angular_derivative_bounds: tuple[Fraction, Fraction] | None


@dataclass(frozen=True)
class CylinderCurveBranch:
    """
    Retain whole-cap positive-branch and angular progress bounds, not actual trim-domain coverage.
    """

    chart: CylinderChart
    curve: NativeCapCurve
    radial_lower_mm: Fraction
    angular_derivative_bounds: tuple[Fraction, Fraction] | None
    status: str
    evidence: CylinderCurveEvidence

    def __post_init__(self) -> None:
        """
        Prevent source or bound replacement from retaining a previously qualified curve branch.
        """
        owned = self.evidence
        if (
            owned.chart is not self.chart
            or owned.curve is not self.curve
            or owned.radial_lower_mm != self.radial_lower_mm
            or owned.angular_derivative_bounds != self.angular_derivative_bounds
        ):
            raise ValueError("The SAME intrinsic chart/curve branch evidence required")


def inspect_curve(
    chart: CylinderChart, curve: NativeCapCurve, checkpoint: Callable[[], None]
) -> CylinderCurveBranch:
    """
    Bound the exact rational angular ratio and derivative over one complete captured native curve.
    """
    checkpoint()
    if curve.revision != chart.reference.native.revision:
        raise ValueError("The SAME native cylinder revision required")
    coefficients = tuple(chart.affine_coordinates(p) for p in curve.controls)
    lower = min(p[1] for p in coefficients)
    bounds = None
    status = "unresolved_cylinder_curve_branch"
    if lower > 0:
        x = tuple(p[1] * w for p, w in zip(coefficients, curve.weights))
        y = tuple(p[2] * w for p, w in zip(coefficients, curve.weights))
        numerator = elevate(
            add(multiply(derivative(y), x), multiply(y, derivative(x)), Fraction(-1)), 4
        )
        denominator = multiply(x, x)
        rates = tuple(n / w for n, w in zip(numerator, denominator))
        bounds = min(rates), max(rates)
        if (bounds[0] > 0 or bounds[1] < 0) and max(map(abs, bounds)) / min(
            map(abs, bounds)
        ) <= 1024:
            status = "qualified_monotone_cylinder_curve_branch"
    checkpoint()
    evidence = CylinderCurveEvidence(chart, curve, lower, bounds)
    return CylinderCurveBranch(chart, curve, lower, bounds, status, evidence)
