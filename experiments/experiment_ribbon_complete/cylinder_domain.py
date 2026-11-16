"""
Bound intrinsic cylinder windows and actual line branches without assuming native trim interiors.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from .cylinder_coordinates import CylinderChart
from .exact_frame import Point
from .material_paths import square_root_lower
from .native_face_condition import parameter_bounds
from .ruled_support import square_root_upper


def ratio_hull(
    chart: CylinderChart, controls: tuple[Point, ...]
) -> tuple[Fraction, tuple[Fraction, Fraction]]:
    """
    Bound angular ratio over complete positive-basis controls with strict positive radial coefficients.

    For a positive rational curve, Y/X is a convex blend of y_i/x_i when all
    x_i>0. The caller supplies complete controls and verifies positive weights.
    This bounds the curve only, never a filled trim interior.
    """
    if len(controls) < 2:
        raise ValueError("Complete positive-basis curve controls required")
    values = tuple(chart.affine_coordinates(point) for point in controls)
    lower = min(p[1] for p in values)
    if lower <= 0:
        raise ValueError("A strict positive whole-curve radial branch required")
    ratios = tuple(p[2] / p[1] for p in values)
    return lower, (min(ratios), max(ratios))


@dataclass(frozen=True)
class CylinderLineEvidence:
    """
    Own the exact chart and original line endpoints used for one qualification.
    """

    chart: CylinderChart
    endpoints: tuple[Point, Point]
    bounds: tuple[Fraction, tuple[Fraction, Fraction], Fraction, Fraction, str]


@dataclass(frozen=True)
class CylinderLineBound:
    """
    Retain whole-line branch and axial-fidelity evidence, not exact native/material seam identity.
    """

    chart: CylinderChart
    endpoints: tuple[Point, Point]
    radial_lower_mm: Fraction
    ratio_bounds: tuple[Fraction, Fraction]
    axial_error_upper_mm: Fraction
    height_difference_mm: Fraction
    status: str
    evidence: CylinderLineEvidence

    def __post_init__(self) -> None:
        """
        Reject source replacement while retaining old line bounds.
        """
        if (
            self.evidence.chart is not self.chart
            or self.evidence.endpoints is not self.endpoints
            or self.evidence.bounds
            != (
                self.radial_lower_mm,
                self.ratio_bounds,
                self.axial_error_upper_mm,
                self.height_difference_mm,
                self.status,
            )
        ):
            raise ValueError("The SAME owned cylinder line evidence required")


def inspect_line(
    chart: CylinderChart, endpoints: tuple[Point, Point], checkpoint: Callable[[], None]
) -> CylinderLineBound:
    """
    Check a complete actual line against the cylinder branch and one physical axial-error allowance.
    """
    checkpoint()
    lower, bounds = ratio_hull(chart, endpoints)
    delta = tuple(b - a for a, b in zip(*endpoints))
    error = sum(map(abs, chart.reference.native.radial(delta)), Fraction(0))
    heights = tuple(chart.affine_coordinates(p)[0] for p in endpoints)
    difference = heights[1] - heights[0]
    status = (
        "qualified_axial_cylinder_line_branch"
        if difference != 0 and error <= Fraction(1, 100)
        else "unresolved_axial_cylinder_line_branch"
    )
    checkpoint()
    return CylinderLineBound(
        chart,
        endpoints,
        lower,
        bounds,
        error,
        difference,
        status,
        CylinderLineEvidence(chart, endpoints, (lower, bounds, error, difference, status)),
    )


@dataclass(frozen=True)
class CylinderWindowEvidence:
    """
    Own the chart and physical angular extent of the bounded global coordinate proof.
    """

    chart: CylinderChart
    maximum_abs_ratio: Fraction
    bounds: tuple[Fraction | None, Fraction | None, Fraction | None, Fraction | None, str]


@dataclass(frozen=True)
class CylinderWindowBound:
    """
    Retain global separation/conditioning on a bounded intrinsic window, not proof of actual face coverage.

    Physical coordinates are (axis_coefficient_mm,R*angular_ratio). Height may
    be unbounded. A trim adapter must separately establish that the WHOLE actual
    face belongs to the declared positive branch and angular window.
    """

    chart: CylinderChart
    maximum_abs_ratio: Fraction
    separation_lower: Fraction | None
    forward_upper: Fraction | None
    inverse_upper: Fraction | None
    condition_upper: Fraction | None
    status: str
    evidence: CylinderWindowEvidence

    def __post_init__(self) -> None:
        """
        Refuse using a prior condition bound for a different chart or angular domain.
        """
        if (
            self.evidence.chart is not self.chart
            or self.evidence.maximum_abs_ratio != self.maximum_abs_ratio
            or self.evidence.bounds
            != (
                self.separation_lower,
                self.forward_upper,
                self.inverse_upper,
                self.condition_upper,
                self.status,
            )
        ):
            raise ValueError("The SAME owned cylinder window evidence required")


def certify_window(
    chart: CylinderChart, maximum_abs_ratio: Fraction, checkpoint: Callable[[], None]
) -> CylinderWindowBound:
    """
    Bound global half-cylinder chord separation and independent numerical conditioning on |t|<=T.

    The exact axes a/e/f are pairwise orthogonal. Angle derivative is
    ||e||*||f||/(||e||²+t²||f||²). Across the half-cylinder angle gap is<pi;
    chord length>=half the corresponding arc length. Orthogonal height then
    gives global separation min(||a||,||e||*||f||/(2*(e²+T²*f²))). Forward
    angular-column L1<=2*||f||/||e|| in physical R*t, with no strain allowance.
    """
    checkpoint()
    if (
        chart.status != "qualified_intrinsic_cylinder_basis"
        or type(maximum_abs_ratio) is not Fraction
        or maximum_abs_ratio < 0
    ):
        raise ValueError(
            "A qualified same-source chart and exact nonnegative angular bound required"
        )
    axis, across, normal = chart.evidence.frame.columns
    assert all(
        sum((x * y for x, y in zip(a, b)), Fraction(0)) == 0
        for a, b in ((axis, across), (axis, normal), (across, normal))
    )
    squared = tuple(sum((x * x for x in row), Fraction(0)) for row in (axis, across, normal))
    lows = tuple(square_root_lower(x) for x in squared)
    separation = None
    forward = inverse = condition = None
    status = "unresolved_intrinsic_cylinder_window"
    if min(lows) > 0:
        separation = min(
            lows[0], lows[1] * lows[2] / (2 * (squared[1] + maximum_abs_ratio**2 * squared[2]))
        )
        partials = sum(map(abs, axis), Fraction(0)), 2 * square_root_upper(squared[2]) / lows[1]
        forward, inverse, condition = parameter_bounds(
            partials, (Fraction(1), Fraction(1)), separation
        )
        status = (
            "certified_intrinsic_cylinder_window"
            if condition <= 1024
            else "unresolved_intrinsic_cylinder_window_conditioning"
        )
    checkpoint()
    return CylinderWindowBound(
        chart,
        maximum_abs_ratio,
        separation,
        forward,
        inverse,
        condition,
        status,
        CylinderWindowEvidence(
            chart, maximum_abs_ratio, (separation, forward, inverse, condition, status)
        ),
    )
